import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as discovery_app
from system.auth import hash_password
from system.db import ensure_database_ready, reset_database_state
from system.db.repositories import ArtifactRepository, SessionRepository, UserRepository, WorkspaceRepository
from system.job_manager import DatabaseJobStore, JobManager
from system.review_manager import latest_review_map, record_review_action, review_history_map


class DatabaseBackedTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        self.database_url = f"sqlite:///{Path(self.tmpdir.name) / 'control_plane.db'}"
        reset_database_state(self.database_url)
        ensure_database_ready()
        self.user = UserRepository().create_user(
            email="owner@example.com",
            password_hash=hash_password("secret123"),
            display_name="Owner",
        )
        self.workspace = WorkspaceRepository().create_workspace(
            name="Workspace A",
            owner_user_id=self.user["user_id"],
        )
        WorkspaceRepository().add_membership(
            workspace_id=self.workspace["workspace_id"],
            user_id=self.user["user_id"],
            role="owner",
        )

    def tearDown(self):
        reset_database_state()
        os.environ.pop("DISCOVERY_ALLOWED_ARTIFACT_ROOTS", None)
        self.tmpdir.cleanup()

    def _extract_csrf_token(self, text: str) -> str:
        match = re.search(r'name="csrf_token" value="([^"]+)"', text)
        if match:
            return match.group(1)
        meta = re.search(r'<meta name="csrf-token" content="([^"]*)"', text)
        self.assertIsNotNone(meta)
        return meta.group(1)


