import os
import tempfile
import unittest
from pathlib import Path

from system.db import ensure_database_ready, reset_database_state
from system.services.claim_service import create_session_claims
from system.services.experiment_request_service import (
    create_session_experiment_requests,
    list_session_experiment_requests,
)
from system.services.scientific_session_truth_service import build_scientific_session_truth


class ExperimentRequestServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        reset_database_state(f"sqlite:///{Path(self.tmpdir.name) / 'experiment_requests.db'}")
        ensure_database_ready()

    def tearDown(self):
        reset_database_state()
        os.environ.pop("DISCOVERY_ALLOWED_ARTIFACT_ROOTS", None)
        self.tmpdir.cleanup()

    def test_create_experiment_requests_persists_claim_derived_recommended_experiments(self):
        scientific_truth = {
            "session_id": "session_experiment_requests_1",
            "target_definition": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
            },
            "evidence_loop": {
                "active_modeling_evidence": ["Observed experimental values"],
                "active_ranking_evidence": ["Model predictions", "Retrieved reference chemistry context"],
            },
        }
        decision_payload = {
            "top_experiments": [
                {
                    "rank": 1,
                    "candidate_id": "cand_1",
                    "smiles": "CCO",
                    "canonical_smiles": "CCO",
                    "trust_label": "Stronger trust",
                    "rationale_primary_driver": "High ranking compatibility supports near-term testing.",
                    "domain_status": "in_domain",
                },
                {
                    "rank": 2,
                    "candidate_id": "cand_2",
                    "smiles": "CCN",
                    "canonical_smiles": "CCN",
                    "trust_label": "Mixed trust",
                    "rationale_primary_driver": "Prediction dispersion makes this a useful learning candidate.",
                    "domain_status": "near_boundary",
                },
            ]
        }
        claims = create_session_claims(
            session_id="session_experiment_requests_1",
            workspace_id="workspace_1",
            decision_payload=decision_payload,
            scientific_truth=scientific_truth,
            created_by_user_id="user_1",
        )

        created = create_session_experiment_requests(
            session_id="session_experiment_requests_1",
            workspace_id="workspace_1",
            claims=claims,
            decision_payload=decision_payload,
            requested_by_user_id="user_1",
        )
        recreated = create_session_experiment_requests(
            session_id="session_experiment_requests_1",
            workspace_id="workspace_1",
            claims=claims,
            decision_payload=decision_payload,
            requested_by_user_id="user_1",
        )

        requests = list_session_experiment_requests("session_experiment_requests_1", workspace_id="workspace_1")
        self.assertEqual(len(created), 2)
        self.assertEqual(len(recreated), 2)
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0]["status"], "proposed")
        self.assertEqual(requests[0]["requested_measurement"], "pIC50")
        self.assertEqual(requests[0]["priority_tier"], "high")
        self.assertIn("recommended next step", requests[0]["rationale_summary"].lower())
        self.assertIn("not scheduled or completed lab work", requests[0]["rationale_summary"].lower())
        self.assertEqual(requests[1]["priority_tier"], "medium")

    def test_scientific_session_truth_includes_experiment_request_refs_when_requests_exist(self):
        decision_payload = {
            "top_experiments": [
                {
                    "rank": 1,
                    "candidate_id": "cand_1",
                    "smiles": "CCO",
                    "canonical_smiles": "CCO",
                    "trust_label": "Stronger trust",
                    "rationale_primary_driver": "High ranking compatibility supports near-term testing.",
                    "domain_status": "in_domain",
                }
            ]
        }
        scientific_truth_seed = {
            "session_id": "session_experiment_requests_2",
            "target_definition": {
                "target_name": "solubility",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
            },
            "evidence_loop": {
                "active_modeling_evidence": ["Observed experimental values"],
                "active_ranking_evidence": ["Model predictions"],
            },
        }
        claims = create_session_claims(
            session_id="session_experiment_requests_2",
            workspace_id="workspace_1",
            decision_payload=decision_payload,
            scientific_truth=scientific_truth_seed,
            created_by_user_id="user_1",
        )
        create_session_experiment_requests(
            session_id="session_experiment_requests_2",
            workspace_id="workspace_1",
            claims=claims,
            decision_payload=decision_payload,
            requested_by_user_id="user_1",
        )

        truth = build_scientific_session_truth(
            session_id="session_experiment_requests_2",
            workspace_id="workspace_1",
            source_name="upload.csv",
            session_record={
                "session_id": "session_experiment_requests_2",
                "workspace_id": "workspace_1",
                "source_name": "upload.csv",
                "summary_metadata": {"last_job_status": "succeeded"},
            },
            analysis_report={
                "modeling_mode": "regression",
                "decision_intent": "prioritize_experiments",
                "target_definition": scientific_truth_seed["target_definition"],
                "ranking_policy": {"primary_score": "confidence", "primary_score_label": "Ranking compatibility"},
                "run_contract": {"training_scope": "session_trained"},
                "comparison_anchors": {"comparison_ready": True},
            },
            decision_payload={"summary": {"candidate_count": 1}, **decision_payload},
            review_queue={"summary": {"counts": {}}},
        )

        self.assertEqual(truth["experiment_request_summary"]["request_count"], 1)
        self.assertIn("recommend next experiments", truth["experiment_request_summary"]["summary_text"].lower())
        self.assertEqual(truth["experiment_request_refs"][0]["candidate_id"], "cand_1")


if __name__ == "__main__":
    unittest.main()
