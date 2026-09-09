"""Exercise sharded evaluation, resumed coverage, and conservative certificates."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from research.benchmark import ROOT
from research.full_sweep import classify, portfolio
from research.merge_sweep import merge


class FullSweepTests(unittest.TestCase):
    def test_parallel_portfolio_preserves_order_ties_and_early_stop(self):
        ready = threading.Event()
        configs = [{"candidate": i} for i in range(4)]

        def native(n, m, d, config):
            i = config["candidate"]
            if i == 0:
                self.assertTrue(ready.wait(5))
            if i == 1:
                ready.set()
            return {"verified": True, "total_length": [12, 10, 10, 9][i]}

        with patch("research.full_sweep.native", side_effect=native):
            best, selected, attempts = portfolio(4, 3, 1, 10, configs, workers=4)
        self.assertEqual(best["total_length"], 10)
        self.assertEqual(selected, configs[1])
        self.assertEqual(attempts, 2)

        def unavailable(n, m, d, config):
            if config["candidate"] == 0:
                return None
            return {"verified": True, "total_length": 12}

        with patch("research.full_sweep.native", side_effect=unavailable):
            sequential = portfolio(4, 3, 1, 10, configs)
            parallel = portfolio(4, 3, 1, 10, configs, workers=4)
        self.assertEqual(parallel, sequential)
        self.assertEqual(parallel[1:], (configs[1], 4))

    def test_parallel_candidates_match_sequential_native_results(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "pairs.json"
            manifest.write_text(json.dumps([[15, 11], [14, 10], [4, 3]]))
            observations = []
            for workers in (1, 4):
                output = Path(directory) / str(workers)
                subprocess.run(
                    [sys.executable, "-m", "research.full_sweep", "--max-n", "15",
                     "--workers", "2", "--pairs", str(manifest),
                     "--candidate-workers", str(workers), "--output", str(output)],
                    cwd=ROOT, check=True, capture_output=True,
                )
                self.assertTrue((output / "_SUCCESS").exists())
                observations.append({
                    (r["N"], r["M"]): r for r in map(
                        json.loads, (output / "results.jsonl").read_text().splitlines()
                    )
                })
            for key, sequential in observations[0].items():
                parallel = observations[1][key]
                for field in ("d", "lower_bound", "geometric_config", "trials",
                              "paper_status", "geometric_status"):
                    self.assertEqual(sequential[field], parallel[field], (key, field))
                for method in ("paper", "geometric"):
                    self.assertEqual(sequential[method]["total_length"],
                                     parallel[method]["total_length"], (key, method))

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
            inputs = [Path(directory) / "0", Path(directory) / "1"]
            merged, metadata = merge(inputs + [inputs[0]], 4)
            self.assertEqual(len(merged), 16)
            self.assertGreater(metadata["consistent_repeated_rows"], 0)
            conflicting = Path(directory) / "conflicting"
            conflicting.mkdir()
            altered = dict(merged[0], d=merged[0]["d"] + 1)
            (conflicting / "results.jsonl").write_text(json.dumps(altered) + "\n")
            (conflicting / "run.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Repeated observations disagree"):
                merge(inputs + [conflicting], 4)
            with self.assertRaisesRegex(ValueError, "Incomplete coverage"):
                merge(inputs[:1], 4)
            self.assertEqual(len(rows), 16)
            self.assertEqual(
                {(r["N"], r["M"]) for r in rows},
                {(n, m) for n in range(1, 5) for m in range(1, 5)},
            )
            for row in rows:
                self.assertTrue(row["geometric"]["verified"])
                self.assertEqual(row["geometric"]["total_length"], row["lower_bound"])

    def test_explicit_pairs_cover_only_requested_orientations_and_guard_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "pairs.json"
            manifest.write_text(json.dumps([[4, 3], [2, 2]]))
            output = Path(directory) / "out"
            command = [
                sys.executable,
                "-m",
                "research.full_sweep",
                "--max-n",
                "4",
                "--workers",
                "2",
                "--pairs",
                str(manifest),
                "--output",
                str(output),
            ]
            subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
            rows = [
                json.loads(line)
                for line in (output / "results.jsonl").read_text().splitlines()
            ]
            self.assertEqual({(r["N"], r["M"]) for r in rows}, {(4, 3), (3, 4), (2, 2)})
            self.assertEqual(len(rows), 3)
            self.assertTrue((output / "_SUCCESS").exists())
            subprocess.run(
                command + ["--resume"], cwd=ROOT, check=True, capture_output=True
            )
            manifest.write_text(json.dumps([[4, 2]]))
            rejected = subprocess.run(
                command + ["--resume"], cwd=ROOT, capture_output=True, text=True
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("signature differs", rejected.stderr)
            manifest.write_text(json.dumps([[4, 3], [4, 3]]))
            rejected = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("duplicate pair", rejected.stderr)

    def test_gap_to_lower_bound_alone_is_not_nonoptimality(self):
        route = {"verified": True, "total_length": 12}
        self.assertEqual(classify(route, 10, route), "unknown")
        self.assertEqual(
            classify(route, 10, {"verified": True, "total_length": 11}), "nonoptimal"
        )
        self.assertEqual(classify(route, 12, None), "optimal")
        self.assertEqual(classify(None, 10, route), "construction_failed")
