"""Exercise sharded evaluation, resumed coverage, and conservative certificates."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from research.benchmark import ROOT
from research.full_sweep import classify


class FullSweepTests(unittest.TestCase):
    def test_shards_cover_both_orientations_and_resume_without_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = []
            for shard in range(2):
                output = Path(directory) / str(shard)
                command = [
                    sys.executable,
                    "-m",
                    "research.full_sweep",
                    "--max-n",
                    "4",
                    "--workers",
                    "2",
                    "--shards",
                    "2",
                    "--shard",
                    str(shard),
                    "--output",
                    str(output),
                ]
                subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
                self.assertTrue((output / "_SUCCESS").exists())
                original = (output / "results.jsonl").read_text()
                subprocess.run(
                    command + ["--resume"], cwd=ROOT, check=True, capture_output=True
                )
                self.assertEqual((output / "results.jsonl").read_text(), original)
                rows.extend(json.loads(line) for line in original.splitlines())
            self.assertEqual(len(rows), 16)
            self.assertEqual(
                {(r["N"], r["M"]) for r in rows},
                {(n, m) for n in range(1, 5) for m in range(1, 5)},
            )
            for row in rows:
                self.assertTrue(row["geometric"]["verified"])
                self.assertEqual(row["geometric"]["total_length"], row["lower_bound"])

    def test_gap_to_lower_bound_alone_is_not_nonoptimality(self):
        route = {"verified": True, "total_length": 12}
        self.assertEqual(classify(route, 10, route), "unknown")
        self.assertEqual(
            classify(route, 10, {"verified": True, "total_length": 11}), "nonoptimal"
        )
        self.assertEqual(classify(route, 12, None), "optimal")
        self.assertEqual(classify(None, 10, route), "construction_failed")
