"""Behavior checks against the paper and a mathematically independent oracle."""

import unittest
from research.experiment import run, min_pitch, optimal, assignment_lower_bound
from research.bounds import assignment_lower_bound as folded_lower_bound


class ReproductionTests(unittest.TestCase):
    def test_one_and_two_terminal_wide_arrays(self):
        # NM*d is a lower bound, as each terminal is at least d from any edge.
        for n, m in [(1, 1), (1, 100), (100, 1), (2, 2), (2, 100), (100, 2)]:
            for d in (1, 3):
                with self.subTest(N=n, M=m, d=d):
                    result = run(n, m, d, improved=True)
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

    def test_improved_routes_and_remaining_gap(self):
        # Both orientations, and a known case that remains globally suboptimal.
        for n, m, d, expected in [
            (88, 90, 27, 4051488),
            (90, 88, 27, 4051488),
            (98, 51, 20, 1399338),
        ]:
            with self.subTest(N=n, M=m):
                baseline = run(n, m, d)
                result = run(n, m, d, improved=True)
                self.assertTrue(result["verified"])
                self.assertLessEqual(result["total_length"], baseline["total_length"])
                self.assertEqual(result["total_length"], expected)

    def test_residual_repairs_known_counterexamples(self):
        # Independently computed grid optima / assignment lower bounds.
        for n, m, d, expected in [
            (111, 27, 12, 326743),
            (98, 51, 20, 1399334),
            (15, 99, 8, 51076),
            (99, 15, 8, 51076),
            (15, 100, 8, 51616),
            (100, 15, 8, 51616),
            (13, 73, 7, 25204),
            (73, 13, 7, 25204),
            (13, 100, 7, 35032),
            (100, 13, 7, 35032),
            (199, 35, 17, 1165807),
        ]:
            with self.subTest(N=n, M=m):
                result = run(n, m, d, polish=True)
                self.assertTrue(result["verified"])
                self.assertTrue(result["residual_optimality_certified"])
                self.assertEqual(result["total_length"], expected)

    def test_residual_certificates_against_independent_grid_flow(self):
        for n, m in [(3, 4), (4, 3), (5, 8), (8, 5), (7, 8), (8, 7), (9, 10), (10, 9)]:
            with self.subTest(N=n, M=m):
                d = min_pitch(n, m)["d"]
                result = run(n, m, d, polish=True)
                exact = optimal(n, m, d)
                self.assertTrue(result["verified"])
                self.assertGreaterEqual(result["total_length"], exact["total_length"])
                if result["residual_optimality_certified"]:
                    self.assertEqual(result["total_length"], exact["total_length"])

    def test_excluded_axis_terminals_do_not_abort_routing(self):
        for n, m in [(301, 21), (21, 301)]:
            result = run(n, m, 11, improved=True)
            self.assertTrue(result["verified"])
            self.assertFalse(result["selected_fan"])
        result = run(11, 3, 2, polish=True)
        self.assertTrue(result["residual_optimality_certified"])
        self.assertEqual(result["total_length"], optimal(11, 3, 2)["total_length"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
