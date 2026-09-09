# Reproduce the paper comparisons and figures

## Published data and measurement boundaries

The values in `benchmarks/paper/table_ii.csv` and `table_iii.csv` were transcribed from page 11 of the [paper](https://trinkle23897.github.io/pdf/URBER.pdf#page=11). The source metadata includes the PDF hash, DOI, reported hardware, and the separate 30–100 sweep described on page 12. No paper screenshot is needed to rebuild the charts.

`reproduced_ii.jsonl` contains fresh serial calls of the original-rule reconstruction and the geometric method at every listed Table II pitch. Wall time includes subprocess startup and verification. `reproduced_iii.jsonl` preserves earlier runs of the byte-identical original-rule C++ source; its times are the executable's internal times, not newly measured wall times. The geometric method and full-grid MCF were not rerun on Table III.

The Table II quality chart subtracts the **published MCF optimum**, not an intermediate heuristic result. Its timing panels keep the paper's CPU measurements separate from current measurements. Neither panel establishes a cross-machine speedup.

## Individual methods

```sh
make -j4
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
mkdir -p results/routes

# Exact vertex-capacitated minimum-cost flow, including path export.
.venv/bin/python -m research.experiment mcf 30 30 9 \
  --output results/routes/mcf-30x30-d9.json

# Original-rule reconstruction.
./build/urber 30 30 9 results/routes/paper-30x30-d9.json

# Improved geometric construction; no online flow solver.
.venv/bin/python route.py 30 30 9 results/routes/geometric-30x30-d9.json
```

The MCF implementation uses unit vertex capacities and directed unit-cost grid moves, with source supplies at terminals and distinct boundary sinks. Exported paths are extracted from positive flow and checked for intersections, intermediate boundary visits, other terminals, and agreement with the optimal objective.

## Complete published tables

```sh
.venv/bin/python -m research.paper --table ii --methods paper geometric \
  --output results/table-ii.jsonl
.venv/bin/python -m research.paper --table ii --methods mcf \
  --output results/table-ii-mcf.jsonl
.venv/bin/python -m research.paper --table iii --methods paper \
  --output results/table-iii.jsonl
```

Runs are serial so the measured methods do not compete with each other. Use `--resume` to continue a matching checkpoint. The exact MCF graph and Table III routing grids can be large; their costs are not represented by the quick unit tests.

## Routing examples

The repository includes the actual path JSON used in the README under `benchmarks/paper/routes/`. To regenerate those paths from the algorithms:

```sh
.venv/bin/python -m research.paper --table ii --case 30 30 \
  --methods mcf paper geometric --paths-dir results/routes \
  --output results/example-30.jsonl
.venv/bin/python -m research.paper --table ii --case 72 13 \
  --methods mcf paper geometric --paths-dir results/routes \
  --output results/example-72.jsonl

.venv/bin/python -m research.plot_routes \
  results/routes/mcf-30x30-d9.json results/routes/paper-30x30-d9.json \
  results/routes/geometric-30x30-d9.json \
  --labels "Minimum-cost flow" "Paper method" "Geometric replay" \
  --output results/routing-square.png
```

Substitute `72x13-d6` to draw the rectangular example. `make plot` redraws every README figure from the checked-in published data, measurements, and paths, without rerunning expensive solvers.

## Dense optimality maps

To reconstruct the original paper method on the completed thin-rectangle dataset and compare it with the final geometric results:

```sh
.venv/bin/python -m research.benchmark --mode paper --workers 8 \
  --output results/paper-thin-400.jsonl
.venv/bin/python -m research.plot_benchmark \
  --paper-results results/paper-thin-400.jsonl
```

To run **all 160,000 ordered pairs**, use the full-square runner:

```sh
.venv/bin/python -m research.full_sweep --max-n 400 --workers 32 \
  --output results/full-400
```

Workers use separate processes so a native solver holding Python's interpreter lock cannot serialize the sweep. Set the worker count to the CPU and memory capacity available on each host.

For two machines, run disjoint shards:

```sh
# Host A
.venv/bin/python -m research.full_sweep --max-n 400 --workers 32 \
  --shards 2 --shard 0 --output results/full-400-shard0
# Host B
.venv/bin/python -m research.full_sweep --max-n 400 --workers 32 \
  --shards 2 --shard 1 --output results/full-400-shard1
```

Keep each run in a persistent session. Each directory contains `run.json`, `results.jsonl`, `progress.json`, `errors.jsonl`, and, only after successful completion of its assigned domain, `_SUCCESS`. Resume with identical code and settings plus `--resume`; the worker count may change. An error or unfinished case is not counted as a completed optimal result.

For each unordered dimension pair, the runner retains an existing benchmark pitch if present; otherwise it uses the canonical paper reconstruction's bisection result. This is a heuristic pitch policy, not a minimum-feasibility theorem. Both orientations use that same pitch. The lower bound can be shared by symmetry, but both ordered orientations are actually constructed and verified.

Offline evaluation tries candidates from the fixed runtime portfolio and may stop once one reaches a proved lower bound. It sends no target length to the constructor. This certifies the portfolio's minimum without needlessly running its remaining candidates. If no candidate reaches the bound, all candidates are tried. A positive lower-bound gap alone is labeled `unknown`; `nonoptimal` requires a shorter verified witness.

After collecting both shard files:

```sh
.venv/bin/python -m research.plot_full_sweep \
  results/full-400-shard0/results.jsonl results/full-400-shard1/results.jsonl \
  --max-n 400 --output results/optimality-full400.png
```

The full-square plot requires complete, nonoverlapping coverage by default. Use `--allow-incomplete` only for an explicitly labeled progress plot. The checked-in full-square map covers all 160,000 cases. The earlier thin-rectangle figure covers only its stated subset.


## Reproduce the published full-square artifacts

The completed September 9, 2026 run is stored under `benchmarks/full400/`. Redraw its map without rerunning routing:

```sh
.venv/bin/python -m research.plot_full_sweep benchmarks/full400/results.jsonl.gz \
  --max-n 400 --output results/optimality-full400.png
```

To publish a new complete sweep, first merge its original and helper snapshots. The following example uses two disjoint shards; include all helper inputs when applicable:

```sh
.venv/bin/python -m research.merge_sweep results/full-400-shard0 results/full-400-shard1 \
  --max-n 400 --output results/merged-full400
.venv/bin/python -m research.export_sweep results/merged-full400 \
  --output results/published-full400 --source-commit "$(git rev-parse HEAD)"
```

The exporter requires complete unique coverage and verified witnesses, checks lower-bound classifications, and writes CSV, losslessly compressed full observations, aggregate results, and provenance with input/artifact hashes. Keep the raw snapshots for provenance audits. `seconds` within a geometric observation measures its **selected native candidate**, not all candidates, bound computation, or end-to-end portfolio time. These files are a solution-quality benchmark, not a portable runtime comparison. Difficult replay candidates can take hours even when the selected routing was a fast baseline.

## Rebalance pending cases

An explicit JSON list such as `[[400, 399], [400, 398]]` can assign pending canonical pairs to another worker pool. `--pairs` preserves the list's order, evaluates both orientations, and records the list's hash for safe resumption. It cannot be combined with `--shards`.

```sh
.venv/bin/python -m research.full_sweep --max-n 400 --workers 64 \
  --pairs pending.json --output results/helper
```

When only expensive pairs remain, parallelize their native candidate calls as
well. For example, eight pair workers with eight candidates each use at most
64 concurrent native calls:

```sh
.venv/bin/python -m research.full_sweep --max-n 400 --workers 8 \
  --candidate-workers 8 --pairs pending.json --output results/tail-helper
```

Candidate results are consumed in the same order as the sequential evaluation,
including tie handling, lower-bound early stopping, and the preferred candidate
for the transposed case. Speculative calls may do extra work after an earlier
candidate reaches the bound; their results do not change the selected routing
or the reported trial count. This option accelerates offline evaluation without
changing the routing algorithm. Budget the product of both worker counts against
available CPU and memory, and keep existing long-running jobs until combined
coverage is verified.

Helpers can run while an original shard continues its long-running cases. Do not sum their counters: repeated observations can overlap. Collect stable result snapshots and merge only after the union covers the entire intended domain:

```sh
.venv/bin/python -m research.merge_sweep results/original-shard2 results/helper-a results/helper-b \
  --max-n 400 --shards 6 --shard 2 --output results/merged-shard2
```

The merge verifies dimensions, pitch, bounds, and statuses; repeated observations must agree on pitch, bound, both lengths, and both statuses. It rejects missing cases and disagreements, retains input hashes and run provenance, and writes `_SUCCESS` only for complete combined coverage. Original inputs may be partial because the helper observations fill the missing cases. Keep active original work until all its assigned cases are covered by verified results.
