import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as discovery_app
from system.discovery_workbench import build_discovery_workbench


class DiscoveryWorkbenchTest(unittest.TestCase):
    def test_build_discovery_workbench_derives_missing_fields(self):
        decision_output = {
            "iteration": 3,
            "artifact_state": "ok",
            "source_path": "data/decision_output.json",
            "source_updated_at": "2026-03-25T12:00:00+00:00",
            "top_experiments": [
                {
                    "smiles": "CCO",
                    "confidence": 0.91,
                    "uncertainty": 0.1,
                    "novelty": 0.58,
                    "experiment_value": 0.72,
                }
            ],
        }

        workbench = build_discovery_workbench(
            decision_output=decision_output,
            analysis_report={"warnings": [], "top_level_recommendation_summary": "Start with the top candidate."},
            review_queue={},
            session_id=None,
            evaluation_summary={"selected_model": {"name": "rf_isotonic", "calibration_method": "isotonic"}},
            system_version="2.0.0",
        )

        self.assertEqual(workbench["state"]["kind"], "ready")
        self.assertEqual(workbench["summary"]["model_version"], "rf_isotonic:isotonic")
        self.assertEqual(workbench["summary"]["dataset_version"], "data_decision_output.json")

        candidate = workbench["candidates"][0]
        self.assertEqual(candidate["candidate_id"], "candidate_1")
        self.assertEqual(candidate["bucket"], "exploit")
        self.assertEqual(candidate["risk"], "low")
        self.assertEqual(candidate["status"], "suggested")
        self.assertEqual(candidate["provenance"], "Not available")
        self.assertTrue(candidate["explanation_lines"])

    def test_build_discovery_workbench_reports_error_state(self):
        workbench = build_discovery_workbench(
            decision_output={"artifact_state": "error", "top_experiments": []},
            analysis_report={},
            review_queue={},
            session_id=None,
            evaluation_summary={},
            system_version="2.0.0",
        )

        self.assertEqual(workbench["state"]["kind"], "error")


class DiscoveryRouteTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(discovery_app.app)

    def test_discovery_page_renders_workbench_sections(self):
        response = self.client.get("/discovery")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Discovery Results", response.text)
        self.assertIn("Filter And Sort", response.text)
        self.assertIn("Review Workflow Summary", response.text)

    def test_reviews_api_accepts_bulk_payload(self):
        reviews = [
            {
                "candidate_id": "cand_1",
                "smiles": "CCO",
                "action": "approve",
                "status": "approved",
                "note": "Looks reasonable",
                "reviewed_at": "2026-03-25T12:00:00+00:00",
                "reviewer": "qa",
            }
        ]

        with (
            patch.object(discovery_app, "record_review_actions", return_value=reviews) as mock_record,
            patch.object(discovery_app, "load_decision_output", return_value={"top_experiments": [{"candidate_id": "cand_1", "smiles": "CCO"}]}),
            patch.object(discovery_app, "annotate_candidates_with_reviews", side_effect=lambda candidates, session_id=None: candidates),
            patch.object(discovery_app, "persist_review_queue", return_value={"summary": {"counts": {"approved": 1}}}),
        ):
            response = self.client.post(
                "/api/reviews",
                json={
                    "session_id": "session_1",
                    "items": [{"candidate_id": "cand_1", "smiles": "CCO", "action": "approve", "status": "approved"}],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("reviews", response.json())
        mock_record.assert_called_once()


if __name__ == "__main__":
    unittest.main()
