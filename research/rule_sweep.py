"""Evaluate one deterministic construction on the recorded 1..400 pitches."""

import argparse
import csv
import hashlib
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from route import ROOT, construct


def evaluate(row):
    n, m, d = (int(row[key]) for key in ("N", "M", "d"))
    bound = int(row["lower_bound"])
    result = construct(n, m, d)
    length = result["total_length"]
    if length < bound:
        raise ValueError(f"Length below the independent bound: {(n, m, d)}")
    witness = min(int(row["paper_length"]), int(row["total_length"]))
    return {
        "N": n,
        "M": m,
        "d": d,
        "lower_bound": bound,
        "paper_length": int(row["paper_length"]),
        "reference_length": int(row["total_length"]),
        "total_length": length,
        "status": "optimal"
        if length == bound
        else "nonoptimal"
        if witness < length
        else "unknown",
        "constructor": result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-n", type=int, default=400)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.max_n <= 400 or args.workers < 1:
        parser.error("require 1 <= max-n <= 400 and positive workers")
    if args.shards < 1 or not 0 <= args.shard < args.shards:
        parser.error("require 0 <= shard < shards")
    data = ROOT / "benchmarks/rules400/results.csv"
    with data.open() as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if max(int(row["N"]), int(row["M"])) <= args.max_n
            and ((int(row["N"]) - 1) * args.max_n + int(row["M"]) - 1) % args.shards
            == args.shard
        ]
    # Start expensive cases first; short cases fill the remaining gaps in the pool.
    rows.sort(
        key=lambda r: (
            int(r["N"]) * int(r["M"]) * int(r["d"]) * (int(r["N"]) + int(r["M"]))
        ),
        reverse=True,
    )
    files = [
        "route.py",
        "research/rule_sweep.py",
        "build/construct",
        "build/pure_fan",
        "benchmarks/rules400/results.csv",
        "src/router.hpp",
        "src/construct.cpp",
        "src/pure/pure_fan.cpp",
        "src/routing_types.hpp",
        "src/verify.hpp",
    ]
    metadata = {
        "files": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in files
        },
        "max_n": args.max_n,
        "shards": args.shards,
        "shard": args.shard,
    }
    signature = hashlib.sha256(
        json.dumps(metadata, sort_keys=True).encode()
    ).hexdigest()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = args.output / "run.json"
    results = args.output / "results.jsonl"
    expected = {(int(r["N"]), int(r["M"])) for r in rows}
    done = set()
    counts = {}
    if args.resume:
        if (
            not manifest.exists()
            or json.loads(manifest.read_text())["signature"] != signature
        ):
            parser.error("checkpoint does not match the current constructor and domain")
        if results.exists():
            for line in results.read_text().splitlines():
                row = json.loads(line)
                key = row["N"], row["M"]
                if (
                    key not in expected
                    or key in done
                    or not row["constructor"]["verified"]
                ):
                    parser.error("invalid checkpoint row")
                done.add(key)
                counts[row["status"]] = counts.get(row["status"], 0) + 1
    else:
        if manifest.exists() or results.exists():
            parser.error("output already exists; choose --resume or a new directory")
        manifest.write_text(
            json.dumps(dict(signature=signature, **metadata), indent=2) + "\n"
        )
    pending = [r for r in rows if (int(r["N"]), int(r["M"])) not in done]
    started = time.monotonic()
    errors = 0
    with (
        results.open("a") as out,
        (args.output / "errors.jsonl").open("a") as err,
        ThreadPoolExecutor(args.workers) as pool,
    ):
        futures = {pool.submit(evaluate, row): row for row in pending}
        for future in as_completed(futures):
            source = futures[future]
            try:
                row = future.result()
            except (
                OSError,
                subprocess.SubprocessError,
                ValueError,
                RuntimeError,
            ) as error:
                errors += 1
                err.write(
                    json.dumps(
                        {"N": source["N"], "M": source["M"], "error": repr(error)}
                    )
                    + "\n"
                )
                err.flush()
            else:
                out.write(json.dumps(row) + "\n")
                out.flush()
                done.add((row["N"], row["M"]))
                counts[row["status"]] = counts.get(row["status"], 0) + 1
            if (len(done) + errors) % 100 == 0 or len(done) + errors == len(expected):
                progress = {
                    "completed": len(done),
                    "expected": len(expected),
                    "errors": errors,
                    "counts": counts,
                    "seconds": time.monotonic() - started,
                }
                temporary = args.output / "progress.tmp"
                temporary.write_text(json.dumps(progress) + "\n")
                temporary.replace(args.output / "progress.json")
                print(json.dumps(progress), flush=True)
    if done != expected:
        raise RuntimeError(
            f"Incomplete sweep: {len(done)}/{len(expected)}, {errors} errors"
        )
    (args.output / "_SUCCESS").write_text(
        json.dumps({"cases": len(done), "counts": counts, "signature": signature})
        + "\n"
    )


if __name__ == "__main__":
    main()
