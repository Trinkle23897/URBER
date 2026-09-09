"""Reproduce the paper's fixed-pitch cases with explicitly selected methods."""

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

from research.experiment import ROOT, optimal, run
from route import construct


def published_cases(table):
    with (ROOT / "benchmarks/paper" / f"table_{table}.csv").open() as stream:
        return [
            {
                key: int(value)
                if key in {"N", "M", "d"} or key.endswith("_length")
                else float(value)
                for key, value in row.items()
            }
            for row in csv.DictReader(stream)
        ]


def measure(case, table, method, paths_dir=None):
    n, m, d = (case[key] for key in ("N", "M", "d"))
    started = time.perf_counter()
    path = None
    if paths_dir is not None:
        paths_dir.mkdir(parents=True, exist_ok=True)
        path = paths_dir / f"{method}-{n}x{m}-d{d}.json"
    if method == "paper":
        result = run(n, m, d, path=path)
    elif method == "single_pass":
        result = construct(n, m, d, path)
    elif method == "geometric":
        process = subprocess.run(
            [sys.executable, str(ROOT / "research/replay.py"), str(n), str(m), str(d)]
            + ([str(path)] if path else []),
            capture_output=True,
            text=True,
            check=True,
        )
        result = json.loads(process.stdout)
    else:
        result = optimal(n, m, d, path=path)
    wall = time.perf_counter() - started
    if not result.get("verified", result.get("feasible", False)):
        raise RuntimeError(f"{method} failed at {(n, m, d)}: {result}")
    return {
        "table": table,
        "N": n,
        "M": m,
        "d": d,
        "method": method,
        "total_length": result["total_length"],
        "wall_seconds": wall,
        "engine_seconds": result.get("constructor_seconds", result.get("seconds")),
        "published_urber_length": case["urber_length"],
        "published_mcf_length": case.get("mcf_length"),
        "delta_to_published_urber": result["total_length"] - case["urber_length"],
        "delta_to_published_mcf": (
            result["total_length"] - case["mcf_length"]
            if "mcf_length" in case
            else None
        ),
        "constructor": result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", choices=("ii", "iii"), default="ii")
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=("paper", "single_pass", "geometric", "mcf"),
        default=["paper", "single_pass"],
        help="geometric selects the legacy replay portfolio",
    )
    parser.add_argument("--case", nargs=2, type=int, metavar=("N", "M"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--paths-dir", type=Path, help="export paths for routing figures"
    )
    args = parser.parse_args()
    cases = published_cases(args.table)
    if args.case:
        cases = [r for r in cases if [r["N"], r["M"]] == args.case]
        if not cases:
            parser.error("--case must be a row of the selected published table")
    methods = list(dict.fromkeys(args.methods))
    output = (
        args.output
        or ROOT / "results" / f"paper-{args.table}-{'-'.join(methods)}.jsonl"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    files = [
        "research/paper.py",
        "research/experiment.py",
        f"benchmarks/paper/table_{args.table}.csv",
    ]
    if "paper" in methods:
        files += ["build/urber"]
    if "single_pass" in methods:
        files += ["route.py", "build/construct", "build/pure_fan"]
    if "geometric" in methods:
        files += [
            "research/replay.py",
            "profiles.json",
            "build/pure_router",
            "build/pure_fan",
        ]
    signature = hashlib.sha256(
        json.dumps(
            {
                "files": {
                    p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                    for p in files
                },
                "python": sys.version,
                "platform": platform.platform(),
                "paths_dir": str(args.paths_dir),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    done = set()
    if args.resume and output.exists():
        for line in output.read_text().splitlines():
            row = json.loads(line)
            if row.get("run_signature") != signature:
                parser.error(
                    "checkpoint code or environment differs; choose another --output"
                )
            done.add((row["N"], row["M"], row["d"], row["method"]))
    # Run serially so the methods do not compete for CPU during timing.
    with output.open("a" if args.resume else "x") as stream:
        for case in cases:
            for method in methods:
                key = case["N"], case["M"], case["d"], method
                if key in done:
                    continue
                row = measure(case, args.table, method, args.paths_dir)
                row["run_signature"] = signature
                stream.write(json.dumps(row) + "\n")
                stream.flush()
                print(
                    f"{method}: {key[:3]}, L={row['total_length']}, wall={row['wall_seconds']:.6f}s",
                    flush=True,
                )
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
