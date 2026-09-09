# Routing model and construction methods

There are `N × M` terminals at `(i*d, j*d)`, for `1 <= i <= N` and `1 <= j <= M`. The rectangular boundary is at `x=0`, `x=(N+1)d`, `y=0`, and `y=(M+1)d`.

Every terminal needs one axis-aligned grid path to a distinct boundary vertex. Paths must be vertex-disjoint, cannot pass through another terminal, and cannot touch the boundary except at their own exit. The objective is to minimize the sum of path lengths **at fixed pitch `d`**. Choosing a smaller feasible pitch is a separate problem. The paper's empirical pitch formula and the research script's heuristic pitch search do not prove a minimum feasible pitch.

The comparison problem permits nonmonotone paths. The pure constructors emit monotone paths; matching a valid lower bound still proves optimality against the larger feasible set.

## Current deterministic rules

The constructor uses `A=max(N,M)`, `B=min(N,M)` and transposes exported paths back
into the requested orientation. It chooses its rule regime before routing:

- `2*d >= B`: the explicit, proved-optimal [fan construction](fan-proof.md).
- `3*d < B`: the original reconstructed rules in canonical orientation.
- Otherwise: the revised central assignment and boundary-choice rules below.

`route.py` invokes exactly one native constructor. There is no reconstruction,
parameter portfolio, residual repair, online oracle, or pitch adjustment. A failed
construction returns an error. Timing fields vary; the paths are deterministic.

### Central assignment

On an odd horizontal middle axis, alternate quadrant ownership with phase
`floor(A/2) mod 2`, so the innermost axis terminal aligns with the adjacent central
column. Retain the paper's vertical-axis and center ownership rules.

For an odd `B` with `3*A >= 4*B`, cap the initial horizontal central fan at

```
C = floor((A + 1 + [A mod 4 = 3])/3)       if B = 2*d + 1
C = floor(A/2) - [A is even]              otherwise.
```

The actual cap is also limited to `2*d-1`. In other cases retain `floor(A/2)`.
After the central fans, assign the remaining horizontal-axis terminals from the
inside outward, alternating quadrant ownership and reflecting through the center.
When an odd number remains, start with the opposite-quadrant pair that has more
unused boundary capacity after accounting for its non-axis terminals.

These are construction rules supported by the recorded experiments, not a general
optimality theorem. In particular, a shorter central fan does not by itself prove
that the remaining routing can be completed optimally.

### Boundary choice

Let `(t_x,t_y)` be the available bottom/left boundary prefixes in a quadrant, and
let `P` contain its unrouted terminals. The two candidate channels have endpoints
`p_x,p_y` and lengths `l_x,l_y`. Use the relaxed distance estimate

```
c((x,y), a,b) = min(y + max(0,x-a), x + max(0,y-b)).
```

When the original boundary-priority rule permits either direction, compare

```
S_x = l_x + sum(c(p,t_x-1,t_y) for p in P except p_x)
S_y = l_y + sum(c(p,t_x,t_y-1) for p in P except p_y).
```

Choose the smaller score; break ties by channel length, then by available prefix
length. Commit one channel. The estimate accounts for the remaining terminals but
relaxes shared exits and internal intersections; it is not an exact future cost.
Two-dimensional Fenwick counts compute the score difference without rescanning
all terminals. The shared part of the two sums cancels.

The original row/column fan rules still apply. A long remaining strip is peeled
in its long direction using only the selected channel. Comparing two channels is
restricted to a corner with at most `2*B` rows and columns. This restriction, cached
frontiers, and disjoint committed paths give the original asymptotic work bound;
see [guarantees.md](guarantees.md).

## Legacy replay dispatch

The archived `python -m research.replay` entry point uses the same high-pitch fan. Otherwise, it retains the previous pure-rule portfolio and tries 12 fixed configurations of geometric replay. Each configuration specifies an orientation, odd-axis ownership phase, boundary-priority rule, replay depth, and preferred equal-length action. `profiles.json` contains only those parameters. It does not map dimensions to paths or optimal lengths.

## Guided replay

The construction starts with the original central-axis assignment and four routing quadrants. Before each action, it records the number of completed paths, the outermost unfinished row and column, and the next available boundary ports.

An action routes one channel toward either boundary, or finishes the current row or column. Replay changes an earlier action, removes the affected suffix, and reconstructs that suffix with the usual geometric occupancy checks.

A shorter complete reconstruction is accepted. Selected equal-length moves are also accepted: they can expose a later improvement without making the incumbent longer.

The crucial change is to **retain successful later decisions**. Rebuilding every suffix greedily can erase earlier improvements and make a useful change appear unprofitable. A replay plan records the incumbent's explicit actions and reuses a hint when the routed-path count and outermost unfinished row/column match again.

That match is only a heuristic. It does not imply identical occupied vertices. Paths are always reconstructed and the final routing is independently verified.

## Fixed effort limits

- `guided`: two passes and a soft budget of `256*G` weighted visits per quadrant.
- `deep`: eight passes and a soft budget of `1024*G` weighted visits per quadrant.
- Both use a fixed cap of 16,384 trials per quadrant, with at most a small action-batch overshoot.
- A hard guard stops an unexpectedly long replay between channel searches; restoration retains the previous valid suffix.

Weighted visits measure selected grid operations, not every machine instruction. The separate fixed attempt cap bounds copying and bookkeeping. Cached unfinished-row/column frontiers avoid rescanning the long dimension for every path.

The result is a bounded heuristic, not an unbounded search for a certificate. Failure to find a better move does not prove global optimality.
