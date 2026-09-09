"""Audit recorded witnesses or run the legacy replay portfolio on the complete domain."""

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_cases():
    with (ROOT / "benchmarks/thin_400.csv").open(newline="") as stream:
        return [
            {
                key: (value if key == "mode" else int(value) if value else None)
                for key, value in row.items()
            }
            for row in csv.DictReader(stream)
        ]


def audit(row, mode, check_bounds=False):
    dimensions = [str(row[key]) for key in ("N", "M", "d")]
    if mode == "paper":
        command = [str(ROOT / "build/urber"), *dimensions]
    elif mode == "portfolio":
        command = [sys.executable, str(ROOT / "research/replay.py"), *dimensions]
    elif row["mode"] == "fan":
        command = [str(ROOT / "build/pure_fan"), *dimensions]
    else:
        command = [str(ROOT / "build/pure_router"), *dimensions, "--mode", row["mode"]]
        if row["mode"] == "baseline":
            command += ["--alpha", "110"]
        else:
            for key in ("candidate", "phase", "alpha", "tie"):
                command += ["--" + key, str(row[key])]
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    if process.returncode and not (
        mode == "paper" and process.returncode == 1 and process.stdout
    ):
        raise RuntimeError(f"{dimensions}: {process.stderr.strip()}")
    result = json.loads(process.stdout)
    verified = result.get("verified", False)
    if (not verified and mode != "paper") or result.get("residual_work", 0):
        raise RuntimeError(f"Unverified or residual-based result: {dimensions}")
    if mode != "paper" and result["total_length"] != row["total_length"]:
        raise RuntimeError(f"Length mismatch: {dimensions}: {result['total_length']}")
    if mode == "witness" and row["mode"] in ("guided", "deep"):
        for key in ("weighted_grid_visits", "replay_attempts", "accepted_replays"):
            if result[key] != row[key]:
                raise RuntimeError(f"Replay trace mismatch: {dimensions}: {key}")
    bound = row["lower_bound"]
    if check_bounds:
        from research.bounds import assignment_lower_bound

        recomputed = assignment_lower_bound(row["N"], row["M"], row["d"])
        if recomputed != bound:
            raise RuntimeError(f"Lower-bound mismatch: {dimensions}")
    if verified and result["total_length"] < bound:
        raise RuntimeError(f"Verified result below the lower bound: {dimensions}")
    if mode != "paper" and result["total_length"] != bound:
        raise RuntimeError(f"Optimality gap: {dimensions}")
    return {
        "N": row["N"],
        "M": row["M"],
        "d": row["d"],
        "audit_mode": mode,
        "lower_bound": bound,
        "bound_recomputed": check_bounds,
        "optimality_verified_offline": verified and result["total_length"] == bound,
        "constructor": result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("portfolio", "witness", "paper"), default="portfolio"
    )
    parser.add_argument("--max-n", type=int, default=400)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--check-bounds", action="store_true")
    parser.add_argument(
        "--resume", action="store_true", help="resume a matching audit checkpoint"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 5 <= args.max_n <= 400 or args.workers < 1:
        parser.error("--max-n must be in 5..400 and --workers must be positive")
    rows = [row for row in load_cases() if row["N"] <= args.max_n]
    suffix = "-checked-bounds" if args.check_bounds else ""
    output = (
        args.output
        or ROOT / "results" / f"audit-{args.mode}-{args.max_n}{suffix}.jsonl"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    inputs = [
        "research/replay.py",
        "profiles.json",
        "build/pure_router",
        "build/pure_fan",
        "build/urber",
        "benchmarks/thin_400.csv",
        "research/benchmark.py",
        "research/bounds.py",
    ]
    fingerprint = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in inputs
    }
    fingerprint.update(mode=args.mode, max_n=args.max_n, check_bounds=args.check_bounds)
    signature = hashlib.sha256(
        json.dumps(fingerprint, sort_keys=True).encode()
    ).hexdigest()
    done = set()
    expected = {(row["N"], row["M"], row["d"]) for row in rows}
    if args.resume and output.exists():
        for line in output.read_text().splitlines():
            saved = json.loads(line)
            key = saved["N"], saved["M"], saved["d"]
            if (
                saved.get("run_signature") != signature
                or key not in expected
                or key in done
                or not (
                    saved.get("optimality_verified_offline") or args.mode == "paper"
                )
            ):
                parser.error(
                    "checkpoint does not match this audit; use a new --output path"
                )
            done.add(key)
    pending_rows = [row for row in rows if (row["N"], row["M"], row["d"]) not in done]
    with (
        output.open("a" if args.resume else "x") as stream,
        ThreadPoolExecutor(args.workers) as pool,
    ):
        pending = [
            pool.submit(audit, row, args.mode, args.check_bounds)
            for row in pending_rows
        ]
        for completed, future in enumerate(as_completed(pending), len(done) + 1):
            result = future.result()
            result["run_signature"] = signature
            stream.write(json.dumps(result) + "\n")
            stream.flush()
            if completed % 100 == 0 or completed == len(rows):
                print(f"Evaluated {completed}/{len(rows)}", flush=True)
    print(f"Evaluated {len(rows)} cases; saved {output}")


if __name__ == "__main__":
    main()
