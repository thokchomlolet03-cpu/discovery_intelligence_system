import os
import tempfile
import unittest
from pathlib import Path

from system.db import ensure_database_ready, reset_database_state
from system.services.belief_update_service import create_belief_update, list_session_belief_updates
from system.services.claim_service import create_session_claims
from system.services.experiment_request_service import create_session_experiment_requests, list_session_experiment_requests
from system.services.experiment_result_service import ingest_experiment_result
from system.services.scientific_session_truth_service import build_scientific_session_truth


class BeliefUpdateServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        reset_database_state(f"sqlite:///{Path(self.tmpdir.name) / 'belief_updates.db'}")
        ensure_database_ready()

    def tearDown(self):
        reset_database_state()
        os.environ.pop("DISCOVERY_ALLOWED_ARTIFACT_ROOTS", None)
        self.tmpdir.cleanup()

    def _seed_claim_request_result(self, session_id: str, *, observed_value=None, observed_label: str = ""):
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
            observed_value=observed_value,
            observed_label=observed_label,
            measurement_unit="log units",
            result_quality="confirmatory",
            ingested_by="Owner",
            ingested_by_user_id="user_1",
        )
        return claims[0], request, result

    def test_create_belief_update_strengthens_support_for_positive_observed_label(self):
        claim, _, result = self._seed_claim_request_result("session_belief_1", observed_label="positive")

        created = create_belief_update(
            session_id="session_belief_1",
            workspace_id="workspace_1",
            claim_id=claim["claim_id"],
            experiment_result_id=result["experiment_result_id"],
            created_by="Owner",
            created_by_user_id="user_1",
        )

        stored = list_session_belief_updates("session_belief_1", workspace_id="workspace_1")
        self.assertEqual(len(stored), 1)
        self.assertEqual(created["belief_update_id"], stored[0]["belief_update_id"])
        self.assertEqual(stored[0]["previous_support_level"], "moderate")
        self.assertEqual(stored[0]["updated_support_level"], "strong")
        self.assertEqual(stored[0]["update_direction"], "strengthened")
        self.assertEqual(stored[0]["governance_status"], "proposed")

    def test_numeric_only_result_keeps_support_unresolved_and_appears_in_scientific_truth(self):
        claim, _, result = self._seed_claim_request_result("session_belief_2", observed_value=6.8)
        create_belief_update(
            session_id="session_belief_2",
            workspace_id="workspace_1",
            claim_id=claim["claim_id"],
            experiment_result_id=result["experiment_result_id"],
            created_by="Owner",
            created_by_user_id="user_1",
        )

        truth = build_scientific_session_truth(
            session_id="session_belief_2",
            workspace_id="workspace_1",
            source_name="upload.csv",
            session_record={
                "session_id": "session_belief_2",
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

        self.assertEqual(truth["belief_update_summary"]["update_count"], 1)
        self.assertIn("belief update", truth["belief_update_summary"]["summary_text"].lower())
        self.assertEqual(truth["belief_update_refs"][0]["update_direction"], "unresolved")
        self.assertEqual(truth["belief_update_refs"][0]["updated_support_level"], "moderate")


if __name__ == "__main__":
    unittest.main()
