import tempfile
import unittest
from pathlib import Path

import pandas as pd

from dashboard import find_artifact, normalize_candidates, normalize_decision_payload, normalize_logs_payload, ui_labels


class DashboardTest(unittest.TestCase):
    def test_find_artifact_falls_back_to_repo_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = find_artifact(Path(tmpdir), ("data.csv",))

        self.assertIsNotNone(artifact)
        self.assertTrue(str(artifact).endswith("data.csv"))

    def test_normalize_candidates_adds_dashboard_defaults(self):
        frame = pd.DataFrame([{"polymer": "cand_1", "confidence": 0.75}])

        normalized = normalize_candidates(frame)

        self.assertIn("uncertainty", normalized.columns)
        self.assertIn("novelty", normalized.columns)
        self.assertIn("final_score", normalized.columns)
        self.assertAlmostEqual(float(normalized.loc[0, "uncertainty"]), 0.5, places=6)
        self.assertEqual(float(normalized.loc[0, "novelty"]), 0.0)

    def test_ui_labels_use_current_thresholds(self):
        frame = pd.DataFrame([{"confidence": 0.9}, {"confidence": 0.5}, {"confidence": 0.1}])

        labels = ui_labels(frame, low_threshold=0.3, high_threshold=0.7)

        self.assertEqual(list(labels), ["1", "uncertain", "0"])

    def test_normalize_logs_payload_flattens_nested_metrics(self):
        payload = [
            {
                "iteration": 2,
                "dataset_size": 120,
                "selected_model": {"name": "rf_sigmoid", "calibration_method": "sigmoid"},
                "holdout": {"accuracy": 0.9, "f1_macro": 0.8},
                "feasible_candidates": 18,
                "infeasible_candidates": 2,
                "top_experiment_value": 0.77,
                "decision_risk_counts": {"high": 2, "medium": 5, "low": 3},
                "selection_counts": {"exploit": 4, "learn": 3, "explore": 3},
                "label_counts": {"1": 80, "0": 30, "-1": 10},
            }
        ]

        normalized = normalize_logs_payload(payload)

        self.assertEqual(int(normalized.loc[0, "iteration"]), 2)
        self.assertEqual(float(normalized.loc[0, "holdout_accuracy"]), 0.9)
        self.assertEqual(int(normalized.loc[0, "selection_learn"]), 3)
        self.assertEqual(int(normalized.loc[0, "label_-1"]), 10)
        self.assertEqual(int(normalized.loc[0, "feasible_candidates"]), 18)
        self.assertEqual(int(normalized.loc[0, "decision_high_risk"]), 2)

    def test_normalize_decision_payload_extracts_top_experiments(self):
        payload = {
            "iteration": 1,
            "summary": {"top_k": 10},
            "top_experiments": [
                {
                    "rank": 1,
                    "smiles": "CCO",
                    "confidence": 0.4,
                    "uncertainty": 0.8,
                    "novelty": 0.6,
                    "experiment_value": 0.7,
                    "risk": "high",
                }
            ],
        }

        normalized = normalize_decision_payload(payload)

        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized.loc[0, "smiles"], "CCO")
        self.assertEqual(normalized.loc[0, "risk"], "high")


if __name__ == "__main__":
    unittest.main()
