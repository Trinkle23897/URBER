# Benchmark methodology and provenance

These archived experiments evaluate the **legacy replay portfolio** (`python -m research.replay`), not the current single-construction `route.py`. Its published 99.75625% rate must not be attributed to the current default.

## Complete square: 1 <= N,M <= 400

The September 9, 2026 experiment covers **all 160,000 ordered pairs**. Each orientation was actually constructed; no rows were filled by copying the transposed result. The objective is minimum total wire length `L` at the recorded fixed `(N,M,d)`.

For each canonical dimension pair, pitch comes from the existing thin-rectangle or published-table benchmarks when available. Otherwise the reconstructed paper method chooses pitch by bisection. Both orientations and both methods use that same pitch. This policy does not establish minimum feasible pitch, and the 30–100 subset is not an exact reproduction of the paper's Figure 17 pitch choices.

| Method | Proven optimal | Proven nonoptimal | Unknown |
|---|---:|---:|---:|
| Paper-method reconstruction | 131,592 (82.245%) | 28,063 | 345 |
| Improved geometric method | 159,610 (99.75625%) | 0 | 390 |

All 320,000 method outputs are geometrically verified. The improved result is shorter than the paper-method result in 28,063 cases, equal in 131,937, and never longer. In the 5,041-case 30–100 dimension subset, the reconstruction has 4,621 proven optima (91.67%) and the improved method has 4,997 (99.13%), with 44 unknown improved results. The original paper reports approximately 91.9%; different pitch selection and reconstruction details prevent treating these as identical experiments.

Optimal means equality with a valid lower bound: the proved fan construction at high pitch, or the boundary-assignment relaxation at lower pitch. Nonoptimal requires a shorter verified witness. A positive gap alone is **unknown**. The improved method's maximum gap is 68 at `(13,24,6)` and `(24,13,6)`; the 30–100 subset's maximum is 4. Exhaustive coverage does not prove universal optimality.

### Artifacts and provenance

- [results.csv](../benchmarks/full400/results.csv): dimensions, pitch, lower bound, both lengths, gaps, classifications, and pitch/bound sources.
- [results.jsonl.gz](../benchmarks/full400/results.jsonl.gz): losslessly compressed merged observations, including selected configurations, work counters, and native verification flags.
- [summary.json](../benchmarks/full400/summary.json): full-square, 30–100, and thin-rectangle subset results.
- [provenance.json](../benchmarks/full400/provenance.json): source revision, input hashes, artifact hashes, worker settings, and platform metadata, without private host names or absolute paths.

The run used source revision `4af3e2d29b1cdd85af0c7255b394c2f8e450cdbf`; earlier runner revisions differed only in progress reporting and scheduling, with unchanged native routing sources and candidate semantics. Completed and partial shard/helper snapshots were merged after checking coverage and agreement of **3,491 repeated observations**. Repeats had to agree on pitch, bound, both lengths, and both classifications; no favorable result was selected from conflicting observations. Full-grid MCF was not run for every case.

Offline early stopping and speculative candidate parallelism preserve the fixed portfolio's minimum length. The native constructor receives neither the lower bound nor a target answer. The raw `seconds` fields describe individual selected native calls, not total portfolio or sweep runtime; rejected candidates can dominate total work. The run is evidence about solution quality, not a cross-hardware speed comparison. [Reproduction commands](reproduction.md#reproduce-the-published-full-square-artifacts).

## Earlier thin-rectangle test

### Domain and objective

The checked-in [CSV](../benchmarks/thin_400.csv) contains every integer pair in

`1 <= N <= 400, 1 <= M <= floor(N/5)`.

There are exactly 15,880 canonical pairs. Transposition covers 31,760 oriented dimensions, but the earlier thin-rectangle sweep enumerates the 15,880 canonical pairs; it is not a separate exhaustive run of both orientations or the entire `400 × 400` square.

The pitch in each row is fixed throughout comparison. These pitches came from the earlier reproduction experiments and are not claimed to be globally minimum feasible pitches. The objective is total wire length `L` at the recorded `(N,M,d)`.

### Results

| Construction | Optimal cases | Rate |
| --- | ---: | ---: |
| Paper-method reconstruction | 8,742 / 15,880 | 55.05% |
| Improved geometric replay portfolio | 15,880 / 15,880 | 100% |

The paper method was rerun on every recorded `(N,M,d)` using `build/urber`. All 15,880 outputs passed the geometry verifier; 7,138 are longer than the verified improved routing. These results are in [paper_method_thin_400.csv](../benchmarks/paper_method_thin_400.csv). This compares the reconstructed original method directly with the improved method, rather than with an intermediate portfolio.

Every improved length equals the offline boundary-assignment lower bound. The high-pitch branch handles 9,037 cases; the remaining 6,843 use the low-pitch portfolio. The standalone baseline and representative replay traces were checked against the original research implementation. These checks supplement the [fan theorem](fan-proof.md); they do not replace it.

This stress-test domain differs from the paper's `30 <= N,M <= 100` experiment. The paper's 91.9% is not a baseline percentage for this thin-rectangle domain. The published Table II and III comparisons are documented in [reproduction.md](reproduction.md).

### What is in the earlier CSV?

Each row records dimensions, fixed pitch, final length, and the independent lower bound. The legacy `baseline_length` column preserves the intermediate portfolio for traceability; it is not the paper-method baseline. The latter is recorded separately in `paper_method_thin_400.csv`. `mode` identifies `fan`, `baseline`, `guided`, or `deep`. For replay rows, `candidate`, `phase`, `alpha`, and `tie` identify a successful configuration, and the final three columns record its work counters. Unused fields are empty.

`candidate` bit 0 selects port priority and bit 1 transposes the construction orientation. `phase` controls ownership of odd central axes. These per-case columns are **offline witness metadata**. The legacy replay entry point reads only the dimension-independent configurations in `profiles.json`.

The original offline sweep stopped testing a case once a candidate matched the lower bound. This is sound for evaluating the full portfolio: it contains that same verified candidate, and no legal candidate can beat a valid lower bound. The runtime does not have this stopping oracle and evaluates its fixed portfolio.

### Reproduce and audit the earlier dataset

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

### Earlier provenance and limitations

The improved-method experiments were completed on September 8, 2026, on a local Apple Silicon machine. The direct paper-method comparison was added on September 9, 2026 (UTC). The public repository reorganizes the standalone implementation without changing the routing rules. [provenance.json](../benchmarks/provenance.json) records hashes of the original source and raw full-sweep results before packaging. [summary.json](../benchmarks/summary.json), [profile_validation.json](../benchmarks/profile_validation.json), and [smoke.json](../benchmarks/smoke.json) preserve the reported aggregate, representative trace checks, and end-to-end measurements.

Early sweep rows used the equivalent research constructor; later rows used the standalone constructor with a cached frontier and a hard replay guard. Representative checks matched exact lengths and work counters. All recorded winning traces are below the guard threshold. The per-case work counters are not complete instruction counts or portable timing measurements.

The parameter portfolio was selected using this benchmark. A 100% result on this finite domain is not an out-of-sample guarantee. General optimality outside the high-pitch theorem remains unproved. See [guarantees.md](guarantees.md) for the precise complexity and optimality claims.
