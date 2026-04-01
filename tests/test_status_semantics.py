import unittest

from system.services.status_semantics_service import build_status_semantics, persisted_status_snapshot


class StatusSemanticsServiceTest(unittest.TestCase):
    def test_build_status_semantics_marks_validation_ready_when_analysis_can_run(self):
        semantics = build_status_semantics(
            session_record={
                "session_id": "session_1",
                "summary_metadata": {},
            },
            upload_metadata={
                "session_id": "session_1",
                "validation_summary": {
                    "can_run_analysis": True,
                    "total_rows": 12,
                    "valid_smiles_count": 11,
                },
            },
        )

        self.assertIsNotNone(semantics)
        self.assertEqual(semantics["status_code"], "validation_ready")
        self.assertTrue(semantics["usable_upload"])
        self.assertTrue(semantics["usable_validation"])
        self.assertFalse(semantics["viewable_artifacts"])
        self.assertTrue(semantics["rerun_possible"])

    def test_build_status_semantics_marks_failed_viewable_sessions_cautiously(self):
        semantics = build_status_semantics(
            session_record={
                "session_id": "session_2",
                "summary_metadata": {
                    "artifact_index": {
                        "analysis_report_json": "/tmp/analysis_report.json",
                        "decision_output_json": "/tmp/decision_output.json",
                    }
                },
            },
            upload_metadata={
                "session_id": "session_2",
                "validation_summary": {
                    "can_run_analysis": True,
                },
            },
            analysis_report={"artifact_state": "ok"},
            decision_payload={"artifact_state": "ok"},
            current_job={
                "status": "failed",
                "progress_stage": "finalizing_artifacts",
                "error": "Artifact write failed after partial persistence.",
            },
        )

        self.assertEqual(semantics["status_code"], "analysis_failed_viewable")
        self.assertEqual(semantics["where_failed"], "artifact_finalization")
        self.assertTrue(semantics["viewable_artifacts"])
        self.assertTrue(semantics["can_open_discovery"])
        self.assertTrue(semantics["can_open_dashboard"])
        self.assertFalse(semantics["trustworthy_recommendations"])
        self.assertIn("saved artifacts", semantics["headline"].lower())

    def test_build_status_semantics_marks_results_ready_when_decision_artifact_exists(self):
        semantics = build_status_semantics(
            session_record={"session_id": "session_3"},
            upload_metadata={
                "session_id": "session_3",
                "validation_summary": {"can_run_analysis": True},
            },
            decision_payload={
                "artifact_state": "ok",
                "summary": {"candidate_count": 3},
            },
        )

        self.assertEqual(semantics["status_code"], "results_ready")
        self.assertTrue(semantics["trustworthy_recommendations"])
        self.assertTrue(semantics["can_open_discovery"])
        self.assertTrue(semantics["can_open_dashboard"])

    def test_persisted_status_snapshot_tracks_running_and_failure_states(self):
        queued = persisted_status_snapshot(
            status="queued",
            progress_stage="queued",
            error="",
            viewable_artifacts=False,
        )
        running = persisted_status_snapshot(
            status="running",
            progress_stage="preparing_dataset",
            error="",
            viewable_artifacts=False,
        )
        failed = persisted_status_snapshot(
            status="failed",
            progress_stage="finalizing_artifacts",
            error="partial write failure",
            viewable_artifacts=True,
        )

        self.assertEqual(queued["status_code"], "analysis_queued")
        self.assertTrue(queued["usable_validation"])
        self.assertFalse(queued["rerun_possible"])
        self.assertEqual(running["status_code"], "analysis_running")
        self.assertEqual(running["status_tone"], "warning")
        self.assertEqual(failed["status_code"], "analysis_failed_viewable")
        self.assertEqual(failed["where_failed"], "artifact_finalization")
        self.assertTrue(failed["viewable_artifacts"])
        self.assertEqual(failed["last_error"], "partial write failure")


if __name__ == "__main__":
    unittest.main()
