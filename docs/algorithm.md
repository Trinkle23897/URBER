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
C = 1                                   if B - 2*d < 10
C = floor(A/2) - [A is even]              otherwise.
```

The actual cap is also limited to `2*d-1`. In other cases retain `floor(A/2)`.
The short fan leaves the remaining middle-axis terminals for the later boundary
allocation instead of committing their exits before surrounding demand is known.
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

Let `(n_x,n_y)` be the outermost unrouted column and row. If the original
boundary-priority direction disagrees with the sign of
`t_x*n_y - t_y*n_x`, allow either direction. Retain the original priority if
its candidate first reaches an interior column/row: that channel is still
clearing access to the frontier. When both candidates end on the local middle
row `y=floor((B+1)/2)*d`, compare their projected costs even if the original
priority preferred one direction. A row/column batch starts only when its first
terminal is available.

For `B-2*d >= 10`, retain the original shortest-channel rule and its optional
second commit, after the revised central assignment. If only one candidate
channel exists, use it. Otherwise the following single-commit rule applies.

For `3*A >= 4*B`, first assign each pending terminal to the cheaper boundary
under `c` at the current prefixes; ties choose the bottom boundary when `x>y`.
Keep this partition fixed while comparing both candidates. Remove the candidate's
terminal, add its actual channel length, and compute the minimum total distance
from each remaining group to distinct ports on its boundary. This last problem
is one-dimensional ordered matching, evaluated by integer bucket L1 isotonic
regression. If both candidates end on the middle row, also evaluate the two
alternating assignments of equidistant terminals: odd `x/d` to bottom, or even
`x/d` to bottom. For each candidate take the smallest of these three analytical
projection costs, then choose the candidate with smaller cost. These calculations
do not construct or undo routes; exactly one candidate channel is committed.

On a tie, or for `3*A < 4*B`, compare the independent-distance scores

```
S_x = l_x + sum(c(p,t_x-1,t_y) for p in P except p_x)
S_y = l_y + sum(c(p,t_x,t_y-1) for p in P except p_y).
```

Break remaining ties by channel length, then by available prefix length. Commit
one channel. The projection score respects distinct ports within each boundary
group, but relaxes interior intersections and fixes the boundary assignment;
it is not an exact future routing cost. Two-dimensional Fenwick counts evaluate
the independent-distance score difference without rescanning all terminals.

The original row/column fan rules still apply. A long remaining strip is peeled
in its long direction using only the selected channel. Comparing two channels is
restricted to a corner with at most `2*B` rows and columns. This restriction, cached
frontiers, and disjoint committed paths give the original asymptotic work bound;
see [guarantees.md](guarantees.md).
