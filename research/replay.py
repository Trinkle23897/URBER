"""Legacy geometric replay portfolio for reproducing archived experiments."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("N", type=int)
    parser.add_argument("M", type=int)
    parser.add_argument("d", type=int)
    parser.add_argument("output", nargs="?", help="optional complete path JSON")
    parser.add_argument(
        "--baseline", action="store_true", help="use the previous pure rule portfolio"
    )
    args = parser.parse_args()
    if min(args.N, args.M, args.d) < 1:
        parser.error("N, M and d must be positive")
    exact_fan = 2 * args.d >= min(args.N, args.M)
    executable = ROOT / "build" / ("pure_fan" if exact_fan else "pure_router")
    if not executable.exists():
        parser.error("build the native helpers with: make pure-router")
    configs = [{}] if exact_fan else [{"mode": "baseline", "alpha": 110}]
    if not exact_fan and not args.baseline:
        profiles = ROOT / "profiles.json"
        if not profiles.exists():
            parser.error(
                "the geometric replay profile set has not been finalized yet; use --baseline"
            )
        configs += json.loads(profiles.read_text())["profiles"]
    n, m = max(args.N, args.M), min(args.N, args.M)
    seen, best, best_path = set(), None, None
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="urber-pure-") as temporary:
        for i, config in enumerate(configs):
            if "phase" in config:
                nn, mm = (m, n) if config["candidate"] & 2 else (n, m)
                effective = (
                    config["mode"],
                    config["alpha"],
                    config["tie"],
                    config["candidate"],
                    (config["phase"] >> 1) & 1 if mm % 2 else 0,
                    config["phase"] & 1 if nn % 2 else 0,
                )
                if effective in seen:
                    continue
                seen.add(effective)
            candidate_path = Path(temporary) / f"candidate-{i}.json"
            command = [str(executable), str(args.N), str(args.M), str(args.d)]
            if args.output:
                command.append(str(candidate_path))
            for key, value in config.items():
                command += ["--" + key, str(value)]
            result = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
            if result.returncode:
                if best is None and i == len(configs) - 1:
                    sys.stderr.write(result.stderr)
                continue
            row = json.loads(result.stdout)
            assert row["verified"] and row.get("residual_work", 0) == 0
            if best is None or row["total_length"] < best["total_length"]:
                best, best_path = row, candidate_path
                best["selected_profile"] = config
        if best is None:
            parser.error("all geometric constructions failed at this pitch")
        if args.output:
            shutil.copyfile(best_path, args.output)
    best.update(
        method="proven_fan" if exact_fan else "pure_geometric_portfolio",
        optimality_certified=exact_fan,
        polished=False,
        residual_work=0,
        selected_candidate_seconds=best.get("seconds"),
        seconds=time.monotonic() - started,
    )
    print(json.dumps(best))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
