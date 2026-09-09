# Benchmark methodology and provenance

## Revised deterministic construction

The current `route.py` was evaluated on **all 160,000 ordered pairs** with
`1 <= N,M <= 400`, at the same recorded pitches as the archived reconstruction
comparison. Four disjoint shards launched 64 native constructor processes each.
Every ordered pair, including both orientations, was actually constructed.

All 160,000 outputs pass the independent geometry verifier and equal a valid
lower bound. The reconstructed paper method has 131,592 optima (82.245%); the
revised rules have 160,000 (100%). The new routing supplies a shorter verified
witness for each of the 28,408 nonoptimal paper-method outputs. The Figure 17
dimension range is 5,041/5,041 optimal, compared with the paper's approximately
91.9% reported result and the reconstruction's 4,621/5,041 (91.67%).

Pitch is fixed throughout each comparison. It comes from the existing benchmark
when available and otherwise from the reconstructed method's bisection. This
is not a claim of minimum feasible pitch or an exact reproduction of every
pitch used in Figure 17. Table II comparisons separately use its published
pitches without substitution.

The new rule was developed using counterexamples in this domain. The exhaustive
result is a verified in-domain result, not an out-of-sample guarantee. General
optimality beyond the proved high-pitch branch remains open.

- [Per-case CSV](../benchmarks/rules400/results.csv)
- [Full observations](../benchmarks/rules400/results.jsonl.gz)
- [Aggregate results](../benchmarks/rules400/summary.json)
- [Frozen source, input, binary, and artifact hashes](../benchmarks/rules400/provenance.json)
- [Corresponding 1–100 data](../benchmarks/rules100/summary.json)

No constructor receives a target length or calls the reference solver. The
runner classifies each already completed and verified construction. Each native
call uses one deterministic rule sequence. The exporter checks unique coverage,
fixed inputs, native verification, and classification, and preserves every
shard's binary hash. These observations measure solution quality; the per-case
timing fields are not isolated throughput benchmarks.

## Reproducibility

`benchmarks/rules400/results.csv` is the fixed input reference for new sweeps:
its dimensions, pitch, paper length, and independently verified optimum are read
before routing. The constructor receives only `(N,M,d)`; reference lengths are
used by the evaluator after the call returns.

The published observations and their original source hashes are preserved.
Historical fields in those records describe the original measurement environment;
retired source files are recoverable from Git history at the recorded revision.
Current commands and new run manifests use only the paper method, the revised
constructor, and the offline minimum-cost-flow reference.

See [reproduction.md](reproduction.md) for benchmark and figure commands.