class JobManagerTest(DatabaseBackedTestCase):
    def test_job_creation_persists_job_and_session_metadata(self):
        store = DatabaseJobStore()
        session_repository = SessionRepository()

        job = store.create_job(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )
        persisted_job = store.get_job(job["job_id"], workspace_id=self.workspace["workspace_id"])
        persisted_session = session_repository.get_session("session_1", workspace_id=self.workspace["workspace_id"])

        self.assertEqual(persisted_job["job_id"], job["job_id"])
        self.assertEqual(persisted_job["status"], "queued")
        self.assertEqual(persisted_job["progress_stage"], "queued")
        self.assertEqual(persisted_job["progress_percent"], 0)
        self.assertEqual(persisted_session["session_id"], "session_1")
        self.assertEqual(persisted_session["latest_job_id"], job["job_id"])
        self.assertEqual(persisted_session["workspace_id"], self.workspace["workspace_id"])

    def test_job_lifecycle_transitions_to_succeeded_and_registers_artifacts(self):
        result_path = Path(self.tmpdir.name) / "result.json"
        result_path.write_text(json.dumps({"message": "done"}))

        def runner(dataframe, **kwargs):
            self.assertEqual(dataframe, "frame")
            self.assertEqual(kwargs["analysis_options"]["session_id"], "session_1")
            return {
                "message": "Analysis complete.",
                "mode": "prediction",
                "summary": {"analyzed_rows": 3},
                "warnings": ["warn"],
                "analysis_report": {"warnings": ["warn"]},
                "upload_session_summary": {"session_id": "session_1"},
                "artifacts": {"result_json": str(result_path)},
                "discovery_url": "/discovery?session_id=session_1",
                "dashboard_url": "/dashboard?session_id=session_1",
            }

        artifact_repository = ArtifactRepository()
        manager = JobManager(store=DatabaseJobStore(), pipeline_runner=runner, artifact_repository=artifact_repository)
        job = manager.store.create_job(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )

        with (
            patch("system.job_manager.load_session_metadata", return_value={"filename": "upload.csv"}),
            patch("system.job_manager.load_session_dataframe", return_value="frame"),
        ):
            manager.run_analysis_job(
                job_id=job["job_id"],
                source_name="upload.csv",
                analysis_options={"intent": "rank_uploaded_molecules", "input_type": "experimental_results"},
            )

        stored = manager.get_job(job["job_id"], workspace_id=self.workspace["workspace_id"])
        artifacts = artifact_repository.list_artifacts(
            session_id="session_1",
            job_id=job["job_id"],
            workspace_id=self.workspace["workspace_id"],
        )
        session_metadata = SessionRepository().get_session("session_1", workspace_id=self.workspace["workspace_id"])

        self.assertEqual(stored["status"], "succeeded")
        self.assertEqual(stored["progress_stage"], "completed")
        self.assertEqual(stored["progress_percent"], 100)
        self.assertEqual(stored["artifact_refs"]["result_json"], str(result_path))
        self.assertIn("result_json", {artifact["artifact_type"] for artifact in artifacts})
        self.assertEqual(session_metadata["summary_metadata"]["last_job_status"], "succeeded")

    def test_job_lifecycle_ignores_directory_artifact_refs(self):
        result_path = Path(self.tmpdir.name) / "result.json"
        result_path.write_text(json.dumps({"message": "done"}))
        run_dir = Path(self.tmpdir.name) / "session_dir"
        run_dir.mkdir()

        def runner(dataframe, **kwargs):
            self.assertEqual(dataframe, "frame")
            return {
                "message": "Analysis complete.",
                "mode": "prediction",
                "summary": {"analyzed_rows": 3},
                "warnings": [],
                "analysis_report": {"warnings": []},
                "upload_session_summary": {"session_id": "session_1"},
                "artifacts": {
                    "run_dir": str(run_dir),
                    "result_json": str(result_path),
                },
                "discovery_url": "/discovery?session_id=session_1",
                "dashboard_url": "/dashboard?session_id=session_1",
            }

        artifact_repository = ArtifactRepository()
        manager = JobManager(store=DatabaseJobStore(), pipeline_runner=runner, artifact_repository=artifact_repository)
        job = manager.store.create_job(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )

        with (
            patch("system.job_manager.load_session_metadata", return_value={"filename": "upload.csv"}),
            patch("system.job_manager.load_session_dataframe", return_value="frame"),
        ):
            manager.run_analysis_job(
                job_id=job["job_id"],
                source_name="upload.csv",
                analysis_options={"intent": "rank_uploaded_molecules", "input_type": "experimental_results"},
            )

        stored = manager.get_job(job["job_id"], workspace_id=self.workspace["workspace_id"])
        artifacts = artifact_repository.list_artifacts(
            session_id="session_1",
            job_id=job["job_id"],
            workspace_id=self.workspace["workspace_id"],
        )

        self.assertEqual(stored["status"], "succeeded")
        self.assertEqual(stored["progress_stage"], "completed")
        self.assertEqual(stored["progress_percent"], 100)
        self.assertEqual({artifact["artifact_type"] for artifact in artifacts}, {"result_json"})

    def test_job_lifecycle_transitions_to_failed_and_persists_error(self):
        def failing_runner(dataframe, **kwargs):
            raise ValueError("bad input for scientific pipeline")

        manager = JobManager(store=DatabaseJobStore(), pipeline_runner=failing_runner)
        job = manager.store.create_job(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )

        with (
            patch("system.job_manager.load_session_metadata", return_value={"filename": "upload.csv"}),
            patch("system.job_manager.load_session_dataframe", return_value="frame"),
        ):
            manager.run_analysis_job(
                job_id=job["job_id"],
                source_name="upload.csv",
                analysis_options={"intent": "rank_uploaded_molecules", "input_type": "experimental_results"},
            )

        stored = manager.get_job(job["job_id"], workspace_id=self.workspace["workspace_id"])
        session_metadata = SessionRepository().get_session("session_1", workspace_id=self.workspace["workspace_id"])
        self.assertEqual(stored["status"], "failed")
        self.assertGreaterEqual(stored["progress_percent"], 0)
        self.assertIn("ValueError", stored["error"])
        self.assertEqual(session_metadata["summary_metadata"]["last_job_status"], "failed")
        self.assertIn("bad input for scientific pipeline", session_metadata["summary_metadata"]["last_error"])

    def test_job_failure_sanitizes_sensitive_error_text(self):
        def failing_runner(dataframe, **kwargs):
            raise RuntimeError(f"could not read /tmp/secret/session_1.csv for job {kwargs['analysis_options']['session_id']}")

        manager = JobManager(store=DatabaseJobStore(), pipeline_runner=failing_runner)
        job = manager.store.create_job(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )

        with (
            patch("system.job_manager.load_session_metadata", return_value={"filename": "upload.csv"}),
            patch("system.job_manager.load_session_dataframe", return_value="frame"),
        ):
            manager.run_analysis_job(
                job_id=job["job_id"],
                source_name="upload.csv",
                analysis_options={"intent": "rank_uploaded_molecules", "input_type": "experimental_results"},
            )

        stored = manager.get_job(job["job_id"], workspace_id=self.workspace["workspace_id"])
        self.assertEqual(stored["status"], "failed")
        self.assertIn("RuntimeError", stored["error"])
        self.assertNotIn("/tmp/secret", stored["error"])
        self.assertIn("[path]", stored["error"])


