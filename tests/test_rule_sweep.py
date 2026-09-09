"""A completed rule sweep must survive export without losing coverage or evidence."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from research.export_rule_sweep import collect
from route import ROOT


class RuleSweepTests(unittest.TestCase):
    def test_sharded_export_rejects_missing_and_corrupt_observations(self):
        with tempfile.TemporaryDirectory() as folder:
            inputs = [Path(folder) / str(i) for i in range(2)]
            for shard, output in enumerate(inputs):
                command = [
                    sys.executable,
                    "-m",
                    "research.rule_sweep",
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
                original = (output / "results.jsonl").read_bytes()
                subprocess.run(
                    command + ["--resume"], cwd=ROOT, check=True, capture_output=True
                )
                self.assertEqual((output / "results.jsonl").read_bytes(), original)
            rows, sources, repeated = collect(inputs, 4)
            self.assertEqual(
                {(r["N"], r["M"]) for r in rows},
                {(n, m) for n in range(1, 5) for m in range(1, 5)},
            )
            self.assertEqual(repeated, 0)
            self.assertEqual(len(sources), 2)
            published = Path(folder) / "published"
            subprocess.run(
                [sys.executable, "-m", "research.export_rule_sweep",
                 *map(str, inputs), "--max-n", "4", "--output", str(published)],
                cwd=ROOT, check=True, capture_output=True,
            )
            summary = json.loads((published / "summary.json").read_text())
            self.assertEqual(summary["full_square"]["revised"]["statuses"], {"optimal": 16})
            with self.assertRaisesRegex(ValueError, "Incomplete coverage"):
                collect(inputs[:1], 4)
            path = inputs[0] / "results.jsonl"
            records = [json.loads(line) for line in path.read_text().splitlines()]
            records[0]["total_length"] += 1
            path.write_text("".join(json.dumps(r) + "\n" for r in records))
            with self.assertRaisesRegex(ValueError, "Invalid native construction"):
                collect(inputs, 4)


if __name__ == "__main__":
    unittest.main()
