"""Merge repeated sweep observations only after checking agreement and coverage."""

import argparse
import hashlib
import json
from pathlib import Path

from research.full_sweep import classify


def merge(inputs, max_n, shard=0, shards=1):
    expected = {
        (nn, mm)
        for n in range(1, max_n + 1)
        for m in range(1, n + 1)
        if (n * (n - 1) // 2 + m - 1) % shards == shard
        for nn, mm in ((n, m), (m, n))
    }
    rows, sources, repeats = {}, [], 0
    for directory in inputs:
        path = directory / "results.jsonl"
        raw = path.read_bytes()
        seen = set()
        for line in raw.splitlines():
            row = json.loads(line)
            key = row["N"], row["M"]
            if key not in expected or key in seen:
                raise ValueError(f"Out-of-domain or duplicate input row: {key}")
            seen.add(key)
            if row["d"] < 1 or row["lower_bound"] < 0:
                raise ValueError(f"Invalid pitch or bound: {key}")
            for method, other in (("paper", "geometric"), ("geometric", "paper")):
                result = row[method]
                if (
                    result
                    and result.get("verified")
                    and result["total_length"] < row["lower_bound"]
                ):
                    raise ValueError(f"Routing below bound: {key}")
                if row[f"{method}_status"] != classify(
                    result, row["lower_bound"], row[other]
                ):
                    raise ValueError(f"Invalid status: {key}")
            if key in rows:
                previous = rows[key]
                fields = ("d", "lower_bound", "paper_status", "geometric_status")

                def lengths(r):
                    return tuple(
                        (r[k] or {}).get("total_length") for k in ("paper", "geometric")
                    )

                if any(previous[k] != row[k] for k in fields) or lengths(
                    previous
                ) != lengths(row):
                    raise ValueError(f"Repeated observations disagree: {key}")
                repeats += 1
            else:
                rows[key] = row
        sources.append(
            dict(
                name=directory.name,
                rows=len(seen),
                results_sha256=hashlib.sha256(raw).hexdigest(),
                run=json.loads((directory / "run.json").read_text()),
                input_complete=(directory / "_SUCCESS").exists(),
            )
        )
    missing = expected - rows.keys()
    if missing:
        raise ValueError(
            f"Incomplete coverage: {len(rows)}/{len(expected)}; missing examples {sorted(missing)[:5]}"
        )
    return [rows[key] for key in sorted(rows)], dict(
        kind="merged_observations",
        max_n=max_n,
        shard=shard,
        shards=shards,
        cases=len(rows),
        consistent_repeated_rows=repeats,
        sources=sources,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--max-n", type=int, default=400)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.max_n < 1 or not 0 <= args.shard < args.shards:
        parser.error("Invalid dimensions or shard")
    rows, metadata = merge(args.inputs, args.max_n, args.shard, args.shards)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "results.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows)
    )
    (args.output / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (args.output / "_SUCCESS").write_text(
        f"Verified complete coverage of {len(rows)} ordered cases.\n"
    )
    print(json.dumps({k: v for k, v in metadata.items() if k != "sources"}))


if __name__ == "__main__":
    main()
