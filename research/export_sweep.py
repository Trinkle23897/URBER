"""Publish a verified merged sweep as CSV, compressed observations, and summary."""

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

from research.full_sweep import classify


def summarize(rows):
    result = {"cases": len(rows)}
    for method in ("paper", "geometric"):
        gaps = [r[method]["total_length"] - r["lower_bound"] for r in rows]
        counts = dict(Counter(r[f"{method}_status"] for r in rows))
        largest = max(gaps, default=0)
        result[method] = {
            "statuses": counts,
            "optimal_percent": 100 * counts.get("optimal", 0) / len(rows)
            if rows
            else None,
            "max_lower_bound_gap": largest,
            "max_gap_examples": [
                [r["N"], r["M"], r["d"]] for r, gap in zip(rows, gaps) if gap == largest
            ][:10],
        }
    result["geometric_vs_paper"] = dict(
        Counter(
            "shorter"
            if r["geometric"]["total_length"] < r["paper"]["total_length"]
            else "longer"
            if r["geometric"]["total_length"] > r["paper"]["total_length"]
            else "equal"
            for r in rows
        )
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    metadata = json.loads((args.input / "run.json").read_text())
    if (
        metadata.get("kind") != "merged_observations"
        or not (args.input / "_SUCCESS").exists()
    ):
        raise ValueError("Export requires a completed research.merge_sweep output")
    raw = (args.input / "results.jsonl").read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    max_n = metadata["max_n"]
    if len(rows) != max_n**2 or {(r["N"], r["M"]) for r in rows} != {
        (n, m) for n in range(1, max_n + 1) for m in range(1, max_n + 1)
    }:
        raise ValueError("Export requires complete, unique square coverage")
    for r in rows:
        for method, other in (("paper", "geometric"), ("geometric", "paper")):
            witness = r[method]
            if (
                not witness
                or not witness.get("verified")
                or witness.get("residual_work", 0)
            ):
                raise ValueError(
                    "Expected verified geometric witnesses without residual work"
                )
            if witness["total_length"] < r["lower_bound"] or r[
                f"{method}_status"
            ] != classify(witness, r["lower_bound"], r[other]):
                raise ValueError("Inconsistent lower bound or status")
    args.output.mkdir(parents=True, exist_ok=True)
    with (
        (args.output / "results.jsonl.gz").open("wb") as target,
        gzip.GzipFile(filename="", fileobj=target, mode="wb", mtime=0) as packed,
    ):
        packed.write(raw)
    fields = [
        "N",
        "M",
        "d",
        "lower_bound",
        "paper_length",
        "geometric_length",
        "paper_gap",
        "geometric_gap",
        "paper_status",
        "geometric_status",
        "pitch_source",
        "bound_source",
    ]
    with (args.output / "results.csv").open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            row = {k: r[k] for k in fields if k in r}
            for method in ("paper", "geometric"):
                row[f"{method}_length"] = r[method]["total_length"]
                row[f"{method}_gap"] = row[f"{method}_length"] - r["lower_bound"]
            writer.writerow(row)
    summary = {
        "full_square": summarize(rows),
        "paper_dimensions_30_100": summarize(
            [r for r in rows if 30 <= r["N"] <= 100 and 30 <= r["M"] <= 100]
        ),
        "thin_canonical": summarize([r for r in rows if r["M"] <= r["N"] // 5]),
    }
    # Whitelist provenance fields; never export operational host names or paths.
    provenance = {
        "source_commit": args.source_commit,
        "max_n": max_n,
        "consistent_repeated_rows": metadata["consistent_repeated_rows"],
        "merged_jsonl_sha256": hashlib.sha256(raw).hexdigest(),
        "artifacts": {
            name: hashlib.sha256((args.output / name).read_bytes()).hexdigest()
            for name in ("results.csv", "results.jsonl.gz")
        },
        "inputs": [
            {
                "id": f"input-{i:02d}",
                "rows": s["rows"],
                "results_sha256": s["results_sha256"],
                "input_complete": s["input_complete"],
                "run": {
                    k: s["run"][k]
                    for k in (
                        "signature",
                        "workers",
                        "candidate_workers",
                        "created_utc",
                        "platform",
                    )
                    if k in s["run"]
                },
            }
            for i, s in enumerate(metadata["sources"], 1)
        ],
    }
    for name, data in (("summary.json", summary), ("provenance.json", provenance)):
        (args.output / name).write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
