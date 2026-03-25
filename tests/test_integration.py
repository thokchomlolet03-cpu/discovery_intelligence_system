import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent.parent


class IntegrationTest(unittest.TestCase):
    def run_command(self, *args):
        return subprocess.run(
            [sys.executable, *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_evaluate_system_writes_structured_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.run_command("evaluate_system.py", "--output-dir", tmpdir, "--seed", "123")
            summary_path = Path(tmpdir) / "evaluation_summary.json"
            config_path = Path(tmpdir) / "run_config.json"

            self.assertTrue(summary_path.exists())
            self.assertTrue(config_path.exists())

            summary = json.loads(summary_path.read_text())
            self.assertIn("selected_model", summary)
            self.assertIn("benchmark", summary)
            self.assertIn("metrics", summary)

    def test_evolve_system_dry_run_writes_artifacts_without_mutating_source_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = REPO_ROOT / "data.csv"
            before = pd.read_csv(data_path)

            self.run_command(
                "evolve_system.py",
                "--iterations",
                "1",
                "--candidates-per-round",
                "6",
                "--feedback-per-class",
                "2",
                "--output-dir",
                tmpdir,
                "--dry-run",
                "--seed",
                "123",
            )

            after = pd.read_csv(data_path)
            self.assertEqual(len(before), len(after))

            for name in (
                "run_config.json",
                "evaluation_summary.json",
                "decision_output.json",
                "logs.json",
                "iteration_history.csv",
                "generated_candidates.csv",
                "candidates_processed.csv",
                "predicted_candidates.csv",
                "labeled_candidates.csv",
                "review_queue.csv",
            ):
                self.assertTrue((Path(tmpdir) / name).exists(), name)

            self.assertTrue((Path(tmpdir) / "data" / "knowledge.json").exists())
            self.assertTrue((Path(tmpdir) / "data" / "logs.json").exists())
            self.assertTrue((Path(tmpdir) / "data" / "decision_output.json").exists())

            predicted = pd.read_csv(Path(tmpdir) / "predicted_candidates.csv")
            if not predicted.empty:
                for column in ("experiment_value", "risk_level", "is_feasible", "feasibility_reason"):
                    self.assertIn(column, predicted.columns)

    def test_evolve_system_write_back_only_adds_balanced_feedback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_data = REPO_ROOT / "data.csv"
            temp_data = Path(tmpdir) / "data.csv"
            shutil.copy2(source_data, temp_data)

            before = pd.read_csv(temp_data)
            before_counts = before["biodegradable"].value_counts(dropna=False).to_dict()

            self.run_command(
                "evolve_system.py",
                "--iterations",
                "1",
                "--candidates-per-round",
                "6",
                "--feedback-per-class",
                "2",
                "--output-dir",
                tmpdir,
                "--data-path",
                str(temp_data),
                "--seed",
                "123",
            )

            after = pd.read_csv(temp_data)
            after_counts = after["biodegradable"].value_counts(dropna=False).to_dict()

            delta_pos = after_counts.get(1, 0) - before_counts.get(1, 0)
            delta_neg = after_counts.get(0, 0) - before_counts.get(0, 0)

            self.assertGreaterEqual(delta_pos, 0)
            self.assertGreaterEqual(delta_neg, 0)
            self.assertEqual(delta_pos, delta_neg)


if __name__ == "__main__":
    unittest.main()
