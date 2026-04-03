import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from system.db import ensure_database_ready, reset_database_state
from system.run_pipeline import run_pipeline
from tests.test_pipeline_services import canonical_decision_output


class ClaimPipelineIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        reset_database_state(f"sqlite:///{Path(self.tmpdir.name) / 'pipeline_claims.db'}")
        ensure_database_ready()

    def tearDown(self):
        reset_database_state()
        os.environ.pop("DISCOVERY_ALLOWED_ARTIFACT_ROOTS", None)
        self.tmpdir.cleanup()

    @patch("system.run_pipeline.build_discovery_result")
    @patch("system.run_pipeline.persist_review_queue")
    @patch("system.run_pipeline.build_prediction_result")
    def test_run_pipeline_adds_claims_and_experiment_requests_when_workspace_context_is_available(
        self,
        build_prediction_result_mock,
        persist_review_queue_mock,
        build_discovery_result_mock,
    ):
        session_id = "session_claim_pipeline"
        scored = pd.DataFrame([{"smiles": "CCO", "confidence": 0.91, "uncertainty": 0.10, "novelty": 0.58}])
        build_prediction_result_mock.return_value = (
            {
                "mode": "prediction",
                "message": "Ranked uploaded molecules for review using the current scoring workflow.",
                "summary": {"scored_candidates": 1},
                "top_candidates": [],
                "decision_output": canonical_decision_output(session_id),
            },
            scored,
            None,
        )
        persist_review_queue_mock.return_value = {
            "session_id": session_id,
            "generated_at": "2026-03-25T12:05:00+00:00",
            "summary": {"pending_review": 1, "approved": 0, "rejected": 0, "tested": 0, "ingested": 0, "counts": {}},
            "groups": {},
        }

        result = run_pipeline(
            pd.DataFrame([{"smiles": "CCO", "biodegradable": -1, "molecule_id": "mol_1", "source": "upload", "notes": ""}]),
            persist_artifacts=False,
            update_discovery_snapshot=False,
            seed=42,
            source_name="upload.csv",
            analysis_options={
                "session_id": session_id,
                "workspace_id": "workspace_1",
                "created_by_user_id": "user_1",
                "input_type": "structure_only_screening",
                "intent": "rank_uploaded_molecules",
                "scoring_mode": "balanced",
                "consent_learning": False,
                "column_mapping": {
                    "smiles": "smiles",
                    "biodegradable": "biodegradable",
                    "molecule_id": "molecule_id",
                    "source": "source",
                    "notes": "notes",
                },
            },
        )

        build_discovery_result_mock.assert_not_called()
        self.assertEqual(len(result["claims"]), 1)
        self.assertEqual(len(result["experiment_requests"]), 1)
        self.assertEqual(result["claims"][0]["session_id"], session_id)
        self.assertEqual(result["claims"][0]["workspace_id"], "workspace_1")
        self.assertEqual(result["experiment_requests"][0]["claim_id"], result["claims"][0]["claim_id"])
        self.assertEqual(result["scientific_session_truth"]["claims_summary"]["claim_count"], 1)
        self.assertEqual(result["scientific_session_truth"]["claim_refs"][0]["candidate_id"], "cand_1")
        self.assertEqual(result["scientific_session_truth"]["experiment_request_summary"]["request_count"], 1)
        self.assertEqual(result["scientific_session_truth"]["experiment_request_refs"][0]["candidate_id"], "cand_1")


if __name__ == "__main__":
    unittest.main()
