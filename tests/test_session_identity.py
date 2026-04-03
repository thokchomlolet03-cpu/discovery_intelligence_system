import unittest

from system.services.session_identity_service import build_metric_interpretation, build_session_identity, build_trust_context


class SessionIdentityServiceTest(unittest.TestCase):
    def test_builds_identity_for_legacy_classification_session(self):
        identity = build_session_identity(
            session_record={
                "session_id": "session_1",
                "workspace_id": "workspace_1",
                "source_name": "upload.csv",
                "created_at": "2026-03-25T12:00:00+00:00",
                "summary_metadata": {
                    "last_job_status": "succeeded",
                },
            },
            upload_metadata={
                "session_id": "session_1",
                "filename": "upload.csv",
                "selected_mapping": {"smiles": "smiles", "biodegradable": "biodegradable"},
                "validation_summary": {
                    "rows_with_labels": 10,
                    "rows_with_values": 0,
                    "rows_without_values": 10,
                },
            },
            analysis_report={
                "decision_intent": "prioritize_experiments",
                "modeling_mode": "binary_classification",
                "top_level_recommendation_summary": "Start with the highest-confidence shortlist candidate.",
            },
            decision_payload={
                "artifact_state": "ok",
                "summary": {"candidate_count": 4},
            },
        )

        self.assertIsNotNone(identity)
        self.assertEqual(identity["target_definition"]["target_name"], "biodegradability")
        self.assertEqual(identity["target_definition"]["target_kind"], "classification")
        self.assertEqual(identity["modeling_mode"], "binary_classification")
        self.assertEqual(identity["session_status"], "results_ready")
        self.assertEqual(identity["evidence_support_label"], "Moderate evidence support")
        self.assertIn("class labels", identity["evidence_summary"].lower())

    def test_builds_identity_for_measurement_regression_session(self):
        identity = build_session_identity(
            session_record={
                "session_id": "session_2",
                "workspace_id": "workspace_1",
                "source_name": "potency.csv",
                "created_at": "2026-03-25T12:00:00+00:00",
                "summary_metadata": {"last_job_status": "succeeded"},
            },
            upload_metadata={
                "session_id": "session_2",
                "filename": "potency.csv",
                "selected_mapping": {"smiles": "smiles", "value": "pic50"},
                "validation_summary": {
                    "rows_with_labels": 0,
                    "rows_with_values": 12,
                    "value_column": "pic50",
                },
            },
            analysis_report={
                "modeling_mode": "regression",
                "decision_intent": "prioritize_experiments",
                "target_definition": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_column": "pic50",
                    "scientific_meaning": "Higher predicted values are treated as more favorable for pIC50.",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                    "success_definition": "Success means prioritizing molecules expected to achieve higher pIC50 values.",
                },
                "measurement_summary": {"rows_with_values": 12},
            },
            decision_payload={"artifact_state": "ok", "summary": {"candidate_count": 3}},
        )

        self.assertIsNotNone(identity)
        self.assertEqual(identity["target_definition"]["target_kind"], "regression")
        self.assertEqual(identity["modeling_mode"], "regression")
        self.assertIn("continuous", identity["scientific_purpose"].lower())
        self.assertEqual(identity["evidence_support_label"], "Stronger evidence support")
        self.assertIn("observed values", identity["evidence_summary"].lower())

    def test_build_metric_interpretation_distinguishes_regression_semantics(self):
        interpretation = build_metric_interpretation(
            target_definition={
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
            },
            modeling_mode="regression",
            ranking_policy={"primary_score_label": "Priority score"},
        )

        self.assertTrue(any(item["label"] == "Observed or derived data facts" for item in interpretation))
        self.assertTrue(any(item["label"] == "Applicability and novelty" for item in interpretation))
        model_judgment = next(item for item in interpretation if item["label"] == "Model judgment")
        self.assertIn("continuous estimate", model_judgment["text"])
        self.assertIn("ranking compatibility", model_judgment["text"].lower())

    def test_builds_identity_for_failed_viewable_session_with_cautious_trust_summary(self):
        identity = build_session_identity(
            session_record={
                "session_id": "session_3",
                "workspace_id": "workspace_1",
                "source_name": "upload.csv",
                "created_at": "2026-03-25T12:00:00+00:00",
                "summary_metadata": {
                    "last_job_status": "failed",
                    "artifact_index": {
                        "decision_output_json": "/tmp/decision_output.json",
                    },
                },
            },
            upload_metadata={
                "session_id": "session_3",
                "filename": "upload.csv",
                "selected_mapping": {"smiles": "smiles", "biodegradable": "biodegradable"},
                "validation_summary": {
                    "can_run_analysis": True,
                    "rows_with_labels": 8,
                },
            },
            analysis_report={"artifact_state": "ok"},
            decision_payload={"artifact_state": "ok", "summary": {"candidate_count": 2}},
            current_job={
                "status": "failed",
                "progress_stage": "finalizing_artifacts",
                "error": "write failed after saving the decision package",
            },
        )

        self.assertEqual(identity["session_status"], "analysis_failed_viewable")
        self.assertIn("still viewable", identity["trust_summary"].lower())

    def test_builds_identity_with_bridge_state_summary_for_legacy_baseline_fallback(self):
        identity = build_session_identity(
            session_record={
                "session_id": "session_4",
                "workspace_id": "workspace_1",
                "source_name": "fallback.csv",
                "created_at": "2026-03-25T12:00:00+00:00",
                "summary_metadata": {"last_job_status": "succeeded"},
            },
            upload_metadata={
                "session_id": "session_4",
                "filename": "fallback.csv",
                "selected_mapping": {"smiles": "smiles"},
                "validation_summary": {"rows_with_labels": 0, "rows_with_values": 0},
            },
            analysis_report={
                "modeling_mode": "binary_classification",
                "decision_intent": "prioritize_experiments",
                "run_contract": {
                    "selected_model_name": "rf_model_v1",
                    "selected_model_family": "random_forest",
                    "training_scope": "baseline_bundle",
                    "scoring_mode": "balanced",
                    "reference_basis": {
                        "novelty_reference": "reference_dataset_similarity",
                        "applicability_reference": "reference_dataset_similarity",
                    },
                },
                "comparison_anchors": {
                    "comparison_ready": False,
                    "scoring_policy_version": "scoring_policy.v1",
                    "explanation_contract_version": "normalized_explanation.v1",
                },
            },
            decision_payload={"artifact_state": "ok", "summary": {"candidate_count": 2}},
        )

        self.assertEqual(identity["evidence_support_label"], "Limited evidence support")
        self.assertIn("legacy baseline bundle", identity["bridge_state_summary"].lower())

    def test_builds_identity_from_canonical_scientific_truth_when_present(self):
        identity = build_session_identity(
            session_record={
                "session_id": "session_truth",
                "workspace_id": "workspace_1",
                "source_name": "upload.csv",
                "created_at": "2026-03-25T12:00:00+00:00",
                "summary_metadata": {
                    "last_job_status": "succeeded",
                    "scientific_session_truth": {
                        "target_definition": {
                            "target_name": "pIC50",
                            "target_kind": "regression",
                            "optimization_direction": "maximize",
                            "measurement_column": "pic50",
                            "dataset_type": "measurement_dataset",
                            "mapping_confidence": "medium",
                            "scientific_meaning": "Higher predicted values are treated as more favorable.",
                            "success_definition": "Use higher values as more favorable guidance.",
                        },
                        "decision_intent": "prioritize_experiments",
                        "modeling_mode": "regression",
                        "run_contract": {"training_scope": "session_trained"},
                        "comparison_anchors": {"comparison_ready": True},
                    },
                },
            },
            analysis_report={},
            decision_payload={"artifact_state": "ok", "summary": {"candidate_count": 2}},
        )

        self.assertEqual(identity["target_definition"]["target_name"], "pIC50")
        self.assertEqual(identity["modeling_mode"], "regression")

    def test_build_trust_context_surfaces_selective_evidence_use_without_claiming_learning(self):
        trust = build_trust_context(
            target_definition={"target_name": "pIC50", "target_kind": "regression", "dataset_type": "measurement_dataset"},
            modeling_mode="regression",
            analysis_report={"measurement_summary": {"rows_with_values": 12}},
            decision_payload={},
            ranking_policy={"primary_score_label": "Ranking compatibility"},
            run_provenance={},
            scientific_truth={
                "evidence_activation_policy": {
                    "summary": "Ranking context currently uses Retrieved reference chemistry context and Predicted continuous values.",
                    "ranking_context_summary": "Active ranking context is currently limited to Retrieved reference chemistry context and Predicted continuous values.",
                    "interpretation_summary": "Recommendation interpretation currently uses Human review outcomes and Workspace feedback memory.",
                    "recommendation_reuse_summary": "Conservative recommendation reuse is currently eligible for Observed experimental values and Human review outcomes.",
                    "future_learning_eligibility_summary": "Future learning consideration is currently limited to Observed experimental values and Queued learning evidence.",
                    "permanently_non_active_summary": "Workspace feedback memory and Predicted continuous values are not eligible for stronger future activation.",
                },
                "controlled_reuse": {
                    "recommendation_reuse_active": True,
                    "ranking_context_reuse_active": True,
                    "interpretation_support_active": True,
                    "recommendation_reuse_summary": "Recommendation reuse is active from prior human review outcomes carried through workspace memory.",
                    "ranking_context_reuse_summary": "Ranking-context reuse is active for framing only and does not change the model score.",
                    "interpretation_support_summary": "Workspace feedback memory remains active as interpretation support.",
                },
            },
        )

        self.assertEqual(trust["activation_policy_label"], "Selective evidence use")
        self.assertIn("ranking context", trust["activation_policy_summary"].lower())
        self.assertIn("workspace feedback memory", trust["activation_policy_summary"].lower())
        self.assertEqual(trust["controlled_reuse_label"], "Controlled evidence reuse")
        self.assertIn("recommendation reuse is active", trust["controlled_reuse_summary"].lower())
        self.assertIn("does not change the model score", trust["controlled_reuse_summary"].lower())
        self.assertEqual(trust["future_eligibility_label"], "Future activation eligibility")
        self.assertIn("recommendation reuse", trust["future_eligibility_summary"].lower())
        self.assertIn("future learning consideration", trust["future_eligibility_summary"].lower())
        self.assertIn("not eligible for stronger future activation", trust["future_eligibility_summary"].lower())


if __name__ == "__main__":
    unittest.main()
