# Routing model and geometric replay

There are `N × M` terminals at `(i*d, j*d)`, for `1 <= i <= N` and `1 <= j <= M`. The rectangular boundary is at `x=0`, `x=(N+1)d`, `y=0`, and `y=(M+1)d`.

Every terminal needs one axis-aligned grid path to a distinct boundary vertex. Paths must be vertex-disjoint, cannot pass through another terminal, and cannot touch the boundary except at their own exit. The objective is to minimize the sum of path lengths **at fixed pitch `d`**. Choosing a smaller feasible pitch is a separate problem. The paper's empirical pitch formula and the research script's heuristic pitch search do not prove a minimum feasible pitch.

The comparison problem permits nonmonotone paths. The pure constructors emit monotone paths; matching a valid lower bound still proves optimality against the larger feasible set.

## Runtime dispatch

For `2*d >= min(N,M)`, an explicit fan construction attains a proved optimum. It is described in [fan-proof.md](fan-proof.md).

Otherwise, the router retains the previous pure-rule portfolio and tries 12 fixed configurations of geometric replay. Each configuration specifies an orientation, odd-axis ownership phase, boundary-priority rule, replay depth, and preferred equal-length action. `profiles.json` contains only those parameters. It does not map dimensions to paths or optimal lengths.

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
