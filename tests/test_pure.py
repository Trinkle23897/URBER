"""End-to-end coverage for the standalone pure geometric entry point."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from research.benchmark import audit, load_cases, ROOT
from research.bounds import assignment_lower_bound


class PureRoutingTests(unittest.TestCase):
    def route(self, n, m, d, *extra):
        process = subprocess.run(
            [sys.executable, str(ROOT / "route.py"), str(n), str(m), str(d), *extra],
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

    def test_invalid_dimensions_are_rejected(self):
        process = subprocess.run(
            [sys.executable, str(ROOT / "route.py"), "0", "5", "1"],
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
                command + ["--resume"], cwd=ROOT, capture_output=True, text=True
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("checkpoint does not match", result.stderr)


if __name__ == "__main__":
    unittest.main()
