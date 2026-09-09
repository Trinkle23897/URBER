"""Parallel, resumable comparison on every ordered pair 1 <= N,M <= max_n.

Bounds and early stopping are offline evaluation only. Every accepted witness
is a candidate of the unmodified runtime portfolio and is geometrically checked.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
from pathlib import Path
import platform
import subprocess
import threading
import time

from research.benchmark import ROOT, load_cases
from research.bounds import assignment_lower_bound
from research.experiment import min_pitch, run
from research.paper import published_cases


def native(n, m, d, config=None):
    command = [
        str(ROOT / "build" / ("pure_fan" if config is None else "pure_router")),
        str(n),
        str(m),
        str(d),
    ]
    for key, value in (config or {}).items():
        command += ["--" + key, str(value)]
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode:
        if (
            process.returncode == 1
            and "all constructive candidates failed" in process.stderr
        ):
            return None
        raise RuntimeError(
            f"Constructor execution failed ({process.returncode}): {process.stderr.strip()}"
        )
    result = json.loads(process.stdout)
    if not result.get("verified") or result.get("residual_work", 0):
        raise RuntimeError("The pure constructor returned an invalid result")
    return result


def configurations(n, m, profiles, preferred=None):
    pool = (
        ([preferred] if preferred else [])
        + [
            dict(mode="baseline", alpha=110, candidate=candidate, phase=phase)
            for phase in range(4)
            for candidate in range(4)
        ]
        + profiles
    )
    seen = set()
    for config in pool:
        nn, mm = (m, n) if config["candidate"] & 2 else (n, m)
        key = (
            config["mode"],
            config["alpha"],
            config.get("tie", 1),
            config["candidate"],
            (config["phase"] >> 1) & 1 if mm % 2 else 0,
            config["phase"] & 1 if nn % 2 else 0,
        )
        if key not in seen:
            seen.add(key)
            yield config


def classify(result, bound, other):
    if not result or not result.get("verified"):
        return "construction_failed"
    if result["total_length"] == bound:
        return "optimal"
    if (
        other
        and other.get("verified")
        and other["total_length"] < result["total_length"]
    ):
        return "nonoptimal"
    return "unknown"


def initialize_worker(pitches, profiles, done, active):
    global WORKER_STATE
    WORKER_STATE = pitches, profiles, done, active


def pair(n, m):
    pitches, profiles, done, active = WORKER_STATE

    def stage(key, value):
        active[str(key)] = value

    key = n, m
    try:
        stage(key, "pitch")
        d = pitches.get(key)
        if d is None:
            d = min_pitch(n, m)["d"]
        stage(key, "lower_bound")
        fan = native(n, m, d) if 2 * d >= m else None
        bound = fan["total_length"] if fan else assignment_lower_bound(n, m, d)
        if bound is None:
            raise RuntimeError("No finite assignment lower bound at a routable pitch")
        rows, preferred = [], None
        for nn, mm in [(n, m)] + ([(m, n)] if n != m else []):
            if (nn, mm) in done:
                continue
            stage(key, f"paper {nn}x{mm}")
            paper = run(nn, mm, d)
            if paper.get("verified") and paper["total_length"] < bound:
                raise RuntimeError("Paper routing below the lower bound")
            best, selected, attempts = None, None, 0
            if fan:
                best = fan if nn == n else native(nn, mm, d)
            else:
                for config in configurations(nn, mm, profiles, preferred):
                    attempts += 1
                    stage(key, f"geometric {nn}x{mm} candidate {attempts}: {config}")
                    candidate = native(nn, mm, d, config)
                    if candidate and (
                        best is None or candidate["total_length"] < best["total_length"]
                    ):
                        best, selected = candidate, config
                    if best and best["total_length"] < bound:
                        raise RuntimeError("Geometric routing below the lower bound")
                    if best and best["total_length"] == bound:
                        break
                preferred = selected
            rows.append(
                dict(
                    N=nn,
                    M=mm,
                    d=d,
                    lower_bound=bound,
                    bound_source="fan_theorem" if fan else "boundary_assignment",
                    pitch_source="fixed_benchmark"
                    if key in pitches
                    else "canonical_paper_bisection",
                    paper=paper,
                    geometric=best,
                    geometric_config=selected,
                    trials=attempts,
                    paper_status=classify(paper, bound, best),
                    geometric_status=classify(best, bound, paper),
                )
            )
        return rows, None
    except Exception as error:
        return [], dict(N=n, M=m, error=repr(error))
    finally:
        active.pop(str(key), None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-n", type=int, default=400)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--output", type=Path, default=ROOT / "results/full-400")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--pairs", type=Path, help="JSON list of canonical [N,M] pairs to evaluate"
    )
    args = parser.parse_args()
    if args.max_n < 1 or args.workers < 1:
        parser.error("dimensions and workers must be positive")
    if args.shards < 1 or not 0 <= args.shard < args.shards:
        parser.error("require 0 <= shard < shards")
    assigned = None
    if args.pairs:
        if args.shards != 1 or args.shard != 0:
            parser.error("--pairs cannot be combined with sharding")
        pairs = json.loads(args.pairs.read_text())
        if not isinstance(pairs, list) or any(
            not isinstance(pair, list)
            or len(pair) != 2
            or any(type(x) is not int for x in pair)
            or not 1 <= pair[1] <= pair[0] <= args.max_n
            for pair in pairs
        ):
            parser.error(
                "--pairs requires canonical integer pairs 1 <= M <= N <= max-n"
            )
        assigned = [tuple(pair) for pair in pairs]
        if len(set(assigned)) != len(assigned):
            parser.error("duplicate pair in --pairs manifest")
    args.output.mkdir(parents=True, exist_ok=True)
    files = [
        "build/urber",
        "build/pure_router",
        "build/pure_fan",
        "profiles.json",
        "research/full_sweep.py",
        "research/bounds.py",
        "research/experiment.py",
        "benchmarks/thin_400.csv",
        "benchmarks/paper/table_ii.csv",
        "benchmarks/paper/table_iii.csv",
    ]
    signature = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files}
    if args.pairs:
        signature["pair_manifest_sha256"] = hashlib.sha256(
            args.pairs.read_bytes()
        ).hexdigest()
    signature["max_n"] = args.max_n
    signature["shard"] = args.shard
    signature["shards"] = args.shards
    metadata = args.output / "run.json"
    if metadata.exists():
        if not args.resume:
            parser.error("output already exists; use --resume or another directory")
        if json.loads(metadata.read_text())["signature"] != signature:
            parser.error("checkpoint source/binary signature differs")
    else:
        metadata.write_text(
            json.dumps(
                dict(
                    signature=signature,
                    workers=args.workers,
                    created_utc=datetime.now(timezone.utc).isoformat(),
                    platform=platform.platform(),
                ),
                indent=2,
            )
            + "\n"
        )
    profiles = json.loads((ROOT / "profiles.json").read_text())["profiles"]
    pitches = {(r["N"], r["M"]): r["d"] for r in load_cases()}
    for table in ("ii", "iii"):
        for r in published_cases(table):
            key = max(r["N"], r["M"]), min(r["N"], r["M"])
            if key in pitches and pitches[key] != r["d"]:
                raise RuntimeError(f"Conflicting fixed pitches for {key}")
            pitches[key] = r["d"]
    results_path = args.output / "results.jsonl"
    done, counts = set(), {method: {} for method in ("paper", "geometric")}

    def count(row):
        for method in counts:
            status = row[f"{method}_status"]
            counts[method][status] = counts[method].get(status, 0) + 1

    if results_path.exists():
        for line in results_path.read_text().splitlines():
            row = json.loads(line)
            key = row["N"], row["M"]
            if key in done:
                raise RuntimeError(f"Duplicate completed case {key}")
            done.add(key)
            count(row)
    context = multiprocessing.get_context("spawn")
    manager = context.Manager()
    active, lock, finished = manager.dict(), threading.Lock(), threading.Event()
    started = time.monotonic()
    failures = []
    assigned = (
        assigned
        if assigned is not None
        else [
            (n, m)
            for n in range(1, args.max_n + 1)
            for m in range(1, n + 1)
            if (n * (n - 1) // 2 + m - 1) % args.shards == args.shard
        ]
    )
    assigned_total = sum(1 if n == m else 2 for n, m in assigned)

    def progress():
        with lock:
            state = dict(
                completed=len(done),
                total=assigned_total,
                global_total=args.max_n**2,
                domain="explicit_pairs" if args.pairs else "full_shard",
                shard=args.shard,
                counts=counts,
                errors=len(failures),
                active=active.copy(),
                elapsed_seconds=time.monotonic() - started,
                updated_utc=datetime.now(timezone.utc).isoformat(),
            )
            text = json.dumps(state, indent=2) + "\n"
        temporary = args.output / "progress.tmp"
        temporary.write_text(text)
        temporary.replace(args.output / "progress.json")
        print(
            f"Completed {state['completed']}/{state['total']}; errors={state['errors']}; active={len(state['active'])}",
            flush=True,
        )

    def monitor():
        while not finished.wait(30):
            progress()

    todo = [(n, m) for n, m in assigned if (n, m) not in done or (m, n) not in done]
    probes = {
        (args.max_n, args.max_n),
        (args.max_n, max(1, args.max_n - 1)),
        (args.max_n, max(1, args.max_n // 2)),
    }
    if not args.pairs:
        todo.sort(key=lambda key: (key not in probes, *key))
    reporter = threading.Thread(target=monitor, daemon=True)
    reporter.start()
    try:
        with (
            results_path.open("a") as output,
            (args.output / "errors.jsonl").open("a") as errors,
        ):
            with ProcessPoolExecutor(
                args.workers,
                mp_context=context,
                initializer=initialize_worker,
                initargs=(pitches, profiles, done, active),
            ) as pool:
                for future in as_completed([pool.submit(pair, *key) for key in todo]):
                    rows, error = future.result()
                    if error:
                        failures.append(error)
                        errors.write(json.dumps(error) + "\n")
                        errors.flush()
                    for row in rows:
                        output.write(json.dumps(row) + "\n")
                        output.flush()
                        with lock:
                            done.add((row["N"], row["M"]))
                            count(row)
    finally:
        finished.set()
        reporter.join()
        progress()
        manager.shutdown()
    if failures or len(done) != assigned_total:
        raise SystemExit(
            "Sweep incomplete; inspect errors.jsonl and resume after resolving errors"
        )
    (args.output / "_SUCCESS").write_text(datetime.now(timezone.utc).isoformat() + "\n")


if __name__ == "__main__":
    main()
