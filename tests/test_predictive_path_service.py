import unittest

from system.services.predictive_path_service import build_predictive_path_summary


class PredictivePathServiceTest(unittest.TestCase):
    def test_build_predictive_path_summary_prefers_fresh_analysis_evaluation_over_stale_run_contract_snapshot(self):
        summary = build_predictive_path_summary(
            analysis_report={
                "measurement_summary": {"rows_with_values": 12, "rows_with_labels": 20},
                "ranking_diagnostics": {"score_basis": "priority_score", "spearman_rank_correlation": 0.41},
                "offline_ranking_evaluation": {
                    "evaluation_ready": True,
                    "evaluation_subset_summary": "3 reusable evaluation subsets are now recorded: Top shortlist, Signal-led cohort, Representation-supported cohort.",
                    "cross_session_comparison_summary": "Cross-session evaluation is anchored by pIC50, regression ranking, prioritize experiments, regression, balanced, and session trained.",
                    "representation_condition_summary": "Representation-conditioned evaluation suggests stronger-covered chemistry regions are more reliable in this run.",
                },
            },
            target_definition={"target_name": "pIC50", "target_kind": "regression"},
            modeling_mode="regression",
            run_contract={
                "training_scope": "session_trained",
                "feature_signature": "rdkit_descriptors_4_plus_morgan_fp_2048",
                "selected_model_name": "rf_regression",
                "predictive_evaluation_contract": {
                    "evaluation_subset_summary": "stale snapshot",
                    "cross_session_comparison_summary": "stale snapshot",
                    "representation_condition_summary": "stale snapshot",
                },
            },
            evaluation_summary={
                "selected_model": {"name": "rf_regression"},
                "metrics": {"holdout": {"rmse": 0.41, "mae": 0.27, "r2": 0.31}},
            },
        )

        self.assertIn("reusable evaluation subsets", summary["evaluation_contract"]["evaluation_subset_summary"].lower())
        self.assertIn("cross-session evaluation", summary["evaluation_contract"]["cross_session_comparison_summary"].lower())
        self.assertIn("representation-conditioned evaluation", summary["evaluation_contract"]["representation_condition_summary"].lower())

    def test_build_predictive_path_summary_surfaces_model_heuristic_and_governance_layers(self):
        summary = build_predictive_path_summary(
            analysis_report={
                "measurement_summary": {"rows_with_values": 12, "rows_with_labels": 20},
                "ranking_diagnostics": {
                    "score_basis": "priority_score",
                    "spearman_rank_correlation": 0.41,
                    "predicted_value_rank_correlation": 0.38,
                },
                "offline_ranking_evaluation": {
                    "evaluation_ready": True,
                    "candidate_separation_summary": "Candidate separation is usable but still bounded.",
                    "ranking_stability_summary": "Top-of-shortlist stability is bounded.",
                    "closeness_band_summary": "The shortlist contains a noticeable weak-separation band where nearby candidates are difficult to distinguish confidently.",
                    "top_k_quality_summary": "Top-k quality is usable but still bounded: the lead band shows mean raw signal 0.612 and bounded uncertainty 0.338.",
                    "heuristic_influence_summary": "Heuristic shortlist policy is doing substantial ranking work relative to the raw predictive signal.",
                    "sensitivity_summary": "Some candidates are being downweighted by representation support limits.",
                    "calibration_awareness_summary": "Regression ranking compatibility is not a calibrated probability. It is a bounded ordering signal and should be read together with dispersion and representation support.",
                    "calibration_band_summary": "Higher raw-signal bands do not yet map cleanly to stronger internal shortlist reliability, so score strength should stay bounded and relative.",
                    "comparison_cohort_summary": "Comparison cohort for this run is bounded by regression ranking, session trained, extra trees, and rdkit descriptors 4 plus morgan fp 2048.",
                    "cohort_diagnostic_summary": "A reusable signal-led cohort is now available for later version comparison.",
                    "evaluation_subset_summary": "3 reusable evaluation subsets are now recorded: Top shortlist, Signal-led cohort, Representation-supported cohort.",
                    "session_variation_summary": "Cross-session comparison is possible, but ranking reliability across session variation remains only partly established.",
                    "cross_session_comparison_summary": "Cross-session evaluation is anchored by pIC50, regression ranking, prioritize experiments, regression, balanced, and session trained. Reusable subsets: top_shortlist, signal_led.",
                    "version_comparison_summary": "Offline model comparison selected extra trees ahead of random forest for this run.",
                    "representation_support_summary": "Representation support still limits part of the shortlist, but most candidates remain within stronger chemistry coverage.",
                    "representation_evaluation_summary": "Representation-aware evaluation suggests stronger chemistry coverage improves ranking quality in this run.",
                    "representation_condition_summary": "Representation-conditioned evaluation suggests stronger-covered chemistry regions are more reliable in this run.",
                    "cross_run_comparison_summary": "Cross-run comparison is anchored by regression ranking, session trained, extra trees, and rdkit descriptors 4 plus morgan fp 2048.",
                    "engine_strength_summary": "Engine strengths are becoming more reusable: signal-led cohorts are now reusable across runs.",
                    "engine_weakness_summary": "Engine weaknesses remain visible: representation-limited cohorts still degrade ranking quality.",
                },
            },
            decision_payload={"summary": {"candidate_count": 15}},
            scientific_truth={
                "belief_state_summary": {
                    "support_coherence_summary": "Contradiction-heavy current posture still weakens broader carryover.",
                },
                "scientific_decision_summary": {
                    "decision_status_summary": "Session remains locally useful.",
                    "carryover_guardrail_summary": "Weak local multiplicity does not simulate approved session-family carryover.",
                    "session_family_review_status_summary": "Session-family carryover remains deferred.",
                },
            },
            ranking_policy={
                "primary_score": "priority_score",
                "primary_score_label": "Priority score",
                "formula_text": "priority_score combines confidence, uncertainty, novelty, and experiment value.",
                "formula_summary": "Candidate order prioritizes priority score first.",
                "weight_breakdown": [
                    {"label": "Confidence", "weight": 0.4, "weight_percent": 40.0},
                    {"label": "Experiment value", "weight": 0.3, "weight_percent": 30.0},
                    {"label": "Novelty", "weight": 0.2, "weight_percent": 20.0},
                ],
            },
            target_definition={"target_name": "pIC50", "target_kind": "regression"},
            modeling_mode="regression",
            run_contract={
                "training_scope": "session_trained",
                "feature_signature": "rdkit_descriptors_4_plus_morgan_fp_2048",
                "label_source": "continuous_measurement",
                "selected_model_name": "rf_regression",
            },
            evaluation_summary={
                "selected_model": {"name": "rf_regression", "calibration_method": ""},
                "model_family": "extra_trees",
                "metrics": {
                    "holdout": {
                        "rmse": 0.41,
                        "mae": 0.27,
                        "r2": 0.31,
                        "spearman_rank_correlation": 0.36,
                    }
                },
                "benchmark": [],
            },
        )

        self.assertIn("predictive task is now explicit", summary["summary_text"].lower())
        self.assertIn("confidence", summary["ranking_driver_summary"].lower())
        self.assertIn("priority score", summary["heuristic_logic_summary"].lower())
        self.assertIn("carryover", summary["governance_influence_summary"].lower())
        self.assertIn("feature contract", summary["representation_input_summary"].lower())
        self.assertIn("predicted value", summary["model_signal_summary"].lower())
        self.assertIn("final user-facing ordering", summary["final_ordering_summary"].lower())
        self.assertIn("holdout rmse", summary["evaluation_contract"]["evaluation_summary"].lower())
        self.assertTrue(summary["evaluation_contract"]["evaluation_ready"])
        self.assertIn("candidate separation", summary["evaluation_contract"]["candidate_separation_summary"].lower())
        self.assertIn("top-of-shortlist", summary["evaluation_contract"]["ranking_stability_summary"].lower())
        self.assertIn("weak-separation band", summary["evaluation_contract"]["closeness_band_summary"].lower())
        self.assertIn("top-k quality", summary["evaluation_contract"]["top_k_quality_summary"].lower())
        self.assertIn("not a calibrated probability", summary["evaluation_contract"]["calibration_awareness_summary"].lower())
        self.assertIn("higher raw-signal bands", summary["evaluation_contract"]["calibration_band_summary"].lower())
        self.assertIn("comparison cohort", summary["evaluation_contract"]["comparison_cohort_summary"].lower())
        self.assertIn("signal-led cohort", summary["evaluation_contract"]["cohort_diagnostic_summary"].lower())
        self.assertIn("reusable evaluation subsets", summary["evaluation_contract"]["evaluation_subset_summary"].lower())
        self.assertIn("session variation", summary["evaluation_contract"]["session_variation_summary"].lower())
        self.assertIn("cross-session evaluation", summary["evaluation_contract"]["cross_session_comparison_summary"].lower())
        self.assertIn("extra trees", summary["evaluation_contract"]["version_comparison_summary"].lower())
        self.assertIn("representation support", summary["evaluation_contract"]["representation_support_summary"].lower())
        self.assertIn("representation-aware evaluation", summary["evaluation_contract"]["representation_evaluation_summary"].lower())
        self.assertIn("representation-conditioned evaluation", summary["evaluation_contract"]["representation_condition_summary"].lower())
        self.assertIn("cross-run comparison", summary["evaluation_contract"]["cross_run_comparison_summary"].lower())
        self.assertIn("engine strengths", summary["evaluation_contract"]["engine_strength_summary"].lower())
        self.assertIn("engine weaknesses", summary["evaluation_contract"]["engine_weakness_summary"].lower())
        self.assertIn("heuristic shortlist policy", summary["failure_mode_summary"]["summary_text"].lower())
        self.assertEqual(summary["task_contract"]["predictive_score_label"], "Priority score")
        self.assertEqual(len(summary["next_phase_entry_criteria"]), 3)


if __name__ == "__main__":
    unittest.main()
