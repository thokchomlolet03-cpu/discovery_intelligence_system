import os
import tempfile
import unittest
from pathlib import Path

from system.db import ensure_database_ready, reset_database_state
from system.services.claim_service import create_session_claims
from system.services.experiment_request_service import create_session_experiment_requests
from system.services.experiment_result_service import (
    experiment_result_refs_from_records,
    experiment_result_summary_from_records,
    ingest_experiment_result,
    list_session_experiment_results,
)
from system.services.scientific_session_truth_service import build_scientific_session_truth


class ExperimentResultServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        reset_database_state(f"sqlite:///{Path(self.tmpdir.name) / 'experiment_results.db'}")
        ensure_database_ready()

    def tearDown(self):
        reset_database_state()
        os.environ.pop("DISCOVERY_ALLOWED_ARTIFACT_ROOTS", None)
        self.tmpdir.cleanup()

    def _seed_claims_and_requests(self, session_id: str) -> list[dict]:
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
        return claims

    def test_ingest_experiment_result_persists_human_entered_observed_outcome(self):
        self._seed_claims_and_requests("session_results_1")
        experiment_requests = list_session_experiment_results(
            "session_results_1",
            workspace_id="workspace_1",
        )
        self.assertEqual(experiment_requests, [])

        from system.services.experiment_request_service import list_session_experiment_requests

        experiment_request = list_session_experiment_requests("session_results_1", workspace_id="workspace_1")[0]
        result = ingest_experiment_result(
            session_id="session_results_1",
            workspace_id="workspace_1",
            source_experiment_request_id=experiment_request["experiment_request_id"],
            observed_value=6.3,
            measurement_unit="log units",
            assay_context="screen_a repeat 1",
            result_quality="screening",
            ingested_by="Owner",
            ingested_by_user_id="user_1",
            notes="Manual lab readout entry.",
        )

        stored = list_session_experiment_results("session_results_1", workspace_id="workspace_1")
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["experiment_result_id"], result["experiment_result_id"])
        self.assertEqual(stored[0]["source_experiment_request_id"], experiment_request["experiment_request_id"])
        self.assertEqual(stored[0]["source_claim_id"], experiment_request["claim_id"])
        self.assertEqual(stored[0]["candidate_id"], "cand_1")
        self.assertEqual(stored[0]["observed_value"], 6.3)
        self.assertEqual(stored[0]["result_quality"], "screening")
        self.assertEqual(stored[0]["result_source"], "manual_entry")

    def test_scientific_session_truth_includes_experiment_result_refs_when_results_exist(self):
        self._seed_claims_and_requests("session_results_2")
        from system.services.experiment_request_service import list_session_experiment_requests

        experiment_request = list_session_experiment_requests("session_results_2", workspace_id="workspace_1")[0]
        ingest_experiment_result(
            session_id="session_results_2",
            workspace_id="workspace_1",
            source_experiment_request_id=experiment_request["experiment_request_id"],
            observed_value=6.8,
            measurement_unit="log units",
            result_quality="confirmatory",
            ingested_by="Owner",
            ingested_by_user_id="user_1",
        )

        truth = build_scientific_session_truth(
            session_id="session_results_2",
            workspace_id="workspace_1",
            source_name="upload.csv",
            session_record={
                "session_id": "session_results_2",
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

        self.assertEqual(truth["linked_result_summary"]["result_count"], 1)
        self.assertIn("observed result", truth["linked_result_summary"]["summary_text"].lower())
        self.assertEqual(truth["experiment_result_refs"][0]["candidate_id"], "cand_1")
        self.assertEqual(truth["experiment_result_refs"][0]["result_quality"], "confirmatory")

    def test_experiment_result_refs_capture_numeric_interpretation_and_quality_caution(self):
        results = [
            {
                "experiment_result_id": "result_1",
                "source_claim_id": "claim_1",
                "candidate_id": "cand_1",
                "candidate_reference": {"candidate_label": "cand_1 (CCO)"},
                "target_definition_snapshot": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_unit": "log units",
                    "derived_label_rule": {"operator": ">=", "threshold": 6.0},
                },
                "observed_value": 6.8,
                "measurement_unit": "log units",
                "result_quality": "confirmatory",
                "result_source": "manual_entry",
                "ingested_at": "2026-04-08T10:00:00+00:00",
            },
            {
                "experiment_result_id": "result_2",
                "source_claim_id": "claim_2",
                "candidate_id": "cand_2",
                "candidate_reference": {"candidate_label": "cand_2 (CCN)"},
                "target_definition_snapshot": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_unit": "log units",
                },
                "observed_value": 5.2,
                "measurement_unit": "wrong units",
                "assay_context": "screen_a",
                "result_quality": "screening",
                "result_source": "manual_entry",
                "ingested_at": "2026-04-08T10:05:00+00:00",
            },
        ]

        refs = experiment_result_refs_from_records(results)
        summary = experiment_result_summary_from_records(results)

        self.assertEqual(refs[0]["result_interpretation_label"], "Bounded numeric interpretation available")
        self.assertIn("current target rule", refs[0]["result_interpretation_summary"].lower())
        self.assertEqual(refs[0]["result_support_quality_label"], "Numeric-rule-based but limited")
        self.assertEqual(refs[0]["result_decision_usefulness_label"], "Useful for clarification, still limited")
        self.assertEqual(refs[1]["result_interpretation_label"], "Numeric result recorded, unresolved under current basis")
        self.assertIn("unresolved", refs[1]["result_interpretation_summary"].lower())
        self.assertIn("screening-quality caution", refs[1]["result_interpretation_summary"].lower())
        self.assertEqual(refs[1]["result_support_quality_label"], "Unresolved under current basis")
        self.assertEqual(summary["bounded_numeric_interpretation_count"], 1)
        self.assertEqual(summary["unresolved_numeric_interpretation_count"], 1)
        self.assertEqual(summary["cautious_result_quality_count"], 1)
        self.assertEqual(summary["assay_context_recorded_count"], 1)
        self.assertEqual(summary["limited_result_support_count"], 1)
        self.assertEqual(summary["unresolved_result_support_count"], 1)


if __name__ == "__main__":
    unittest.main()
