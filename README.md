# URBER

Code for **URBER: Ultrafast Rule-Based Escape Routing Method for Large-Scale Sample Delivery Biochips**.

This repository contains an independent reconstruction of the published algorithm and subsequent routing experiments. It is not a recovered copy of the original paper's source code. The reconstruction follows the [paper](https://trinkle23897.github.io/pdf/URBER.pdf); the newer geometric replay method is an extension developed afterward.

## Current result

The pure geometric router reaches the independently computed minimum total wire length on **all 15,880 tested integer pairs** with

\[
1\le N\le400,\qquad 1\le M\le\lfloor N/5\rfloor.
\]

Each case keeps its original pitch `d`. The previous pure-rule portfolio reached the optimum on 13,478 cases (84.87%); geometric replay repairs the remaining 2,402 cases. Every accepted routing passes an independent geometric verifier and matches a boundary-assignment lower bound.

![Optimality before and after geometric replay](assets/optimality.png)

This is a complete sweep of the stated thin-rectangle domain, **not** the entire `400 × 400` parameter square or a theorem for arbitrary dimensions and pitches. The runtime constructor does not read benchmark answers or invoke a flow solver. Offline evaluation uses minimum-cost flow to compute independent lower bounds.

## Build and route

Requires GCC or Clang with C++17 support, Make, and Python 3.11 or later. The routing entry point uses only the Python standard library.

```sh
make -j4
python3 route.py 190 38 18 routes.json
```

Arguments are `N M d [output.json]`. The optional file contains the complete paths as lists of integer-coordinate bends, oriented from boundary to terminal. Standard output is one JSON summary, including the verified total length.

The entry point selects an explicit optimal fan when `2*d >= min(N,M)`. Otherwise it takes the shortest verified result from the previous pure-rule construction and 12 fixed replay configurations in [profiles.json](profiles.json). These parameters are independent of the input dimensions and contain no answer lookup table.

```sh
# Previous pure-rule portfolio, without replay.
python3 route.py 190 38 18 --baseline

# Published-rule reconstruction.
./build/urber 30 30 9 paper-routes.json

# Historical extensions: orientation/priority candidates, then residual repair.
./build/urber 98 51 20 --improved
./build/urber 98 51 20 --polish
```

`--polish` belongs to the separate reference executable and uses residual search. It is never called by `route.py` or either pure C++ executable.

For low-pitch inputs, `optimality_certified: false` means the runtime did not compute a certificate. The benchmark's optimality result comes from offline comparison with an independent lower bound. The high-pitch fan has a general proof and can report a certificate directly.

## Validation and reproduction

Install the optional research dependencies to run tests, recompute lower bounds, or draw plots:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
make test PYTHON=.venv/bin/python
make plot PYTHON=.venv/bin/python

# Reproduce the paper's Table II (writes results/).
.venv/bin/python -m research.experiment ii

# Audit recorded constructive witnesses on a bounded subset.
.venv/bin/python -m research.benchmark --mode witness --max-n 110 --workers 4

# Run the actual fixed-configuration entry point on every benchmark case.
.venv/bin/python -m research.benchmark --mode portfolio --workers 4
```

The last command is expensive. It evaluates the full runtime portfolio rather than stopping once an offline lower bound is met. The `witness` audit uses recorded configuration metadata only to reproduce an already reported witness; it is an offline validation mode, not the routing algorithm. Add `--check-bounds` to independently recompute the recorded bounds, or `--resume` to continue a matching checkpoint. See [benchmark methodology](docs/benchmark.md).

## Cost and guarantees

Geometric replay preserves successful later decisions while changing an earlier routing action, and allows selected equal-length moves. Its extra work and storage are bounded by `O(G)`, where `G = ((N+1)d+1)((M+1)d+1)` is the number of fine-grid vertices. Total work is `O(T_seed + G)`; this is not a proof of strict `O(NM)` when `d` varies.

The constants are substantial. In one local end-to-end measurement, `190 × 38, d=18` took about **28 seconds** with replay versus **0.16 seconds** for the previous pure rules. Those measurements are illustrative, not a portable performance guarantee.

- [Routing model and geometric replay](docs/algorithm.md)
- [Legality, complexity, and optimality evidence](docs/guarantees.md)
- [General optimality proof for the high-pitch fan](docs/fan-proof.md)
- [Complete benchmark data](benchmarks/thin_400.csv) and [summary](benchmarks/summary.json)

## Layout

| Path | Purpose |
| --- | --- |
| `route.py`, `profiles.json` | Pure geometric runtime entry point and fixed configurations |
| `src/pure/` | Standalone geometric replay and explicit fan constructors |
| `src/urber.cpp`, `src/residual_repair.hpp` | Paper reconstruction and historical residual-repair extension |
| `src/verify.hpp`, `src/routing_types.hpp` | Independent geometry checks and shared path types |
| `research/` | Offline lower bounds, paper experiments, benchmark audits, and plotting |
| `tests/` | Routing regressions, exact small-instance comparisons, and invalid-path checks |
| `benchmarks/` | Recorded results and provenance; never read by the runtime router |

Generated binaries and new experiment outputs go into ignored `build/` and `results/` directories.
