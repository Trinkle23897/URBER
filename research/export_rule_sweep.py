"""Validate and publish complete deterministic-rule sweep shards."""

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

from route import ROOT


def digest(data):
    return hashlib.sha256(data).hexdigest()


def classification(length, bound, witness):
    if length < bound:
        raise ValueError("A routing is shorter than its recorded lower bound")
    return (
        "optimal"
        if length == bound
        else "nonoptimal"
        if witness < length
        else "unknown"
    )


def collect(inputs, max_n):
    with (ROOT / "benchmarks/rules400/results.csv").open() as stream:
        reference = {(int(r["N"]), int(r["M"])): r for r in csv.DictReader(stream)}
    rows, sources = {}, []
    common = None
    repeated = 0
    for folder in inputs:
        manifest = json.loads((folder / "run.json").read_text())
        signature = manifest.pop("signature")
        if signature != digest(json.dumps(manifest, sort_keys=True).encode()):
            raise ValueError("Invalid run manifest signature")
        if manifest["max_n"] != max_n:
            raise ValueError("Mixed sweep domains")
        # Binaries may differ across compilers; retain every binary hash below.
        scripts = {
            k: v for k, v in manifest["files"].items() if not k.startswith("build/")
        }
        if common is None:
            common = scripts
        if scripts != common or scripts["benchmarks/rules400/results.csv"] != digest(
            (ROOT / "benchmarks/rules400/results.csv").read_bytes()
        ):
            raise ValueError("Mixed source scripts or reference dataset")
        raw = (folder / "results.jsonl").read_bytes()
        count = 0
        for line in raw.splitlines():
            r = json.loads(line)
            n, m, d = (r[k] for k in ("N", "M", "d"))
            if not all(type(v) is int for v in (n, m, d)) or not (
                1 <= n <= max_n and 1 <= m <= max_n
            ):
                raise ValueError("Out-of-domain case")
            if ((n - 1) * max_n + m - 1) % manifest["shards"] != manifest["shard"]:
                raise ValueError("Case belongs to a different shard")
            ref = reference[n, m]
            if (
                d,
                r["lower_bound"],
                r["paper_length"],
                r["reference_length"],
            ) != tuple(
                int(ref[k])
                for k in ("d", "lower_bound", "paper_length", "total_length")
            ):
                raise ValueError("Case differs from the fixed-pitch reference")
            native = r["constructor"]
            if (
                not native.get("verified")
                or native.get("residual_work") != 0
                or native.get("method") not in {"proven_fan", "geometric_single_pass"}
                or (native["N"], native["M"], native["d"], native["total_length"])
                != (n, m, d, r["total_length"])
            ):
                raise ValueError("Invalid native construction record")
            expected = classification(
                r["total_length"],
                r["lower_bound"],
                min(r["paper_length"], r["reference_length"]),
            )
            if expected != r["status"]:
                raise ValueError("Incorrect optimality classification")
            if (n, m) in rows:
                prior = rows[n, m]
                if any(
                    prior[k] != r[k]
                    for k in ("d", "lower_bound", "total_length", "status")
                ):
                    raise ValueError("Conflicting repeated observations")
                if any(
                    prior["constructor"].get(k) != native.get(k)
                    for k in ("method", "optimality_certified", "revised_rules")
                ):
                    raise ValueError("Mixed constructor records")
                repeated += 1
            else:
                rows[n, m] = r
            count += 1
        sources.append(
            dict(
                rows=count, results_sha256=digest(raw), signature=signature, **manifest
            )
        )
    if len(rows) != max_n * max_n:
        raise ValueError(f"Incomplete coverage: {len(rows)}/{max_n * max_n}")
    return [rows[k] for k in sorted(rows)], sources, repeated


def summarize(rows):
    result = {"cases": len(rows)}
    for method, field in (("paper", "paper_length"), ("revised", "total_length")):
        statuses = Counter()
        for r in rows:
            witness = min(
                r["reference_length"],
                r["total_length"] if method == "paper" else r["paper_length"],
            )
            statuses[classification(r[field], r["lower_bound"], witness)] += 1
        result[method] = dict(
            statuses=dict(statuses),
            optimal_percent=100 * statuses["optimal"] / len(rows) if rows else None,
        )
    result["revised_vs_paper"] = dict(
        Counter(
            "shorter"
            if r["total_length"] < r["paper_length"]
            else "longer"
            if r["total_length"] > r["paper_length"]
            else "equal"
            for r in rows
        )
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--max-n", type=int, default=400)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.max_n <= 400:
        parser.error("require 1 <= max-n <= 400")
    rows, sources, repeated = collect(args.inputs, args.max_n)
    candidate = {
        "hashes": {
            name: value
            for name, value in sources[0]["files"].items()
            if not name.startswith("build/")
        }
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "candidate.json").write_text(json.dumps(candidate, indent=2) + "\n")
    raw = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()
    (args.output / "results.jsonl.gz").write_bytes(gzip.compress(raw, mtime=0))
    fields = [
        "N",
        "M",
        "d",
        "lower_bound",
        "paper_length",
        "total_length",
        "reference_length",
        "status",
    ]
    with (args.output / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream, fields, lineterminator="\n", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)
    summary = dict(
        full_square=summarize(rows),
        paper_dimensions_30_100=summarize(
            [r for r in rows if 30 <= r["N"] <= 100 and 30 <= r["M"] <= 100]
        ),
        thin_canonical=summarize([r for r in rows if r["M"] <= r["N"] // 5]),
    )
    provenance = dict(
        candidate=candidate,
        max_n=args.max_n,
        consistent_repeated_rows=repeated,
        inputs=sources,
        artifacts={
            name: digest((args.output / name).read_bytes())
            for name in ["results.csv", "results.jsonl.gz"]
        },
    )
    for name, value in [("summary.json", summary), ("provenance.json", provenance)]:
        (args.output / name).write_text(json.dumps(value, indent=2) + "\n")
    (args.output / "_SUCCESS").write_text(json.dumps({"cases": len(rows)}) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