class PersistenceRepositoryTest(DatabaseBackedTestCase):
    def test_session_metadata_is_persisted_and_retrievable(self):
        repository = SessionRepository()
        repository.upsert_session(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
            source_name="upload.csv",
            input_type="experimental_results",
            upload_metadata={"filename": "upload.csv", "validation_summary": {"total_rows": 4}},
            summary_metadata={"mode": "prediction"},
        )

        session_metadata = repository.get_session("session_1", workspace_id=self.workspace["workspace_id"])
        self.assertEqual(session_metadata["source_name"], "upload.csv")
        self.assertEqual(session_metadata["input_type"], "experimental_results")
        self.assertEqual(session_metadata["upload_metadata"]["filename"], "upload.csv")
        self.assertEqual(session_metadata["summary_metadata"]["mode"], "prediction")
        self.assertEqual(session_metadata["workspace_id"], self.workspace["workspace_id"])

    def test_artifact_metadata_pointer_is_stored_and_retrievable(self):
        repository = ArtifactRepository()
        artifact_path = Path(self.tmpdir.name) / "decision_output.json"
        artifact_path.write_text(json.dumps({"session_id": "session_1", "top_experiments": []}))

        repository.register_artifact(
            artifact_type="decision_output_json",
            path=artifact_path,
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
            metadata={"kind": "decision"},
        )

        stored_path = repository.get_latest_artifact_path(
            artifact_type="decision_output_json",
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
        )
        stored_artifacts = repository.list_artifacts(session_id="session_1", workspace_id=self.workspace["workspace_id"])
        self.assertEqual(stored_path, artifact_path.resolve())
        self.assertEqual(stored_artifacts[0]["artifact_type"], "decision_output_json")
        self.assertEqual(stored_artifacts[0]["metadata"]["kind"], "decision")


class ReviewPersistenceTest(DatabaseBackedTestCase):
    def test_review_records_and_status_transitions_are_persisted(self):
        first = record_review_action(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            candidate_id="cand_1",
            smiles="CCO",
            action="later",
            status="under review",
            note="Need a second look",
            reviewer="qa",
            actor_user_id=self.user["user_id"],
        )
        second = record_review_action(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            candidate_id="cand_1",
            smiles="CCO",
            action="approve",
            status="approved",
            note="Looks good",
            reviewer="qa",
            actor_user_id=self.user["user_id"],
        )

        key = "session_1::cand_1"
        latest = latest_review_map("session_1", workspace_id=self.workspace["workspace_id"])
        history = review_history_map("session_1", workspace_id=self.workspace["workspace_id"])

        self.assertEqual(first["status"], "under review")
        self.assertEqual(second["previous_status"], "under review")
        self.assertEqual(latest[key]["status"], "approved")
        self.assertEqual(len(history[key]), 2)
        self.assertEqual(second["actor_user_id"], self.user["user_id"])


