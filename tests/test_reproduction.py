"""Behavior checks against the paper and a mathematically independent oracle."""

import unittest
import json
from pathlib import Path
import tempfile
from research.experiment import run, min_pitch, optimal, assignment_lower_bound
from route import construct
from research.bounds import assignment_lower_bound as folded_lower_bound


class ReproductionTests(unittest.TestCase):
    def test_min_cost_flow_exports_disjoint_optimal_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "mcf.json"
            result = optimal(3, 3, 2, path=output)
            routes = json.loads(output.read_text())
        self.assertEqual(result["total_length"], 21)
        self.assertEqual(routes["total_length"], 21)
        self.assertEqual(len(routes["paths"]), 9)
        occupied, terminals = set(), set()
        length = 0
        for path in routes["paths"]:
            terminals.add(tuple(path[-1]))
            points = [tuple(path[0])]
            for (x, y), (xx, yy) in zip(path, path[1:]):
                self.assertTrue((x == xx) != (y == yy))
                dx, dy = (xx > x) - (xx < x), (yy > y) - (yy < y)
                while (x, y) != (xx, yy):
                    x, y = x + dx, y + dy
                    points.append((x, y))
                    length += 1
            for i, point in enumerate(points):
                self.assertNotIn(point, occupied)
                self.assertEqual(point[0] in (0, 8) or point[1] in (0, 8), i == 0)
                occupied.add(point)
        self.assertEqual(terminals, {(x, y) for x in (2, 4, 6) for y in (2, 4, 6)})
        self.assertEqual(length, 21)

    def test_one_and_two_terminal_wide_arrays(self):
        # NM*d is a lower bound, as each terminal is at least d from any edge.
        for n, m in [(1, 1), (1, 100), (100, 1), (2, 2), (2, 100), (100, 2)]:
            for d in (1, 3):
                with self.subTest(N=n, M=m, d=d):
                    result = construct(n, m, d)
                    self.assertTrue(result["verified"])
                    self.assertEqual(result["total_length"], n * m * d)

    def test_paper_routes(self):
        for n, m, d, total in [(6, 4, 2, 72), (30, 30, 9, 55112), (72, 13, 6, 26498)]:
            with self.subTest(N=n, M=m):
                result = run(n, m, d)
                self.assertTrue(result["verified"])
                self.assertEqual(result["total_length"], total)

    def test_parity_and_pitch_against_grid_flow(self):
        # All parity combinations, square/rectangular, and a central intersection.
        for n, m in [(3, 3), (3, 4), (4, 3), (4, 4), (5, 7), (7, 5), (8, 6)]:
            with self.subTest(N=n, M=m):
                result = min_pitch(n, m)
                d = result["d"]
                exact = optimal(n, m, d)
                lower = assignment_lower_bound(n, m, d)
                self.assertEqual(lower, folded_lower_bound(n, m, d))
                self.assertTrue(exact["feasible"])
                self.assertLessEqual(lower, exact["total_length"])
                self.assertLessEqual(exact["total_length"], result["total_length"])
                self.assertFalse(optimal(n, m, d - 1)["feasible"])

    def test_known_nonoptimal_case(self):
        # The paper itself reports four units above optimum for this case.
        result = run(98, 51, 20)
        self.assertEqual(result["total_length"], 1399338)
        self.assertEqual(assignment_lower_bound(98, 51, 20), 1399334)

    def test_infeasible_spacing(self):
        self.assertFalse(run(30, 30, 8)["success"])



if __name__ == "__main__":
    unittest.main(verbosity=2)
