import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from system.db import ensure_database_ready, reset_database_state
from system.db.repositories import BeliefUpdateRepository, ClaimRepository
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

    def _claim_payload(self, *, session_id: str, candidate_id: str, smiles: str) -> dict[str, object]:
        timestamp = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
        return {
            "claim_id": "",
            "workspace_id": "workspace_1",
            "session_id": session_id,
            "candidate_id": candidate_id,
            "candidate_reference": {
                "candidate_id": candidate_id,
                "candidate_label": f"{candidate_id} ({smiles})",
                "canonical_smiles": smiles,
                "smiles": smiles,
                "rank": 1,
            },
            "target_definition_snapshot": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
            },
            "claim_type": "recommendation_assertion",
            "claim_text": f"Under the current session evidence, {candidate_id} ({smiles}) is a plausible follow-up candidate to test for higher pIC50.",
            "bounded_scope": "Bounded scope.",
            "support_level": "limited",
            "evidence_basis_summary": "Derived from current session evidence.",
            "source_recommendation_rank": 1,
            "status": "proposed",
            "created_at": timestamp,
            "updated_at": timestamp,
            "created_by": "system",
            "created_by_user_id": "",
            "reviewed_at": None,
            "reviewed_by": "",
            "metadata": {},
        }

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
        self.assertEqual(observed_rule["support_level"], "limited")
        self.assertTrue(observed_rule["eligible_for_recommendation_reuse"])
        self.assertTrue(observed_rule["eligible_for_ranking_context"])
        self.assertTrue(observed_rule["eligible_for_future_learning"])
        queue_rule = next(
            item for item in truth["evidence_activation_policy"]["rules"] if item["evidence_type"] == "learning_queue"
        )
        workspace_rule = next(
            item for item in truth["evidence_activation_policy"]["rules"] if item["evidence_type"] == "workspace_memory"
        )
        human_review_rule = next(
            item for item in truth["evidence_activation_policy"]["rules"] if item["evidence_type"] == "human_review"
        )
        self.assertEqual(workspace_rule["support_level"], "contextual")
        self.assertEqual(human_review_rule["support_level"], "contextual")
        self.assertEqual(queue_rule["support_level"], "limited")
        self.assertTrue(queue_rule["eligible_for_future_learning"])
        self.assertEqual(
            truth["evidence_activation_policy"]["source_class_label"],
            "User-uploaded uncontrolled source",
        )
        self.assertIn("recommendation reuse", truth["evidence_activation_policy"]["summary"].lower())
        self.assertIn(
            "future learning consideration",
            truth["evidence_activation_policy"]["future_learning_eligibility_summary"].lower(),
        )
        self.assertIn(
            "do not earn broader influence by volume",
            truth["evidence_activation_policy"]["anti_poisoning_summary"].lower(),
        )
        self.assertTrue(truth["controlled_reuse"]["recommendation_reuse_active"])
        self.assertTrue(truth["controlled_reuse"]["ranking_context_reuse_active"])
        self.assertTrue(truth["controlled_reuse"]["interpretation_support_active"])
        self.assertIn("does not change model outputs", truth["controlled_reuse"]["ranking_context_reuse_summary"].lower())
        self.assertIn("without retraining the model", truth["controlled_reuse"]["recommendation_reuse_summary"].lower())
        self.assertTrue(truth["comparison_ready"])

    def test_build_scientific_session_truth_adds_claim_read_across_from_prior_workspace_claims(self):
        repository = ClaimRepository()
        belief_update_repository = BeliefUpdateRepository()
        prior_claim_1 = repository.upsert_claim(
            self._claim_payload(session_id="session_prior", candidate_id="cand_1", smiles="CCO")
        )
        repository.upsert_claim(self._claim_payload(session_id="session_prior", candidate_id="cand_3", smiles="CCC"))
        repository.upsert_claim(self._claim_payload(session_id="session_prior", candidate_id="cand_4", smiles="CCCC"))
        repository.upsert_claim(self._claim_payload(session_id="session_current", candidate_id="cand_1", smiles="CCO"))
        repository.upsert_claim(self._claim_payload(session_id="session_current", candidate_id="cand_2", smiles="CCN"))
        belief_update_repository.upsert_belief_update(
            {
                "belief_update_id": "",
                "workspace_id": "workspace_1",
                "session_id": "session_prior",
                "claim_id": prior_claim_1["claim_id"],
                "experiment_result_id": "",
                "candidate_id": "cand_1",
                "candidate_label": "cand_1 (CCO)",
                "previous_support_level": "limited",
                "updated_support_level": "moderate",
                "update_direction": "strengthened",
                "update_reason": "Observed result linked to prior claim context.",
                "governance_status": "accepted",
                "created_at": datetime(2026, 4, 3, 11, 0, tzinfo=timezone.utc),
                "created_by": "system",
                "created_by_user_id": "",
                "metadata": {},
            }
        )

        truth = build_scientific_session_truth(
            session_id="session_current",
            workspace_id="workspace_1",
            source_name="upload.csv",
            session_record={
                "session_id": "session_current",
                "workspace_id": "workspace_1",
                "source_name": "upload.csv",
                "summary_metadata": {"last_job_status": "succeeded"},
            },
            analysis_report={
                "modeling_mode": "regression",
                "decision_intent": "prioritize_experiments",
                "target_definition": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                },
                "ranking_policy": {"primary_score": "confidence", "primary_score_label": "Ranking compatibility"},
                "run_contract": {"training_scope": "session_trained"},
                "comparison_anchors": {"comparison_ready": True},
            },
            decision_payload={"summary": {"candidate_count": 2}},
            review_queue={"summary": {"counts": {}}},
        )

        self.assertEqual(len(truth["claim_refs"]), 2)
        claim_refs = {item["candidate_id"]: item for item in truth["claim_refs"]}
        self.assertEqual(claim_refs["cand_1"]["claim_read_across_label"], "Continuity-aligned claim")
        self.assertEqual(claim_refs["cand_1"]["claim_prior_support_quality_label"], "Posture-governing continuity")
        self.assertEqual(claim_refs["cand_1"]["claim_prior_active_support_count"], 1)
        self.assertEqual(claim_refs["cand_1"]["claim_support_basis_mix_label"], "No governed support yet")
        self.assertEqual(claim_refs["cand_1"]["claim_actionability_label"], "No governed support yet")
        self.assertEqual(claim_refs["cand_2"]["claim_read_across_label"], "New claim context")
        self.assertEqual(truth["claims_summary"]["continuity_aligned_claim_count"], 1)
        self.assertEqual(truth["claims_summary"]["new_claim_context_count"], 1)
        self.assertEqual(truth["claims_summary"]["claims_with_active_governed_continuity_count"], 1)
        self.assertEqual(truth["claims_summary"]["claims_with_no_governed_support_count"], 2)
        self.assertIn("no governed support yet", truth["claims_summary"]["claim_support_basis_summary_text"].lower())
        self.assertEqual(truth["claims_summary"]["claims_with_insufficient_governed_basis_count"], 2)
        self.assertIn("claim actionability remains bounded", truth["claims_summary"]["claim_actionability_summary_text"].lower())
        self.assertIn("active-governed continuity", truth["claims_summary"]["read_across_summary_text"].lower())

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
        self.assertIn("belief_state_alignment_summary", loaded)


if __name__ == "__main__":
    unittest.main()
