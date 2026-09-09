"""Routing contracts for the default constructor and archived replay method."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.benchmark import ROOT, audit, load_cases
from research.bounds import assignment_lower_bound
from route import construct


class LegacyReplayTests(unittest.TestCase):
    def route(self, n, m, d, *extra):
        process = subprocess.run(
            [
                sys.executable,
                str(ROOT / "research/replay.py"),
                str(n),
                str(m),
                str(d),
                *extra,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        result = json.loads(process.stdout)
        self.assertTrue(result["verified"])
        self.assertEqual(result["residual_work"], 0)
        self.assertFalse(result["polished"])
        return result

    def test_explicit_fan_matches_independent_bounds(self):
        for n, m, d in [(1, 1, 1), (11, 5, 3), (5, 11, 3), (5, 5, 3), (6, 6, 3)]:
            with self.subTest(N=n, M=m, d=d):
                result = self.route(n, m, d)
                self.assertTrue(result["optimality_certified"])
                self.assertEqual(
                    result["total_length"], assignment_lower_bound(n, m, d)
                )

    def test_replay_repairs_baseline_and_writes_transposed_paths(self):
        baseline = self.route(105, 21, 10, "--baseline")
        self.assertEqual(baseline["total_length"], 140539)
        for n, m in [(105, 21), (21, 105)]:
            with self.subTest(N=n, M=m), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "paths.json"
                result = self.route(n, m, 10, str(path))
                self.assertEqual(result["total_length"], 140533)
                self.assertFalse(result["optimality_certified"])
                saved = json.loads(path.read_text())
                self.assertEqual((saved["N"], saved["M"], saved["d"]), (n, m, 10))
                self.assertEqual(len(saved["paths"]), n * m)
                self.assertEqual(saved["total_length"], result["total_length"])

    def test_recorded_deep_replay_trace(self):
        row = next(row for row in load_cases() if (row["N"], row["M"]) == (229, 42))
        result = audit(row, "witness", check_bounds=True)
        self.assertTrue(result["optimality_verified_offline"])
        self.assertEqual(result["constructor"]["total_length"], 2401474)

    def test_paper_audit_records_a_gap_without_claiming_optimality(self):
        row = next(row for row in load_cases() if (row["N"], row["M"]) == (105, 21))
        result = audit(row, "paper")
        self.assertTrue(result["constructor"]["verified"])
        self.assertGreater(result["constructor"]["total_length"], result["lower_bound"])
        self.assertFalse(result["optimality_verified_offline"])

    def test_invalid_dimensions_are_rejected(self):
        process = subprocess.run(
            [sys.executable, str(ROOT / "route.py"), "0", "5", "1"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("must be positive", process.stderr)

    def test_audit_resume_and_stale_checkpoint_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "audit.jsonl"
            command = [
                sys.executable,
                "-m",
                "research.benchmark",
                "--mode",
                "witness",
                "--max-n",
                "5",
                "--output",
                str(path),
            ]
            subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
            original = path.read_text()
            subprocess.run(
                command + ["--resume"], cwd=ROOT, check=True, capture_output=True
            )
            self.assertEqual(path.read_text(), original)
            saved = json.loads(original)
            saved["run_signature"] = "stale"
            path.write_text(json.dumps(saved) + "\n")
            result = subprocess.run(
                command + ["--resume"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("checkpoint does not match", result.stderr)


class SingleConstructionTests(unittest.TestCase):
    def test_one_native_construction_and_repeatable_paths(self):
        # Exercise both sides of the fan threshold, both orientations, and odd axes.
        for n, m, d in [
            (30, 30, 9),
            (72, 13, 6),
            (13, 72, 6),
            (6, 4, 2),
            (5, 11, 3),
            (11, 5, 3),
        ]:
            with self.subTest(N=n, M=m, d=d), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "paths.json"
                with patch("route.subprocess.run", wraps=subprocess.run) as invoke:
                    first = construct(n, m, d, path)
                self.assertEqual(invoke.call_count, 1)
                saved = path.read_bytes()
                second = construct(n, m, d, path)
                self.assertEqual(path.read_bytes(), saved)
                self.assertEqual(first["total_length"], second["total_length"])
                self.assertEqual(first["optimality_certified"], 2 * d >= min(n, m))
                exported = json.loads(saved)
                self.assertEqual(
                    (exported["N"], exported["M"], exported["d"]), (n, m, d)
                )
                self.assertEqual(len(exported["paths"]), n * m)
                if first["optimality_certified"]:
                    self.assertEqual(
                        first["total_length"], assignment_lower_bound(n, m, d)
                    )

    def test_failed_construction_does_not_retry_or_write_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "paths.json"
            with (
                patch("route.subprocess.run", wraps=subprocess.run) as invoke,
                self.assertRaises(subprocess.CalledProcessError),
            ):
                construct(30, 30, 8, path)
            self.assertEqual(invoke.call_count, 1)
            self.assertFalse(path.exists())

    def test_revised_rules_close_known_gaps_in_one_construction(self):
        for n, m, d, expected in [
            (98, 51, 20, 1399334),
            (105, 21, 10, 140533),
            (111, 27, 12, 326743),
            (24, 13, 6, 6454),
            (44, 33, 12, 138128),
            (11, 7, 3, 499),
            (17, 9, 4, 1629),
            (58, 22, 10, 77608),
            (66, 24, 11, 114888),
            # Density alone redirects an interior channel too early here.
            (97, 28, 13, 282056),
            (98, 28, 13, 285860),
            (99, 28, 13, 289692),
            (22, 14, 6, 6656),
            (231, 73, 31, 12067011),
            # A short central fan and middle-row port allocation interact.
            (19, 9, 4, 1875),
            (25, 17, 7, 12548),
            (33, 15, 7, 13913),
            (35, 15, 7, 14966),
            (37, 15, 7, 16037),
            (43, 17, 8, 26787),
        ]:
            with self.subTest(N=n, M=m):
                with patch("route.subprocess.run", wraps=subprocess.run) as invoke:
                    result = construct(n, m, d)
                self.assertEqual(invoke.call_count, 1)
                self.assertEqual(result["total_length"], expected)
                self.assertTrue(result["verified"])
                self.assertFalse(result["optimality_certified"])
                self.assertEqual(result["residual_work"], 0)

    def test_offline_optimality_does_not_claim_an_online_certificate(self):
        result = construct(19, 9, 4)
        self.assertEqual(result["total_length"], assignment_lower_bound(19, 9, 4))
        self.assertFalse(result["optimality_certified"])
        self.assertFalse(result["polished"])
        self.assertEqual(result["residual_work"], 0)


if __name__ == "__main__":
    unittest.main()
