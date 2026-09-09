"""Reproduce the published fixed-pitch cases and independently check small optima."""

import argparse
import csv
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
TABLE_II = [
    (30, 30, 9, 55112),
    (45, 45, 14, 273183),
    (55, 55, 17, 602856),
    (64, 64, 19, 1092600),
    (71, 71, 22, 1657902),
    (72, 13, 6, 26498),
    (77, 26, 11, 183686),
    (111, 27, 12, 326743),
    (69, 58, 19, 1034338),
    (98, 51, 20, 1399338),
]
TABLE_III = [
    (316, 316, 93, 629985640),
    (447, 447, 132, 2517494576),
    (548, 548, 161, 5679142936),
    (632, 632, 186, 10042278616),
    (707, 707, 208, 15720245427),
    (375, 267, 92, 608817645),
    (532, 376, 129, 2420475700),
    (858, 350, 141, 4385731204),
    (904, 442, 171, 8477760224),
    (949, 527, 196, 14012963087),
]


def run(n, m, d, path=None, *, improved=False, polish=False):
    command = [str(ROOT / "build/urber"), str(n), str(m), str(d)]
    if path:
        command.append(str(path))
    if polish:
        command.append("--polish")
    elif improved:
        command.append("--improved")
    process = subprocess.run(command, capture_output=True, text=True)
    if not process.stdout.strip():
        raise RuntimeError(f"{n}x{m}, d={d}: {process.stderr}")
    result = json.loads(process.stdout)
    if process.returncode not in (0, 1):
        raise RuntimeError(process.stderr)
    return result


