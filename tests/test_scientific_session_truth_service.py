import os
import tempfile
import unittest
from pathlib import Path

from system.db import ensure_database_ready, reset_database_state
from system.session_artifacts import load_scientific_session_truth_payload
from system.services.scientific_session_truth_service import (
    build_scientific_session_truth,
    persist_scientific_session_truth,
)


class ScientificSessionTruthServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        reset_database_state(f"sqlite:///{Path(self.tmpdir.name) / 'control_plane.db'}")
        ensure_database_ready()

    def tearDown(self):
        reset_database_state()
        os.environ.pop("DISCOVERY_ALLOWED_ARTIFACT_ROOTS", None)
        self.tmpdir.cleanup()

    def test_build_scientific_session_truth_distinguishes_evidence_roles(self):
        truth = build_scientific_session_truth(
            session_id="session_truth_1",
            workspace_id="workspace_1",
            source_name="upload.csv",
            session_record={
                "session_id": "session_truth_1",
                "workspace_id": "workspace_1",
                "source_name": "upload.csv",
                "summary_metadata": {"last_job_status": "succeeded"},
            },
            upload_metadata={
                "session_id": "session_truth_1",
                "filename": "upload.csv",
                "validation_summary": {
                    "rows_with_values": 12,
                    "rows_with_labels": 0,
                    "semantic_mode": "measurement_dataset",
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
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                    "scientific_meaning": "Higher predicted values are treated as more favorable.",
                    "success_definition": "Use higher values as more favorable guidance.",
                },
                "measurement_summary": {
                    "rows_with_values": 12,
                    "rows_with_labels": 0,
                    "value_column": "pic50",
                },
                "ranking_policy": {
                    "primary_score": "confidence",
                    "primary_score_label": "Ranking compatibility",
                    "formula_label": "priority_score",
                    "formula_summary": "Priority combines ranking compatibility, uncertainty, novelty, and experiment value.",
                },
                "ranking_diagnostics": {"out_of_domain_rate": 0.25},
                "top_level_recommendation_summary": "Start with the strongest predicted-value shortlist candidate.",
                "warnings": [],
                "run_contract": {
                    "selected_model_name": "rf_regression",
                    "selected_model_family": "random_forest",
                    "training_scope": "session_trained",
                    "feature_signature": "rdkit_descriptors_plus_morgan_fp_2048",
                    "label_source": "continuous_measurement",
                    "reference_basis": {
                        "novelty_reference": "reference_dataset_similarity",
                        "applicability_reference": "reference_dataset_similarity",
                    },
                },
                "comparison_anchors": {"comparison_ready": True},
                "contract_versions": {"run_contract_version": "run_contract.v1"},
            },
            decision_payload={
                "summary": {"candidate_count": 3, "top_experiment_value": 0.74},
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
                "modeling_mode": "regression",
            },
            review_queue={
                "summary": {
                    "pending_review": 2,
                    "approved": 1,
                    "rejected": 0,
                    "tested": 0,
                    "ingested": 0,
                    "counts": {
                        "suggested": 2,
                        "under review": 1,
                        "approved": 1,
                        "rejected": 0,
                        "tested": 0,
                        "ingested": 0,
                    },
                }
            },
            workspace_memory={
                "matched_candidate_count": 2,
                "status_counts": {"approved": 1, "tested": 1},
            },
            feedback_store={"consent_learning": True, "queued_rows": 4},
        )

        evidence_types = {item["evidence_type"] for item in truth["evidence_records"]}
        self.assertIn("experimental_value", evidence_types)
        self.assertIn("chemistry_feature", evidence_types)
        self.assertIn("reference_context", evidence_types)
        self.assertIn("model_prediction", evidence_types)
        self.assertIn("human_review", evidence_types)
        self.assertIn("workspace_memory", evidence_types)
        self.assertIn("learning_queue", evidence_types)
        self.assertIn("Observed experimental values", truth["evidence_loop"]["active_modeling_evidence"])
        self.assertIn("Human review outcomes", truth["evidence_loop"]["future_activation_candidates"])
        self.assertIn("Workspace feedback memory", truth["evidence_loop"]["future_activation_candidates"])
        self.assertIn("Queued learning evidence", truth["evidence_loop"]["future_activation_candidates"])
        self.assertIn("memory-only", truth["evidence_loop"]["summary"].lower())
        self.assertIn("do not automatically retrain", truth["evidence_loop"]["learning_boundary_note"].lower())
        self.assertIn("future activation candidates", truth["evidence_loop"]["activation_boundary_summary"].lower())
        self.assertIn("ranking context currently uses", truth["evidence_activation_policy"]["summary"].lower())
        workspace_rule = next(
            item for item in truth["evidence_activation_policy"]["rules"] if item["evidence_type"] == "workspace_memory"
        )
        self.assertFalse(workspace_rule["model_training_allowed"])
        self.assertTrue(workspace_rule["interpretation_allowed"])
        self.assertTrue(workspace_rule["comparison_allowed"])
        self.assertTrue(workspace_rule["memory_only"])
        self.assertFalse(workspace_rule["future_learning_eligible"])
        self.assertFalse(workspace_rule["eligible_for_recommendation_reuse"])
        self.assertTrue(workspace_rule["permanently_non_active"])
        self.assertIn("continuity layer", workspace_rule["ineligibility_reason"].lower())
        observed_rule = next(
            item for item in truth["evidence_activation_policy"]["rules"] if item["evidence_type"] == "experimental_value"
        )
        self.assertTrue(observed_rule["eligible_for_recommendation_reuse"])
        self.assertTrue(observed_rule["eligible_for_ranking_context"])
        self.assertTrue(observed_rule["eligible_for_future_learning"])
        queue_rule = next(
            item for item in truth["evidence_activation_policy"]["rules"] if item["evidence_type"] == "learning_queue"
        )
        self.assertTrue(queue_rule["eligible_for_future_learning"])
        self.assertIn("recommendation reuse", truth["evidence_activation_policy"]["summary"].lower())
        self.assertIn(
            "future learning consideration",
            truth["evidence_activation_policy"]["future_learning_eligibility_summary"].lower(),
        )
        self.assertTrue(truth["controlled_reuse"]["recommendation_reuse_active"])
        self.assertTrue(truth["controlled_reuse"]["ranking_context_reuse_active"])
        self.assertTrue(truth["controlled_reuse"]["interpretation_support_active"])
        self.assertIn("does not change model outputs", truth["controlled_reuse"]["ranking_context_reuse_summary"].lower())
        self.assertIn("without retraining the model", truth["controlled_reuse"]["recommendation_reuse_summary"].lower())
        self.assertTrue(truth["comparison_ready"])

    def test_persisted_scientific_truth_can_be_loaded_from_artifact_or_session_metadata(self):
        truth = build_scientific_session_truth(
            session_id="session_truth_2",
            workspace_id="workspace_1",
            source_name="upload.csv",
            session_record={
                "session_id": "session_truth_2",
                "workspace_id": "workspace_1",
                "source_name": "upload.csv",
                "summary_metadata": {"last_job_status": "succeeded"},
            },
            analysis_report={
                "modeling_mode": "ranking_only",
                "decision_intent": "prioritize_experiments",
                "target_definition": {
                    "target_name": "target not recorded",
                    "target_kind": "classification",
                    "optimization_direction": "classify",
                    "dataset_type": "structure_only",
                    "mapping_confidence": "low",
                },
                "ranking_policy": {
                    "primary_score": "priority_score",
                    "primary_score_label": "Priority score",
                    "formula_label": "priority_score",
                    "formula_summary": "Policy-first ordering.",
                },
                "run_contract": {
                    "training_scope": "ranking_without_target_model",
                    "feature_signature": "rdkit_descriptors_plus_morgan_fp_2048",
                    "reference_basis": {
                        "novelty_reference": "reference_dataset_similarity",
                        "applicability_reference": "reference_dataset_similarity",
                    },
                },
                "comparison_anchors": {"comparison_ready": False},
            },
            decision_payload={"summary": {"candidate_count": 0}},
            review_queue={"summary": {"counts": {}}},
        )

        path = persist_scientific_session_truth(
            truth,
            session_id="session_truth_2",
            workspace_id="workspace_1",
            register_artifact=True,
        )

        self.assertTrue(Path(path).exists())
        loaded = load_scientific_session_truth_payload("session_truth_2", workspace_id="workspace_1", allow_global_fallback=False)
        self.assertEqual(loaded["artifact_state"], "ok")
        self.assertEqual(loaded["session_id"], "session_truth_2")
        self.assertIn("Current recommendations use", loaded["evidence_loop"]["summary"])


if __name__ == "__main__":
    unittest.main()
