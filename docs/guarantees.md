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
   Unsuccessful corner queries obey the same step bound. A failed selected
   strip query stops the construction and adds at most `O(G)` work.
   Projection scoring examines at most `O(B^2)` terminals per decision. Each
   one-dimensional matching cost uses integer bucket isotonic regression in
   `O(B^2+Bd)` time: sorted projections advance the bucket maximum by at most
   `O(Bd)` in total, and its downward moves are charged to those advances.
   The middle-row rule evaluates at most three such assignments, a constant.
   Across `O(B^2)` decisions this is `O(B^4)`, bounded by `O(ABd^2)=O(G)`.
   The paired-channel branch commits at most two channels per iteration.
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

## One-dimensional projection cost

Fix a set of `k` terminals assigned to one boundary with available ports
`1,...,t`. Sort their projected coordinates as `p_1 <= ... <= p_k`. An uncrossing
exchange for absolute distance shows that some minimum-cost assignment has
strictly increasing exit coordinates `s_1 < ... < s_k`.

Set `z_i=s_i-i` and `a_i=p_i-i`. The horizontal or vertical displacement is

```
min sum |a_i-z_i|, subject to 0 <= z_1 <= ... <= z_k <= t-k.
```

This is bounded integer L1 isotonic regression. Clamp each `a_i` to `[0,t-k]`,
add its clamping distance, and apply the max-heap slope update: insert the new
value twice, remove the maximum, and add the removed value minus the new value.
The implementation merges the equal-value case and stores the heap as integer
bucket counts. Sorted terminal projections ensure that the total positive
movement of `a_i` is at most the largest projection; the maximum-bucket pointer's
movement is therefore linear in the number of terminals plus that projection.
If `k>t`, the assignment is infeasible.

This computes the exact cost for the **fixed boundary assignment**. It does not
prove that this assignment, or the resulting two-dimensional routing, is globally
optimal. The external benchmark bound is computed independently.

## Optimality limits of the revised rules

The complete fixed-pitch domain `1 <= N,M <= 400` contains 160,000 independently
verified constructions, all matching valid lower bounds. This certifies every
instance in the published dataset.

The revised rules close known gaps such as `(105,21,10)`, `(111,27,12)`,
`(98,51,20)`, `(24,13,6)`, and `(44,33,12)`, in one construction. This does **not**
prove that they always attain the minimum length. Former counterexamples,
including `(19,9,4)`, `(35,15,7)`, `(37,15,7)`, and `(43,17,8)`, now attain the
independently computed optimum. A finite exhaustive domain is still distinct
from a theorem for arbitrary dimensions and pitches.

Only the high-pitch fan has a general optimality proof. In the other branches,
`optimality_certified: false` means no online certificate; it does not imply a
nonoptimal result. Offline equality with a valid lower bound certifies individual
instances.

## Per-instance optimality

Every legal routing induces an assignment of terminals to distinct boundary exits. A path's length is at least the Manhattan distance between its endpoints. Relaxing interior nonintersection therefore gives a lower bound: the minimum-cost boundary assignment.

If a geometrically verified routing has length equal to that independent lower bound, it is globally optimal for that instance, including comparison against nonmonotone routings. Equivalently,

\[
L_{\mathrm{assignment}} \le L_{\mathrm{opt}} \le L_{\mathrm{constructed}} = L_{\mathrm{assignment}},
\]

so all three quantities are equal. A positive gap to this lower bound alone does not prove nonoptimality; a shorter legal routing would be needed for that conclusion.

The bound is computed only by offline research tools. Every recorded revised-rule routing in the complete 1–400 benchmark attains its independent lower bound.

## Scope of the claim

The revised rules cover the full `1 <= N,M <= 400` square at the recorded pitches.
Finite benchmarks do not establish optimality for arbitrary dimensions or pitches.
General optimality is currently proved only for the [high-pitch fan branch](fan-proof.md).
