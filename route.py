"""Single-construction routing at a fixed pitch, without replay or retries."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def construct(n, m, d, output=None):
    """Choose a branch from the dimensions, then invoke it exactly once."""
    if min(n, m, d) < 1:
        raise ValueError("N, M and d must be positive")
    exact_fan = 2 * d >= min(n, m)
    executable = ROOT / "build" / ("pure_fan" if exact_fan else "urber")
    command = [str(executable), str(n), str(m), str(d)]
    if output is not None:
        command.append(str(output))
    started = time.monotonic()
    process = subprocess.run(command, capture_output=True, text=True, check=True)
    result = json.loads(process.stdout)
    if not result.get("verified"):
        raise RuntimeError("construction did not pass geometry verification")
    result.update(
        method="proven_fan" if exact_fan else "paper_single_pass",
        optimality_certified=exact_fan,
        polished=False,
        residual_work=0,
        constructor_seconds=result.get("seconds"),
        seconds=time.monotonic() - started,
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("N", type=int)
    parser.add_argument("M", type=int)
    parser.add_argument("d", type=int)
    parser.add_argument("output", nargs="?", help="optional complete path JSON")
    args = parser.parse_args()
    try:
        result = construct(args.N, args.M, args.d, args.output)
    except subprocess.CalledProcessError as error:
        sys.stdout.write(error.stdout or "")
        sys.stderr.write(error.stderr or "")
        return error.returncode
    except FileNotFoundError:
        parser.error("build the native constructors with: make")
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
