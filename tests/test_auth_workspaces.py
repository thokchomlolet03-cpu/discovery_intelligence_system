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
from system.db.repositories import ArtifactRepository, JobRepository, ReviewRepository, SessionRepository, UserRepository, WorkspaceRepository
from system.job_manager import DatabaseJobStore


class AuthWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        reset_database_state(f"sqlite:///{Path(self.tmpdir.name) / 'control_plane.db'}")
        ensure_database_ready()

        self.user_repository = UserRepository()
        self.workspace_repository = WorkspaceRepository()
        self.session_repository = SessionRepository()
        self.job_repository = JobRepository()
        self.review_repository = ReviewRepository()
        self.artifact_repository = ArtifactRepository()

        self.user_a = self.user_repository.create_user(
            email="owner_a@example.com",
            password_hash=hash_password("secret123"),
            display_name="Owner A",
        )
        self.workspace_a = self.workspace_repository.create_workspace(
            name="Workspace A",
            owner_user_id=self.user_a["user_id"],
        )
        self.workspace_repository.add_membership(
            workspace_id=self.workspace_a["workspace_id"],
            user_id=self.user_a["user_id"],
            role="owner",
        )

        self.user_b = self.user_repository.create_user(
            email="owner_b@example.com",
            password_hash=hash_password("secret123"),
            display_name="Owner B",
        )
        self.workspace_b = self.workspace_repository.create_workspace(
            name="Workspace B",
            owner_user_id=self.user_b["user_id"],
        )
        self.workspace_repository.add_membership(
            workspace_id=self.workspace_b["workspace_id"],
            user_id=self.user_b["user_id"],
            role="owner",
        )

        self.client = TestClient(discovery_app.app)

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

    def _login(self, email: str, password: str = "secret123") -> None:
        login_page = self.client.get("/login")
        csrf_token = self._extract_csrf_token(login_page.text)
        response = self.client.post(
            "/login",
            data={"email": email, "password": password, "csrf_token": csrf_token, "next": "/upload"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)

    def _authenticated_csrf(self, path: str = "/upload") -> str:
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return self._extract_csrf_token(response.text)

    def test_authenticated_routes_require_login(self):
        page_response = self.client.get("/upload", follow_redirects=False)
        api_response = self.client.post("/api/upload/validate", json={"session_id": "missing", "mapping": {}}, follow_redirects=False)

        self.assertEqual(page_response.status_code, 303)
        self.assertIn("/login", page_response.headers["location"])
        self.assertEqual(api_response.status_code, 401)

    def test_repositories_scope_control_plane_records_by_workspace(self):
        self.session_repository.upsert_session(
            session_id="session_a",
            workspace_id=self.workspace_a["workspace_id"],
            created_by_user_id=self.user_a["user_id"],
            source_name="a.csv",
        )
        self.session_repository.upsert_session(
            session_id="session_b",
            workspace_id=self.workspace_b["workspace_id"],
            created_by_user_id=self.user_b["user_id"],
            source_name="b.csv",
        )
        job_a = self.job_repository.create_job(
            session_id="session_a",
            workspace_id=self.workspace_a["workspace_id"],
            created_by_user_id=self.user_a["user_id"],
            job_id="job_a",
            status="queued",
            created_at="2026-03-26T12:00:00+00:00",
            updated_at="2026-03-26T12:00:00+00:00",
        )
        self.review_repository.record_review(
            {
                "session_id": "session_a",
                "workspace_id": self.workspace_a["workspace_id"],
                "candidate_id": "cand_a",
                "smiles": "CCO",
                "action": "later",
                "status": "under review",
                "timestamp": "2026-03-26T12:00:00+00:00",
                "reviewed_at": "2026-03-26T12:00:00+00:00",
                "actor": "Owner A",
                "reviewer": "Owner A",
                "actor_user_id": self.user_a["user_id"],
                "metadata": {},
            }
        )
        artifact_path = Path(self.tmpdir.name) / "decision_output_a.json"
        artifact_path.write_text(json.dumps({"session_id": "session_a", "top_experiments": []}))
        self.artifact_repository.register_artifact(
            artifact_type="decision_output_json",
            path=artifact_path,
            session_id="session_a",
            workspace_id=self.workspace_a["workspace_id"],
            created_by_user_id=self.user_a["user_id"],
        )

        with self.assertRaises(FileNotFoundError):
            self.session_repository.get_session("session_a", workspace_id=self.workspace_b["workspace_id"])
        with self.assertRaises(FileNotFoundError):
            self.job_repository.get_job(job_a["job_id"], workspace_id=self.workspace_b["workspace_id"])

        reviews_a = self.review_repository.list_reviews(workspace_id=self.workspace_a["workspace_id"])
        reviews_b = self.review_repository.list_reviews(workspace_id=self.workspace_b["workspace_id"])
        artifacts_a = self.artifact_repository.list_artifacts(workspace_id=self.workspace_a["workspace_id"])
        artifacts_b = self.artifact_repository.list_artifacts(workspace_id=self.workspace_b["workspace_id"])

        self.assertEqual(len(reviews_a), 1)
        self.assertEqual(len(reviews_b), 0)
        self.assertEqual(len(artifacts_a), 1)
        self.assertEqual(len(artifacts_b), 0)

    def test_cross_workspace_job_access_is_denied(self):
        self.session_repository.upsert_session(
            session_id="session_a",
            workspace_id=self.workspace_a["workspace_id"],
            created_by_user_id=self.user_a["user_id"],
        )
        job = DatabaseJobStore().create_job(
            session_id="session_a",
            workspace_id=self.workspace_a["workspace_id"],
            created_by_user_id=self.user_a["user_id"],
        )

        self._login(self.user_b["email"])
        denied = self.client.get(f"/api/jobs/{job['job_id']}")
        self.assertEqual(denied.status_code, 404)

        self.client.post(
            "/logout",
            data={"csrf_token": self._authenticated_csrf()},
            follow_redirects=False,
        )
        self._login(self.user_a["email"])
        allowed = self.client.get(f"/api/jobs/{job['job_id']}")
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["job_id"], job["job_id"])

    def test_review_actions_capture_actor_identity(self):
        self.session_repository.upsert_session(
            session_id="session_a",
            workspace_id=self.workspace_a["workspace_id"],
            created_by_user_id=self.user_a["user_id"],
        )
        self._login(self.user_a["email"])

        with (
            patch.object(discovery_app, "load_decision_output", return_value={"top_experiments": []}),
            patch.object(discovery_app, "annotate_candidates_with_reviews", return_value=[]),
            patch.object(discovery_app, "persist_review_queue", return_value={"summary": {"counts": {}}}),
        ):
            response = self.client.post(
                "/api/reviews",
                json={
                    "session_id": "session_a",
                    "candidate_id": "cand_a",
                    "smiles": "CCO",
                    "action": "approve",
                    "status": "approved",
                    "note": "Approved for testing",
                },
                headers={"X-CSRF-Token": self._authenticated_csrf("/discovery")},
            )

        self.assertEqual(response.status_code, 200)
        reviews = self.review_repository.list_reviews(
            session_id="session_a",
            workspace_id=self.workspace_a["workspace_id"],
        )
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["actor_user_id"], self.user_a["user_id"])
        self.assertEqual(reviews[0]["workspace_id"], self.workspace_a["workspace_id"])

    def test_membership_removal_invalidates_authenticated_access(self):
        self._login(self.user_a["email"])
        self.workspace_repository.remove_membership(
            workspace_id=self.workspace_a["workspace_id"],
            user_id=self.user_a["user_id"],
        )

        page_response = self.client.get("/upload", follow_redirects=False)
        api_response = self.client.post(
            "/api/upload/validate",
            json={"session_id": "missing", "mapping": {}},
            headers={"X-CSRF-Token": "stale-token"},
            follow_redirects=False,
        )

        self.assertEqual(page_response.status_code, 303)
        self.assertIn("/login", page_response.headers["location"])
        self.assertEqual(api_response.status_code, 401)

    def test_logout_clears_authenticated_access(self):
        self._login(self.user_a["email"])
        response = self.client.post(
            "/logout",
            data={"csrf_token": self._authenticated_csrf()},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        follow_up = self.client.get("/upload", follow_redirects=False)
        self.assertEqual(follow_up.status_code, 303)
        self.assertIn("/login", follow_up.headers["location"])

    def test_inactive_user_session_fails_safely(self):
        self._login(self.user_a["email"])
        self.user_repository.set_user_active(self.user_a["user_id"], is_active=False)

        page_response = self.client.get("/upload", follow_redirects=False)
        api_response = self.client.get("/api/jobs/missing", follow_redirects=False)

        self.assertEqual(page_response.status_code, 303)
        self.assertIn("/login", page_response.headers["location"])
        self.assertEqual(api_response.status_code, 401)

    def test_cross_workspace_discovery_artifact_access_is_denied(self):
        self.session_repository.upsert_session(
            session_id="session_a",
            workspace_id=self.workspace_a["workspace_id"],
            created_by_user_id=self.user_a["user_id"],
        )
        artifact_path = Path(self.tmpdir.name) / "decision_output_session_a.json"
        artifact_path.write_text(
            json.dumps(
                {
                    "session_id": "session_a",
                    "iteration": 0,
                    "generated_at": "2026-03-26T12:00:00+00:00",
                    "summary": {"top_k": 0, "candidate_count": 0, "risk_counts": {}, "top_experiment_value": 0.0},
                    "top_experiments": [],
                }
            )
        )
        self.artifact_repository.register_artifact(
            artifact_type="decision_output_json",
            path=artifact_path,
            session_id="session_a",
            workspace_id=self.workspace_a["workspace_id"],
            created_by_user_id=self.user_a["user_id"],
        )

        self._login(self.user_b["email"])
        response = self.client.get("/api/discovery", params={"session_id": "session_a"})
        self.assertEqual(response.status_code, 404)

    def test_cross_workspace_review_action_is_denied(self):
        self.session_repository.upsert_session(
            session_id="session_a",
            workspace_id=self.workspace_a["workspace_id"],
            created_by_user_id=self.user_a["user_id"],
        )
        self._login(self.user_b["email"])

        response = self.client.post(
            "/api/reviews",
            json={
                "session_id": "session_a",
                "candidate_id": "cand_a",
                "smiles": "CCO",
                "action": "approve",
                "status": "approved",
            },
            headers={"X-CSRF-Token": self._authenticated_csrf("/discovery")},
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
