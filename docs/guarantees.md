# Legality, complexity, and optimality evidence

Write

\[
G=((N+1)d+1)((M+1)d+1)=\Theta(NMd^2).
\]

## Current single-construction default

The default chooses one rule regime from `(N,M,d)` before constructing paths. It
has no retry budget, route restoration, residual search, or online solver.
Every successful result passes the independent geometry verifier.

Let `A=max(N,M)` and `B=min(N,M)`. The native low-pitch constructor first rejects
inputs that violate the necessary boundary-capacity inequality

\[
AB \le 2(A+B+2)d-4.
\]

For accepted inputs, its time and space are `O(G)`:

1. **Dense original-rule branch, `3d<B`.** The capacity inequality gives
   `A <= 2d(B+2)/(B-2d) = O(d)`; also `B<=A`. Each monotone channel search has at
   most `O((A+B)d)=O(d^2)` steps. There are `O(AB)` channel searches: each successful
   iteration commits a new terminal, and a failed search stops the construction.
   Repeated frontier scans are no larger. Thus this branch takes `O(ABd^2)=O(G)`.
2. **Revised branch, `B/3<=d<B/2`.** First peel any remaining strip longer than
   `2B`, constructing only its selected channel. Charge successful searches and
   commits to disjoint path vertices. Once the frontier is at most `2B` in each
   direction, at most `O(B^2)` terminals remain. Each pair of candidate searches
   takes `O((A+B)d)`, giving `O(AB^2d)=O(ABd^2)=O(G)` because `B=O(d)`.
   A failed search stops the construction and adds at most `O(G)` work.
3. **Bookkeeping.** The revised frontier moves only inward. Fenwick initialization
   and updates take `O(AB log A log B)`. Since `B-2d>=1`, the capacity inequality
   also gives `A=O(B^2)`. Therefore the logarithmic factors are bounded by `O(d^2)`.
   Central-axis reassignment takes `O(AB)`. Masks, storage, path output, and the
   vertex-by-vertex verifier require at most `O(G)` work and space.
4. **High-pitch fan, `2d>=B`.** Explicit paths have `O(AB^2)` bends and are checked
   in `O(G)` time. Since `B<=2d`, their representation also fits within `O(G)`.

At the paper's pitch scale `d=Theta(NM/(N+M))`, this is

\[
O\left(\frac{N^3M^3}{(N+M)^2}\right),
\]

the original asymptotic complexity. It is not strict `O(NM)` for variable pitch.

Termination does not depend on eventually finding an improvement. Every general
iteration either commits at least one previously unrouted terminal or returns
failure. Each channel search has an explicit `gx+gy+2` step limit. Central fans,
axis reassignment, and symmetry copies use finite loops.

## Optimality limits of the revised rules

The revised rules close known gaps such as `(105,21,10)`, `(111,27,12)`,
`(98,51,20)`, `(24,13,6)`, and `(44,33,12)`, in one construction. This does **not**
prove that they always attain the minimum length. For example, `(11,7,3)` remains
a counterexample for the current integrated rules.

Only the high-pitch fan has a general optimality proof. In the other branches,
`optimality_certified: false` means no online certificate; it does not imply a
nonoptimal result. Offline equality with a valid lower bound certifies individual
instances. The default makes no non-regression promise against the archived
replay portfolio. Historical replay rates are not rates of the revised rules.

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
