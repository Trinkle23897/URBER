# Legality, complexity, and optimality evidence

Write

\[
G=((N+1)d+1)((M+1)d+1)=\Theta(NMd^2).
\]

## Legality and non-regression

A replay preserves the completed prefix, saves the suffix, and undoes its occupancy and row/column counts. New paths use the original geometric channel rules. An unsuccessful or longer reconstruction restores the saved suffix. Accepted moves strictly reduce total length or preserve it under the selected neutral-move rule.

The outer portfolio also retains the original pure-rule candidate. An independent verifier reconstructs every occupied grid vertex from the final paths and checks terminal coverage, unique exits, intersections, boundary visits, axis alignment, and total length. A candidate that throws or fails verification is discarded. A successful return is therefore legal and cannot be worse than a retained legal baseline.

The replay-plan key supplies an action hint. Matching the routed count and frontier does not establish equality of occupancy states and is not a global optimality argument.

## Additional replay work is O(G)

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

The bound is computed only by offline research tools. For the published benchmark, every new routing attains it, and those routings also witness that the previous 2,402 longer baseline results were nonoptimal.

## Scope of the claim

The finite benchmark covers all integer pairs in `1 <= N <= 400, 1 <= M <= floor(N/5)`, each at its recorded pitch. It does not establish optimality for arbitrary dimensions or arbitrary pitches. General optimality is currently proved only for the [high-pitch fan branch](fan-proof.md).