class JobRouteTest(DatabaseBackedTestCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(discovery_app.app)
        login_page = self.client.get("/login")
        csrf_token = self._extract_csrf_token(login_page.text)
        response = self.client.post(
            "/login",
            data={"email": self.user["email"], "password": "secret123", "csrf_token": csrf_token, "next": "/upload"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)

    def _authenticated_csrf(self, path: str = "/upload") -> str:
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return self._extract_csrf_token(response.text)

    def test_upload_route_returns_job_handle_without_waiting_for_pipeline_completion(self):
        queued_job = DatabaseJobStore().create_job(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )

        with (
            patch.object(
                discovery_app,
                "load_session_metadata",
                return_value={
                    "filename": "upload.csv",
                    "inferred_mapping": {"smiles": "smiles", "biodegradable": "biodegradable"},
                },
            ),
            patch.object(discovery_app.job_manager, "start_analysis_job", return_value=queued_job) as mock_start,
        ):
            response = self.client.post(
                "/upload",
                data={
                    "session_id": "session_1",
                    "csrf_token": self._authenticated_csrf(),
                    "input_type": "experimental_results",
                    "intent": "rank_uploaded_molecules",
                    "scoring_mode": "balanced",
                    "consent_choice": "private",
                },
            )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["job_id"], queued_job["job_id"])
        self.assertEqual(body["status"], "queued")
        self.assertEqual(body["progress_stage"], "queued")
        self.assertEqual(body["progress_percent"], 0)
        self.assertIn("job_url", body)
        self.assertIn("result_url", body)
        mock_start.assert_called_once()

    def test_job_status_endpoint_returns_persisted_job_metadata(self):
        queued_job = DatabaseJobStore().create_job(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )

        with patch.object(discovery_app.job_manager, "get_job", return_value=queued_job):
            response = self.client.get(f"/api/jobs/{queued_job['job_id']}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["job_id"], queued_job["job_id"])
        self.assertEqual(body["status"], "queued")
        self.assertEqual(body["progress_stage"], "queued")
        self.assertEqual(body["progress_percent"], 0)
        self.assertEqual(body["job_url"], f"/api/jobs/{queued_job['job_id']}")

    def test_job_result_endpoint_returns_artifact_payload_when_job_succeeds(self):
        result_path = Path(self.tmpdir.name) / "result.json"
        result_path.write_text(json.dumps({"message": "Analysis complete.", "top_candidates": []}))
        succeeded_job = DatabaseJobStore().create_job(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )
        succeeded_job = discovery_app.job_manager.store.update_job(
            succeeded_job["job_id"],
            status="succeeded",
            progress_message="Analysis complete.",
            artifact_refs={"result_json": str(result_path)},
        )
        ArtifactRepository().register_artifact(
            artifact_type="result_json",
            path=result_path,
            session_id="session_1",
            job_id=succeeded_job["job_id"],
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )

        with patch.object(discovery_app.job_manager, "get_job", return_value=succeeded_job):
            response = self.client.get(f"/api/jobs/{succeeded_job['job_id']}/result")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Analysis complete.")

    def test_job_result_endpoint_ignores_unregistered_result_paths(self):
        external_result = Path(self.tmpdir.name) / "external_result.json"
        external_result.write_text(json.dumps({"message": "should not load"}))

        succeeded_job = DatabaseJobStore().create_job(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )
        discovery_app.job_manager.store.update_job(
            succeeded_job["job_id"],
            status="succeeded",
            progress_message="Analysis complete.",
            artifact_refs={"result_json": str(external_result)},
        )

        response = self.client.get(f"/api/jobs/{succeeded_job['job_id']}/result")
        self.assertEqual(response.status_code, 404)

    def test_csrf_is_required_for_state_changing_routes(self):
        response = self.client.post(
            "/api/upload/validate",
            json={"session_id": "missing", "mapping": {}},
        )
        self.assertEqual(response.status_code, 403)

    def test_artifact_repository_rejects_path_reassignment_across_workspaces(self):
        artifact_path = Path(self.tmpdir.name) / "decision_output.json"
        artifact_path.write_text(json.dumps({"session_id": "session_1", "top_experiments": []}))
        artifact_repository = ArtifactRepository()
        artifact_repository.register_artifact(
            artifact_type="decision_output_json",
            path=artifact_path,
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )

        other_user = UserRepository().create_user(
            email="other@example.com",
            password_hash=hash_password("secret123"),
            display_name="Other",
        )
        other_workspace = WorkspaceRepository().create_workspace(
            name="Workspace B",
            owner_user_id=other_user["user_id"],
        )
        WorkspaceRepository().add_membership(
            workspace_id=other_workspace["workspace_id"],
            user_id=other_user["user_id"],
            role="owner",
        )

        with self.assertRaises(ValueError):
            artifact_repository.register_artifact(
                artifact_type="decision_output_json",
                path=artifact_path,
                session_id="session_2",
                workspace_id=other_workspace["workspace_id"],
                created_by_user_id=other_user["user_id"],
            )


if __name__ == "__main__":
    unittest.main()