def min_pitch(n, m):
    """Heuristic pitch search; this does not prove a minimum feasible pitch."""
    low, high = (
        max(1, (n * m + 2 * (n + m + 2) - 1) // (2 * (n + m + 2))),
        (min(n, m) + 1) // 2,
    )
    while low < high:
        mid = (low + high) // 2
        if run(n, m, mid)["success"]:
            high = mid
        else:
            low = mid + 1
    result = run(n, m, low)
    if not result["success"]:
        raise RuntimeError("Upper bound not routable")
    return result


def optimal(n, m, d, path=None):
    """Vertex-capacitated fine-grid min-cost flow; no URBER rules used."""
    import numpy as np
    from ortools.graph.python import min_cost_flow

    start = time.perf_counter()
    width, height = (n + 1) * d + 1, (m + 1) * d + 1
    grid = np.arange(width * height, dtype=np.int32).reshape(height, width)
    v = width * height
    flow = min_cost_flow.SimpleMinCostFlow()

    def add(tail, head, cost):
        tail = np.asarray(tail, dtype=np.int32).ravel()
        head = np.asarray(head, dtype=np.int32).ravel()
        flow.add_arcs_with_capacity_and_unit_cost(
            tail,
            head,
            np.ones(len(tail), dtype=np.int64),
            np.full(len(tail), cost, dtype=np.int64),
        )

    all_nodes = grid.ravel()
    add(2 * all_nodes, 2 * all_nodes + 1, 0)
    interior = grid[1:-1, 1:-1]
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        neighbor = grid[1 + dy : height - 1 + dy, 1 + dx : width - 1 + dx]
        add(2 * interior + 1, 2 * neighbor, 1)
    boundary = np.concatenate([grid[0, :], grid[-1, :], grid[1:-1, 0], grid[1:-1, -1]])
    source, sink = 2 * v, 2 * v + 1
    add(2 * boundary + 1, np.full(len(boundary), sink), 0)
    terminals = grid[d : m * d + 1 : d, d : n * d + 1 : d].ravel()
    add(np.full(len(terminals), source), 2 * terminals, 0)
    flow.set_node_supply(source, n * m)
    flow.set_node_supply(sink, -n * m)
    built = time.perf_counter()
    status = flow.solve()
    result = {
        "N": n,
        "M": m,
        "d": d,
        "feasible": status == flow.OPTIMAL,
        "total_length": int(flow.optimal_cost()) if status == flow.OPTIMAL else None,
        "build_seconds": built - start,
        "solve_seconds": time.perf_counter() - built,
        "nodes": flow.num_nodes(),
        "arcs": flow.num_arcs(),
        "status": str(status),
    }
    if path is not None and result["feasible"]:
        successor = {
            flow.tail(i): flow.head(i)
            for i in range(flow.num_arcs())
            if flow.flow(i) and flow.tail(i) != source
        }
        paths, occupied = [], set()
        expected_terminals = {
            (x * d, y * d) for x in range(1, n + 1) for y in range(1, m + 1)
        }
        total = 0
        for terminal in terminals:
            node, points = 2 * int(terminal), []
            while node != sink:
                if node % 2 == 0:
                    vertex = node // 2
                    points.append((vertex % width, vertex // width))
                node = successor[node]
                if len(points) > v:
                    raise RuntimeError("Cycle in extracted minimum-cost flow")
            points.reverse()
            for i, point in enumerate(points):
                x, y = point
                boundary = x in (0, width - 1) or y in (0, height - 1)
                if point in occupied or boundary != (i == 0):
                    raise RuntimeError(
                        "Invalid geometry in extracted minimum-cost flow"
                    )
                if point in expected_terminals and i != len(points) - 1:
                    raise RuntimeError("Extracted path passes through another terminal")
                if i and abs(x - points[i - 1][0]) + abs(y - points[i - 1][1]) != 1:
                    raise RuntimeError("Non-adjacent vertices in extracted path")
                occupied.add(point)
            total += len(points) - 1
            bends = [points[0]]
            for i in range(1, len(points) - 1):
                before = (
                    points[i][0] - points[i - 1][0],
                    points[i][1] - points[i - 1][1],
                )
                after = (
                    points[i + 1][0] - points[i][0],
                    points[i + 1][1] - points[i][1],
                )
                if before != after:
                    bends.append(points[i])
            bends.append(points[-1])
            paths.append(bends)
        if len(paths) != n * m or total != result["total_length"]:
            raise RuntimeError("Extracted flow length or terminal count mismatch")
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(dict(N=n, M=m, d=d, total_length=total, paths=paths)) + "\n"
        )
    return result


def assignment_lower_bound(n, m, d):
    """Relax interior nonintersection; retain unique boundary ports and Manhattan costs.

    Every legal routing induces a feasible flow here. Equality with a checked
    routing therefore certifies global optimality; a gap alone proves nothing.
    """
    from ortools.graph.python import min_cost_flow
    import numpy as np

    flow = min_cost_flow.SimpleMinCostFlow()
    gx, gy = (n + 1) * d, (m + 1) * d
    v = n * m
    offsets = [v, v + gx - 1, v + 2 * (gx - 1), v + 2 * (gx - 1) + gy - 1]
    sink = v + 2 * (gx + gy - 2)
    tails = []
    heads = []
    capacities = []
    costs = []

    def arc(a, b, cap, cost):
        tails.append(a)
        heads.append(b)
        capacities.append(cap)
        costs.append(cost)

    for side, offset in enumerate(offsets):
        size = (gx if side < 2 else gy) - 1
        for j in range(size):
            arc(offset + j, sink, 1, 0)
            if j:
                arc(offset + j - 1, offset + j, v, 1)
                arc(offset + j, offset + j - 1, v, 1)
    for x in range(1, n + 1):
        for y in range(1, m + 1):
            node = (x - 1) * m + y - 1
            for side, pos, cost in [
                (0, x * d, y * d),
                (1, x * d, gy - y * d),
                (2, y * d, x * d),
                (3, y * d, gx - x * d),
            ]:
                arc(node, offsets[side] + pos - 1, 1, cost)
    flow.add_arcs_with_capacity_and_unit_cost(
        np.array(tails, dtype=np.int32),
        np.array(heads, dtype=np.int32),
        np.array(capacities, dtype=np.int64),
        np.array(costs, dtype=np.int64),
    )
    flow.set_nodes_supplies(np.arange(v, dtype=np.int32), np.ones(v, dtype=np.int64))
    flow.set_node_supply(sink, -v)
    if flow.solve() != flow.OPTIMAL:
        return None
    return int(flow.optimal_cost())


def save(name, data):
    directory = ROOT / "results"
    directory.mkdir(exist_ok=True)
    (directory / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n")
    if data:
        with (directory / f"{name}.csv").open("w") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)


def tables(which):
    rows = []
    (ROOT / "results").mkdir(exist_ok=True)
    for n, m, d, published in TABLE_II if which == "ii" else TABLE_III:
        result = run(
            n, m, d, ROOT / f"results/route-{n}-{m}.json" if which == "ii" else None
        )
        result.update(paper_length=published, delta=result["total_length"] - published)
        rows.append(result)
        save(f"table_{which}", rows)
        print(json.dumps(result), flush=True)
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["ii", "iii", "mcf", "pitch"])
    parser.add_argument("dimensions", type=int, nargs="*")
    parser.add_argument("--output", type=Path, help="write MCF paths as JSON")
    args = parser.parse_args()
    if args.output is not None and args.mode != "mcf":
        parser.error("--output is supported for the mcf mode")
    if args.mode in ("ii", "iii"):
        tables(args.mode)
    elif args.mode == "mcf":
        print(json.dumps(optimal(*args.dimensions, path=args.output)), flush=True)
    else:
        print(json.dumps(min_pitch(*args.dimensions)), flush=True)
