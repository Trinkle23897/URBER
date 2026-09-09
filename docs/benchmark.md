# Benchmark methodology and provenance

## Domain and objective

The checked-in [CSV](../benchmarks/thin_400.csv) contains every integer pair in

`1 <= N <= 400, 1 <= M <= floor(N/5)`.

There are exactly 15,880 canonical pairs. Transposition covers 31,760 oriented dimensions, but the reported full sweep enumerates the 15,880 canonical pairs; it is not a separate exhaustive run of both orientations or the entire `400 × 400` square.

The pitch in each row is fixed throughout comparison. These pitches came from the earlier reproduction experiments and are not claimed to be globally minimum feasible pitches. The objective is total wire length `L` at the recorded `(N,M,d)`.

## Results

| Construction | Optimal cases | Rate |
| --- | ---: | ---: |
| Paper-method reconstruction | 8,742 / 15,880 | 55.05% |
| Improved geometric replay portfolio | 15,880 / 15,880 | 100% |

The paper method was rerun on every recorded `(N,M,d)` using `build/urber`. All 15,880 outputs passed the geometry verifier; 7,138 are longer than the verified improved routing. These results are in [paper_method_thin_400.csv](../benchmarks/paper_method_thin_400.csv). This compares the reconstructed original method directly with the improved method, rather than with an intermediate portfolio.

Every improved length equals the offline boundary-assignment lower bound. The high-pitch branch handles 9,037 cases; the remaining 6,843 use the low-pitch portfolio. The standalone baseline and representative replay traces were checked against the original research implementation. These checks supplement the [fan theorem](fan-proof.md); they do not replace it.

This stress-test domain differs from the paper's `30 <= N,M <= 100` experiment. The paper's 91.9% is not a baseline percentage for this thin-rectangle domain. The published Table II and III comparisons are documented in [reproduction.md](reproduction.md).

## What is in the CSV?

Each row records dimensions, fixed pitch, final length, and the independent lower bound. The legacy `baseline_length` column preserves the intermediate portfolio for traceability; it is not the paper-method baseline. The latter is recorded separately in `paper_method_thin_400.csv`. `mode` identifies `fan`, `baseline`, `guided`, or `deep`. For replay rows, `candidate`, `phase`, `alpha`, and `tie` identify a successful configuration, and the final three columns record its work counters. Unused fields are empty.

`candidate` bit 0 selects port priority and bit 1 transposes the construction orientation. `phase` controls ownership of odd central axes. These per-case columns are **offline witness metadata**. The runtime entry point reads only the dimension-independent configurations in `profiles.json`.

The original offline sweep stopped testing a case once a candidate matched the lower bound. This is sound for evaluating the full portfolio: it contains that same verified candidate, and no legal candidate can beat a valid lower bound. The runtime does not have this stopping oracle and evaluates its fixed portfolio.

## Reproduce and audit

```sh
make -j4
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# A manageable initial audit, including the first replay regressions.
.venv/bin/python -m research.benchmark --mode witness --max-n 110 --workers 4

# Regenerate each recorded witness, including the full baseline where applicable.
.venv/bin/python -m research.benchmark --mode witness --workers 4

# Run the public entry point, with no per-case configuration hints.
.venv/bin/python -m research.benchmark --mode portfolio --workers 4

# Independently recompute bounds as well as reconstructing the witnesses.
.venv/bin/python -m research.benchmark --mode witness --check-bounds --workers 4

# Reproduce the paper-method reference on the same fixed inputs.
.venv/bin/python -m research.benchmark --mode paper --workers 32

# Redraw the figures from the checked-in data.
make plot PYTHON=.venv/bin/python
```

The audit writes new JSONL results under `results/`; it does not change the checked-in CSV. Full scans, especially the runtime portfolio, can take many hours. Use `--max-n` to bound a run and `--workers` to control CPU and memory use. Add `--resume` to continue a checkpoint with matching binaries, data, and audit settings; otherwise choose a new `--output` path. Bound-recomputation runs use a separate default filename. The constructor subprocess receives only dimensions and routing configuration, never a lower bound or target length.

The replay audit compares recorded search counters as well as lengths. Geometry verification is performed by the native executable before it returns success. The optional independent bound check uses [research/bounds.py](../research/bounds.py), a reflection-folded boundary assignment solver.

## Provenance and limitations

The improved-method experiments were completed on September 8, 2026, on a local Apple Silicon machine. The direct paper-method comparison was added on September 9, 2026 (UTC). The public repository reorganizes the standalone implementation without changing the routing rules. [provenance.json](../benchmarks/provenance.json) records hashes of the original source and raw full-sweep results before packaging. [summary.json](../benchmarks/summary.json), [profile_validation.json](../benchmarks/profile_validation.json), and [smoke.json](../benchmarks/smoke.json) preserve the reported aggregate, representative trace checks, and end-to-end measurements.

Early sweep rows used the equivalent research constructor; later rows used the standalone constructor with a cached frontier and a hard replay guard. Representative checks matched exact lengths and work counters. All recorded winning traces are below the guard threshold. The per-case work counters are not complete instruction counts or portable timing measurements.

The parameter portfolio was selected using this benchmark. A 100% result on this finite domain is not an out-of-sample guarantee. General optimality outside the high-pitch theorem remains unproved. See [guarantees.md](guarantees.md) for the precise complexity and optimality claims.
