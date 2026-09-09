# Legality, complexity, and optimality evidence

Write

\[
G=((N+1)d+1)((M+1)d+1)=\Theta(NMd^2).
\]

## Current single-construction default

`route.py` selects its branch before construction and invokes one native executable. Below the fan threshold, it executes the unchanged original rules, including their verification. There is no replay or additional search complexity. Above the threshold, the explicit fan emits at most `O(NM min(N,M))` bends; since `min(N,M) <= 2d`, this is `O(G)`. The independent vertex-by-vertex verifier costs `O(G)` time and space. At the paper's pitch scale `d=Theta(NM/(N+M))`, the grid cost is `O(N^3 M^3/(N+M)^2)`. For arbitrary supplied pitch, keep the dependence on `d`; do not claim strict `O(NM)`.

The paper-rule construction terminates without a retry budget: every successful iteration of `general` commits at least one previously unrouted terminal, or returns failure. There are at most `NM` such commits. Its channel search is bounded by `gx+gy+2` steps, and its central-row and symmetry loops are finite. The fan uses explicit finite loops. Successful results pass the geometry verifier; failed construction is returned to the caller without fallback.

The current default makes **no non-regression promise against the archived replay portfolio**. It matches the paper reconstruction below the threshold. On Table II it matches eight published MCF optima; the known gaps at `(111,27,12)` and `(98,51,20)` remain four units. The general optimality theorem covers only the high-pitch fan.

## Legacy replay: legality and non-regression

A replay preserves the completed prefix, saves the suffix, and undoes its occupancy and row/column counts. New paths use the original geometric channel rules. An unsuccessful or longer reconstruction restores the saved suffix. Accepted moves strictly reduce total length or preserve it under the selected neutral-move rule.

The outer portfolio also retains the original pure-rule candidate. An independent verifier reconstructs every occupied grid vertex from the final paths and checks terminal coverage, unique exits, intersections, boundary visits, axis alignment, and total length. A candidate that throws or fails verification is discarded. A successful return is therefore legal and cannot be worse than a retained legal baseline.

The replay-plan key supplies an action hint. Matching the routed count and frontier does not establish equality of occupancy states and is not a global optimality argument.

## Legacy replay: additional work is O(G)

For the `guided` and `deep` branches, the pass counts, trial caps, number of quadrants, and number of parameter configurations are constants independent of `N` and `M`.

1. Forward channel searches, commits, and undo operations contribute to the weighted-visit counter. A soft budget stops subsequent trial batches. During a replay, a hard guard at each channel-search entry limits work to the soft threshold plus `4096*G`. One final monotone search or commit visits at most `O(G)` vertices. Restoring a valid saved suffix also costs `O(G)`.
2. A legal path set is vertex-disjoint, so its paths and bends occupy at most `O(G)` space. Copying, comparing, or restoring a snapshot or suffix is `O(G)`, and the number of such operations is capped independently of the input dimensions.
3. Replay plans contain `O(NM)` entries. Scanning their decisions a fixed number of times is `O(NM)`, hence `O(G)`.
4. The cached outermost unfinished row and column move only inward during a forward phase. Undo raises the frontier using the restored terminal. Scanning is amortized `O(N+M)` per forward phase, with `O(1)` frontier updates per undone path.
5. Initialization, masks, and independent verification use at most `O(G)` work and space per fixed candidate.

Thus the **additional replay layer** uses `O(G)` time and space. If the seed construction takes `T_seed`, the complete fixed portfolio takes `O(T_seed + G)` time. This adds substantial constants even though it does not introduce a new asymptotic factor over an implementation that already allocates and checks the fine grid.

This does not independently re-prove every step of the paper's seed complexity. Conditional on its `O(G)` seed bound and the pitch scale `d=O(NM/(N+M))`, replay preserves

\[
O\left(\frac{N^3M^3}{(N+M)^2}\right).
\]

It is not a proof of strict `O(NM)` for variable pitch.

## Per-instance optimality

Every legal routing induces an assignment of terminals to distinct boundary exits. A path's length is at least the Manhattan distance between its endpoints. Relaxing interior nonintersection therefore gives a lower bound: the minimum-cost boundary assignment.

If a geometrically verified routing has length equal to that independent lower bound, it is globally optimal for that instance, including comparison against nonmonotone routings. A positive gap to this lower bound alone does not prove nonoptimality; a shorter legal routing would be needed for that conclusion.

The bound is computed only by offline research tools. In the archived thin-rectangle replay benchmark, every replay routing attains it. The archived full-square run has 390 replay cases with an unresolved lower-bound gap.

## Scope of the claim

The archived replay experiments cover the thin-rectangle domain and the full `1 <= N,M <= 400` square, each at its recorded pitch. Their rates do not describe the current single-construction default. Finite benchmarks do not establish optimality for arbitrary dimensions or arbitrary pitches. General optimality is currently proved only for the [high-pitch fan branch](fan-proof.md).
