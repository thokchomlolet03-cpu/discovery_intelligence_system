import unittest

from system.services.session_identity_service import build_metric_interpretation, build_session_identity


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

        self.assertTrue(any(item["label"] == "Applicability domain" for item in interpretation))
        model_judgment = next(item for item in interpretation if item["label"] == "Model judgment")
        self.assertIn("continuous estimate", model_judgment["text"])

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


if __name__ == "__main__":
    unittest.main()
