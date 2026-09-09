"""Exact boundary-assignment lower bound, folded by both grid reflections.

This quotient aggregates supplies/capacities over reflection orbits. A quotient
flow lifts uniformly to a feasible fractional full-network flow of equal cost;
integrality of min-cost flow then gives equality of the two optimal costs.
It does not assume that an optimal integral routing itself is symmetric.
"""


def assignment_lower_bound(n, m, d):
    from ortools.graph.python import min_cost_flow
    import numpy as np

    nx, ny = (n + 1) // 2, (m + 1) // 2
    gx, gy = (n + 1) * d, (m + 1) * d
    horizontal, vertical = gx // 2, gy // 2
    terminals = nx * ny
    sink = terminals + horizontal + vertical
    tails, heads, capacities, costs = [], [], [], []

    def add(a, b, capacity, cost):
        tails.append(a)
        heads.append(b)
        capacities.append(capacity)
        costs.append(cost)

    for offset, span in [(terminals, gx), (terminals + horizontal, gy)]:
        for position in range(1, span // 2 + 1):
            node = offset + position - 1
            add(node, sink, 2 if 2 * position == span else 4, 0)
            if position > 1:
                add(node - 1, node, n * m, 1)
                add(node, node - 1, n * m, 1)

    supplies = []
    for x in range(1, nx + 1):
        for y in range(1, ny + 1):
            node = (x - 1) * ny + y - 1
            multiplicity = (1 if 2 * x == n + 1 else 2) * (1 if 2 * y == m + 1 else 2)
            supplies.append(multiplicity)
            add(node, terminals + x * d - 1, multiplicity, y * d)
            add(node, terminals + horizontal + y * d - 1, multiplicity, x * d)

    flow = min_cost_flow.SimpleMinCostFlow()
    flow.add_arcs_with_capacity_and_unit_cost(
        np.array(tails, dtype=np.int32),
        np.array(heads, dtype=np.int32),
        np.array(capacities, dtype=np.int64),
        np.array(costs, dtype=np.int64),
    )
    flow.set_nodes_supplies(
        np.arange(terminals, dtype=np.int32), np.array(supplies, dtype=np.int64)
    )
    flow.set_node_supply(sink, -n * m)
    return int(flow.optimal_cost()) if flow.solve() == flow.OPTIMAL else None
