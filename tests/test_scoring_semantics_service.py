import unittest

import pandas as pd

from system.services.scoring_semantics_service import (
    attach_candidate_score_semantics,
    build_candidate_score_semantics,
    build_offline_ranking_evaluation,
)


class ScoringSemanticsServiceTest(unittest.TestCase):
    def test_build_candidate_score_semantics_separates_raw_policy_and_representation_layers(self):
        semantics = build_candidate_score_semantics(
            {
                "confidence": 0.74,
                "signal_support": 0.70,
                "heuristic_policy_score": 0.68,
                "priority_score": 0.63,
                "representation_support_factor": 0.93,
                "representation_adjustment": -0.05,
                "max_similarity": 0.34,
                "support_density": 0.31,
            },
            target_definition={"target_kind": "classification"},
            bundle={"training_scope": "session_trained", "metrics": {"holdout": {"balanced_accuracy": 0.69, "brier_score": 0.18}}},
        )

        self.assertGreater(semantics["raw_predictive_signal"], 0.72)
        self.assertAlmostEqual(semantics["heuristic_policy_score"], 0.68)
        self.assertAlmostEqual(semantics["final_priority_score"], 0.63)
        self.assertGreaterEqual(semantics["raw_signal_weight"], 0.58)
        self.assertLessEqual(semantics["heuristic_weight"], 0.42)
        self.assertIsNotNone(semantics["blended_priority_score"])
        self.assertIn(semantics["signal_status_label"].lower(), {"fragile signal", "bounded signal", "thinly supported signal", "stronger signal", "too close to separate strongly"})
        self.assertIn("bounded uncertainty", semantics["uncertainty_summary"].lower())
        self.assertIn("heuristic shortlist policy", semantics["heuristic_summary"].lower())
        self.assertIn("representation support", semantics["representation_summary"].lower())

    def test_attach_candidate_score_semantics_adds_bounded_representation_adjustment(self):
        frame = pd.DataFrame(
            [
                {
                    "confidence": 0.80,
                    "uncertainty": 0.25,
                    "novelty": 0.40,
                    "experiment_value": 0.50,
                    "priority_score": 0.66,
                    "max_similarity": 0.20,
                    "support_density": 0.18,
                }
            ]
        )

        enriched = attach_candidate_score_semantics(
            frame,
            target_definition={"target_kind": "classification"},
            bundle={"training_scope": "session_trained", "metrics": {"holdout": {"balanced_accuracy": 0.64}}},
        )

        self.assertIn("score_semantics", enriched.columns)
        self.assertLess(float(enriched.iloc[0]["priority_score"]), 0.66)
        self.assertAlmostEqual(float(enriched.iloc[0]["representation_support_factor"]), 0.80)
        self.assertGreater(float(enriched.iloc[0]["raw_signal_weight"]), 0.35)
        self.assertLess(float(enriched.iloc[0]["heuristic_weight"]), 0.65)
        self.assertIn("neighbor_gap", enriched.columns)
        self.assertIn("neighborhood density are weak", enriched.iloc[0]["score_semantics"]["representation_summary"].lower())
        self.assertIn("bounded uncertainty", enriched.iloc[0]["score_semantics"]["uncertainty_summary"].lower())

    def test_build_offline_ranking_evaluation_surfaces_separation_and_stability(self):
        frame = pd.DataFrame(
            [
                {"raw_predictive_signal": 0.78, "heuristic_policy_score": 0.74, "priority_score": 0.71, "representation_support_factor": 0.96, "raw_signal_weight": 0.62, "uncertainty": 0.22, "neighbor_gap": 0.010},
                {"raw_predictive_signal": 0.76, "heuristic_policy_score": 0.73, "priority_score": 0.70, "representation_support_factor": 0.96, "raw_signal_weight": 0.61, "uncertainty": 0.24, "neighbor_gap": 0.010},
                {"raw_predictive_signal": 0.52, "heuristic_policy_score": 0.66, "priority_score": 0.61, "representation_support_factor": 0.92, "raw_signal_weight": 0.58, "uncertainty": 0.31, "neighbor_gap": 0.050},
                {"raw_predictive_signal": 0.49, "heuristic_policy_score": 0.60, "priority_score": 0.56, "representation_support_factor": 0.85, "raw_signal_weight": 0.55, "uncertainty": 0.44, "neighbor_gap": 0.050},
            ]
        )

        evaluation = build_offline_ranking_evaluation(
            frame,
            target_definition={"target_kind": "classification"},
            bundle={
                "selected_model": {"name": "extra_trees_isotonic", "calibration_method": "isotonic"},
                "model_family": "extra_trees",
                "training_scope": "session_trained",
                "descriptor_features": ["mw", "rdkit_logp", "tpsa", "ring_count"],
                "fingerprint_bits": 2048,
                "metrics": {"holdout": {"brier_score": 0.18, "log_loss": 0.47}},
                "benchmark": [
                    {"name": "extra_trees_isotonic"},
                    {"name": "random_forest_isotonic"},
                ]
            },
        )

        self.assertTrue(evaluation["evaluation_ready"])
        self.assertIn("candidate-level separation", evaluation["evaluation_summary"].lower())
        self.assertIn("candidate separation", evaluation["candidate_separation_summary"].lower())
        self.assertIn("top-of-shortlist", evaluation["ranking_stability_summary"].lower())
        self.assertIn("too close", evaluation["closeness_band_summary"].lower())
        self.assertIn("raw predictive signal", evaluation["heuristic_influence_summary"].lower())
        self.assertIn("signal-relative", evaluation["calibration_awareness_summary"].lower())
        self.assertIn("higher raw-signal bands", evaluation["calibration_band_summary"].lower())
        self.assertIn("comparison cohort", evaluation["comparison_cohort_summary"].lower())
        self.assertIn("reusable", evaluation["cohort_diagnostic_summary"].lower())
        self.assertIn("reusable subset", evaluation["evaluation_subset_summary"].lower())
        self.assertIn("cross-session comparison", evaluation["session_variation_summary"].lower())
        self.assertIn("cross-session evaluation is anchored", evaluation["cross_session_comparison_summary"].lower())
        self.assertIn("selected extra_trees_isotonic", evaluation["version_comparison_summary"].lower())
        self.assertIn("representation support", evaluation["representation_support_summary"].lower())
        self.assertIn("representation-aware evaluation", evaluation["representation_evaluation_summary"].lower())
        self.assertIn("representation-conditioned evaluation", evaluation["representation_condition_summary"].lower())
        self.assertIn("cross-run comparison", evaluation["cross_run_comparison_summary"].lower())
        self.assertIn("engine strengths", evaluation["engine_strength_summary"].lower())
        self.assertIn("engine weaknesses", evaluation["engine_weakness_summary"].lower())
        self.assertTrue(evaluation["comparison_cohorts"])
        self.assertTrue(evaluation["evaluation_subsets"])
        self.assertTrue(evaluation["representation_condition_diagnostics"])
        self.assertTrue(evaluation["calibration_band_diagnostics"])
        self.assertIn("reusable_subset_keys", evaluation["cross_session_evaluation_contract"])
        self.assertIn("reusable_subset_keys", evaluation["cross_run_comparison_contract"])
        self.assertIn("reusable_subset_keys", evaluation["version_comparison_contract"])


if __name__ == "__main__":
    unittest.main()
