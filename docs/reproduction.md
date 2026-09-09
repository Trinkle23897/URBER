# Reproduce the methods and figures

The repository provides three methods: the paper's original-rule reconstruction,
the revised deterministic constructor, and an offline minimum-cost-flow reference.

## Build and run

```sh
make -j4
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
mkdir -p results/routes

# Exact vertex-capacitated minimum-cost flow, including path export.
.venv/bin/python -m research.experiment mcf 30 30 9 \
  --output results/routes/mcf-30x30-d9.json

# Original paper method.
./build/urber 30 30 9 results/routes/paper-30x30-d9.json

# Revised rules: one deterministic construction at the supplied pitch.
.venv/bin/python route.py 30 30 9 results/routes/single-pass-30x30-d9.json
```

MCF paths are extracted from positive flow and checked for intersections,
intermediate boundary visits, other terminals, and agreement with the objective.
The revised constructor runs without an online solver or retry loop.

## Published tables

```sh
.venv/bin/python -m research.paper --table ii --methods paper single_pass \
  --output results/table-ii.jsonl --paths-dir results/routes
.venv/bin/python -m research.paper --table ii --methods mcf \
  --output results/table-ii-mcf.jsonl
.venv/bin/python -m research.paper --table iii --methods paper \
  --output results/table-iii.jsonl
```

Use `--case N M` for one published case and `--resume` for a matching checkpoint.
Table runners call methods serially. Exact MCF and Table III can require substantial
memory and time.

The values in `benchmarks/paper/table_ii.csv` and `table_iii.csv` were transcribed
from page 11 of the [paper](https://trinkle23897.github.io/pdf/URBER.pdf#page=11).
The source metadata records the PDF hash, DOI, reported hardware, and Figure 17
experiment. Table II charts compare with the published MCF optimum. Published CPU
times and current wall times use different hardware and measurement boundaries;
they do not establish a cross-machine speedup.

The checked-in `revised_ii.jsonl` and `revised_environment.json` preserve the
measured comparison and its source hashes. Other validation jobs were active on
the devbox. `reproduced_iii.jsonl` preserves earlier original-rule reconstruction
runs; the revised method and full-grid MCF were not rerun on Table III.

## Exhaustive revised-rule sweep

Each ordered pair is constructed once at its recorded pitch. The reference
`benchmarks/rules400/results.csv` supplies fixed inputs and known optimal lengths;
lengths are used only after construction for classification. Both orientations
are executed, not filled by copying a transposed observation.

```sh
.venv/bin/python -m research.rule_sweep --max-n 400 --workers 64 \
  --output results/rules-400

# Or run disjoint shards on two hosts.
.venv/bin/python -m research.rule_sweep --max-n 400 --workers 64 \
  --shards 2 --shard 0 --output results/rules-shard0
.venv/bin/python -m research.rule_sweep --max-n 400 --workers 64 \
  --shards 2 --shard 1 --output results/rules-shard1

# Collect both shard directories on one host, then validate and export.
.venv/bin/python -m research.export_rule_sweep \
  results/rules-shard0 results/rules-shard1 --max-n 400 \
  --output results/published-rules400
```

Add `--resume` to continue with matching code, inputs, and shard settings. Each
run stores source and binary hashes, per-case observations, progress, errors, and
`_SUCCESS` only after full coverage. Python threads launch independent native
processes. The exporter verifies coverage, fixed inputs, source consistency,
native verification, and classifications before writing CSV, compressed JSONL,
summary, and provenance files.

The original published datasets and provenance remain unchanged. Their historical
source revisions can be retrieved from Git history. New manifests capture the
current runner, constructor sources, binaries, and fixed input reference directly.

## Figures and tests

The checked-in path JSONs under `benchmarks/paper/routes/` contain the actual
routes used in the README. Recreate an example and its figure with:

```sh
.venv/bin/python -m research.paper --table ii --case 30 30 \
  --methods mcf paper single_pass --paths-dir results/routes \
  --output results/example-30.jsonl
.venv/bin/python -m research.plot_routes \
  results/routes/mcf-30x30-d9.json results/routes/paper-30x30-d9.json \
  results/routes/single_pass-30x30-d9.json \
  --labels "Minimum-cost flow" "Paper method" "Revised deterministic rules" \
  --output results/routing-square.png

.venv/bin/python -m research.plot_full_sweep benchmarks/rules400/results.jsonl.gz \
  --max-n 400 --output results/optimality-rules400.png
.venv/bin/python -m research.plot_paper --results benchmarks/paper/revised_ii.jsonl \
  --output-stem results/paper-comparison

make test PYTHON=.venv/bin/python
make plot PYTHON=.venv/bin/python
```

`make plot` redraws all README figures from the checked-in data without rerunning
routing or MCF. Full maps require complete, nonoverlapping coverage by default;
`--allow-incomplete` produces an explicitly labeled progress plot.
