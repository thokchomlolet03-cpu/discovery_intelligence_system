import os
import tempfile
import unittest
from pathlib import Path

from system.db import ensure_database_ready, reset_database_state
from system.services.belief_state_service import get_belief_state_for_target
from system.services.belief_update_service import create_belief_update
from system.services.claim_service import create_session_claims
from system.services.experiment_request_service import create_session_experiment_requests, list_session_experiment_requests
from system.services.experiment_result_service import ingest_experiment_result
from system.services.scientific_session_truth_service import build_scientific_session_truth


class BeliefStateServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        reset_database_state(f"sqlite:///{Path(self.tmpdir.name) / 'belief_states.db'}")
        ensure_database_ready()

    def tearDown(self):
        reset_database_state()
        os.environ.pop("DISCOVERY_ALLOWED_ARTIFACT_ROOTS", None)
        self.tmpdir.cleanup()

    def _seed_claim_request_result(self, session_id: str, *, observed_label: str):
        decision_payload = {
            "top_experiments": [
                {
                    "rank": 1,
                    "candidate_id": "cand_1",
                    "smiles": "CCO",
                    "canonical_smiles": "CCO",
                    "trust_label": "Mixed trust",
                    "rationale_primary_driver": "High ranking compatibility supports near-term testing.",
                    "domain_status": "in_domain",
                }
            ]
        }
        scientific_truth = {
            "session_id": session_id,
            "target_definition": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "measurement_column": "pic50",
                "measurement_unit": "log units",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
            },
            "evidence_loop": {
                "active_modeling_evidence": ["Observed experimental values"],
                "active_ranking_evidence": ["Model predictions"],
            },
        }
        claims = create_session_claims(
            session_id=session_id,
            workspace_id="workspace_1",
            decision_payload=decision_payload,
            scientific_truth=scientific_truth,
            created_by_user_id="user_1",
        )
        create_session_experiment_requests(
            session_id=session_id,
            workspace_id="workspace_1",
            claims=claims,
            decision_payload=decision_payload,
            requested_by_user_id="user_1",
        )
        request = list_session_experiment_requests(session_id, workspace_id="workspace_1")[0]
        result = ingest_experiment_result(
            session_id=session_id,
            workspace_id="workspace_1",
            source_experiment_request_id=request["experiment_request_id"],
            observed_label=observed_label,
            measurement_unit="log units",
            result_quality="confirmatory",
            ingested_by="Owner",
            ingested_by_user_id="user_1",
        )
        return claims[0], result, scientific_truth["target_definition"]

    def test_create_belief_update_refreshes_target_scoped_belief_state(self):
        claim, result, target_definition = self._seed_claim_request_result("session_state_1", observed_label="positive")

        create_belief_update(
            session_id="session_state_1",
            workspace_id="workspace_1",
            claim_id=claim["claim_id"],
            experiment_result_id=result["experiment_result_id"],
            created_by="Owner",
            created_by_user_id="user_1",
        )

        belief_state = get_belief_state_for_target(
            workspace_id="workspace_1",
            target_definition_snapshot=target_definition,
        )
        self.assertIsNotNone(belief_state)
        self.assertEqual(belief_state["active_claim_count"], 1)
        self.assertEqual(belief_state["supported_claim_count"], 1)
        self.assertEqual(belief_state["weakened_claim_count"], 0)
        self.assertEqual(belief_state["unresolved_claim_count"], 0)
        self.assertIn("bounded support summary", belief_state["summary_text"].lower())

    def test_scientific_session_truth_carries_belief_state_summary_when_available(self):
        claim, result, _ = self._seed_claim_request_result("session_state_2", observed_label="negative")
        create_belief_update(
            session_id="session_state_2",
            workspace_id="workspace_1",
            claim_id=claim["claim_id"],
            experiment_result_id=result["experiment_result_id"],
            created_by="Owner",
            created_by_user_id="user_1",
        )

        truth = build_scientific_session_truth(
            session_id="session_state_2",
            workspace_id="workspace_1",
            source_name="upload.csv",
            session_record={
                "session_id": "session_state_2",
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
                    "measurement_column": "pic50",
                    "measurement_unit": "log units",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                },
                "ranking_policy": {"primary_score": "confidence", "primary_score_label": "Ranking compatibility"},
                "run_contract": {"training_scope": "session_trained"},
                "comparison_anchors": {"comparison_ready": True},
            },
            decision_payload={"summary": {"candidate_count": 1}, "top_experiments": []},
            review_queue={"summary": {"counts": {}}},
        )

        self.assertEqual(truth["belief_state_summary"]["active_claim_count"], 1)
        self.assertEqual(truth["belief_state_summary"]["weakened_claim_count"], 1)
        self.assertIn("current belief state", truth["belief_state_summary"]["summary_text"].lower())
        self.assertTrue(truth["belief_state_ref"]["target_key"])


if __name__ == "__main__":
    unittest.main()
