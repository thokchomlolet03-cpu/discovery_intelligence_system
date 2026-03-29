import io
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as discovery_app
from system.auth import hash_password
from system.billing import (
    FEATURE_CANDIDATE_GENERATION,
    FEATURE_DECISION_EXPORT,
    WorkspaceBillingService,
)
from system.contracts import WorkspaceUsageEventType
from system.db import ensure_database_ready, reset_database_state
from system.db.repositories import SessionRepository, UserRepository, WorkspaceRepository, WorkspaceUsageRepository
from system.job_manager import DatabaseJobStore


class BillingPlanTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        reset_database_state(f"sqlite:///{Path(self.tmpdir.name) / 'control_plane.db'}")
        ensure_database_ready()

        self.user_repository = UserRepository()
        self.workspace_repository = WorkspaceRepository()
        self.session_repository = SessionRepository()
        self.usage_repository = WorkspaceUsageRepository()
        self.billing_service = WorkspaceBillingService()

        self.user = self.user_repository.create_user(
            email="owner@example.com",
            password_hash=hash_password("secret123"),
            display_name="Owner",
        )
        self.workspace = self.workspace_repository.create_workspace(
            name="Workspace A",
            owner_user_id=self.user["user_id"],
        )
        self.workspace_repository.add_membership(
            workspace_id=self.workspace["workspace_id"],
            user_id=self.user["user_id"],
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

    def _login(self) -> None:
        response = self.client.get("/login")
        csrf_token = self._extract_csrf_token(response.text)
        login_response = self.client.post(
            "/login",
            data={"email": self.user["email"], "password": "secret123", "csrf_token": csrf_token, "next": "/upload"},
            follow_redirects=False,
        )
        self.assertEqual(login_response.status_code, 303)

    def _authenticated_csrf(self, path: str = "/upload") -> str:
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return self._extract_csrf_token(response.text)

    def _session_metadata(self, total_rows: int = 25) -> dict[str, object]:
        return {
            "session_id": "session_1",
            "filename": "upload.csv",
            "inferred_mapping": {"smiles": "smiles", "biodegradable": "biodegradable"},
            "validation_summary": {
                "total_rows": total_rows,
                "valid_smiles_count": total_rows,
                "invalid_smiles_count": 0,
                "duplicate_count": 0,
                "rows_with_labels": total_rows,
                "rows_without_labels": 0,
                "missing_fields": [],
                "warnings": [],
                "can_run_analysis": True,
            },
        }

    def _csv_bytes(self, rows: int) -> bytes:
        lines = ["smiles,biodegradable"]
        for index in range(rows):
            lines.append(f"CCO{index},1")
        return ("\n".join(lines) + "\n").encode("utf-8")

    def test_default_free_plan_and_internal_plan_entitlements(self):
        free_summary = self.billing_service.plan_summary(self.workspace)
        self.assertEqual(free_summary["plan_tier"], "free")
        self.assertEqual(free_summary["effective_plan_tier"], "free")
        self.assertFalse(free_summary["features"][FEATURE_CANDIDATE_GENERATION])
        self.assertEqual(free_summary["limits"]["max_upload_rows"], 250)

        self.workspace_repository.update_workspace_plan(self.workspace["workspace_id"], plan_tier="internal")
        internal_summary = self.billing_service.plan_summary(self.workspace["workspace_id"])
        self.assertEqual(internal_summary["effective_plan_tier"], "internal")
        self.assertTrue(internal_summary["features"][FEATURE_DECISION_EXPORT])
        self.assertIsNone(internal_summary["limits"]["monthly_analysis_jobs"])

    def test_usage_accounting_is_workspace_scoped(self):
        other_user = self.user_repository.create_user(
            email="other@example.com",
            password_hash=hash_password("secret123"),
            display_name="Other",
        )
        other_workspace = self.workspace_repository.create_workspace(
            name="Workspace B",
            owner_user_id=other_user["user_id"],
            plan_tier="pro",
        )
        self.workspace_repository.add_membership(
            workspace_id=other_workspace["workspace_id"],
            user_id=other_user["user_id"],
            role="owner",
        )

        self.usage_repository.record_event(
            workspace_id=self.workspace["workspace_id"],
            event_type=WorkspaceUsageEventType.analysis_job_created.value,
            quantity=2,
        )
        self.usage_repository.record_event(
            workspace_id=other_workspace["workspace_id"],
            event_type=WorkspaceUsageEventType.analysis_job_created.value,
            quantity=7,
        )

        free_summary = self.billing_service.plan_summary(self.workspace["workspace_id"])
        pro_summary = self.billing_service.plan_summary(other_workspace["workspace_id"])

        self.assertEqual(free_summary["usage"]["analysis_jobs_this_month"], 2)
        self.assertEqual(pro_summary["usage"]["analysis_jobs_this_month"], 7)

    def test_free_workspace_candidate_generation_is_blocked(self):
        self._login()
        with (
            patch.object(discovery_app, "load_session_metadata", return_value=self._session_metadata()),
            patch.object(discovery_app.job_manager, "start_analysis_job") as mock_start,
        ):
            response = self.client.post(
                "/upload",
                data={
                    "session_id": "session_1",
                    "csrf_token": self._authenticated_csrf(),
                    "input_type": "experimental_results",
                    "intent": "generate_candidates",
                    "scoring_mode": "balanced",
                    "consent_choice": "private",
                },
            )

        self.assertEqual(response.status_code, 403)
        body = response.json()
        self.assertEqual(body["code"], "feature_not_available")
        self.assertEqual(body["feature"], FEATURE_CANDIDATE_GENERATION)
        mock_start.assert_not_called()

    def test_pro_workspace_can_create_candidate_generation_job_and_records_usage(self):
        self.workspace_repository.update_workspace_plan(self.workspace["workspace_id"], plan_tier="pro")
        self._login()
        queued_job = DatabaseJobStore().create_job(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )

        with (
            patch.object(discovery_app, "load_session_metadata", return_value=self._session_metadata()),
            patch.object(discovery_app.job_manager, "start_analysis_job", return_value=queued_job) as mock_start,
        ):
            response = self.client.post(
                "/upload",
                data={
                    "session_id": "session_1",
                    "csrf_token": self._authenticated_csrf(),
                    "input_type": "experimental_results",
                    "intent": "generate_candidates",
                    "scoring_mode": "balanced",
                    "consent_choice": "private",
                },
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["job_id"], queued_job["job_id"])
        self.assertEqual(
            self.usage_repository.sum_quantity(
                workspace_id=self.workspace["workspace_id"],
                event_type=WorkspaceUsageEventType.analysis_job_created.value,
            ),
            1,
        )
        self.assertEqual(
            self.usage_repository.sum_quantity(
                workspace_id=self.workspace["workspace_id"],
                event_type=WorkspaceUsageEventType.candidate_generation_requested.value,
            ),
            1,
        )
        mock_start.assert_called_once()

    def test_free_workspace_monthly_analysis_limit_is_enforced(self):
        self._login()
        self.usage_repository.record_event(
            workspace_id=self.workspace["workspace_id"],
            event_type=WorkspaceUsageEventType.analysis_job_created.value,
            quantity=8,
        )

        with (
            patch.object(discovery_app, "load_session_metadata", return_value=self._session_metadata()),
            patch.object(discovery_app.job_manager, "start_analysis_job") as mock_start,
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

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "monthly_analysis_limit_exceeded")
        mock_start.assert_not_called()

    def test_free_workspace_upload_row_limit_is_enforced(self):
        self._login()
        response = self.client.post(
            "/api/upload/inspect",
            data={"csrf_token": self._authenticated_csrf(), "input_type": "experimental_results"},
            files={"file": ("oversized.csv", io.BytesIO(self._csv_bytes(300)), "text/csv")},
        )

        self.assertEqual(response.status_code, 413)
        body = response.json()
        self.assertEqual(body["code"], "upload_too_large")
        self.assertEqual(body["limit"], 250)
        self.assertEqual(self.session_repository.count_sessions(self.workspace["workspace_id"]), 0)

    def test_free_workspace_stored_session_limit_is_enforced(self):
        self._login()
        for index in range(5):
            self.session_repository.upsert_session(
                session_id=f"session_{index}",
                workspace_id=self.workspace["workspace_id"],
                created_by_user_id=self.user["user_id"],
                source_name=f"upload_{index}.csv",
                input_type="experimental_results",
            )

        response = self.client.post(
            "/api/upload/inspect",
            data={"csrf_token": self._authenticated_csrf(), "input_type": "experimental_results"},
            files={"file": ("small.csv", io.BytesIO(self._csv_bytes(2)), "text/csv")},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "session_limit_exceeded")

    def test_decision_export_is_gated_by_plan_and_recorded_for_pro(self):
        self._login()
        self.session_repository.upsert_session(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
            source_name="upload.csv",
            input_type="experimental_results",
        )

        denied = self.client.get("/api/discovery/download?session_id=session_1")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["feature"], FEATURE_DECISION_EXPORT)

        self.workspace_repository.update_workspace_plan(self.workspace["workspace_id"], plan_tier="pro")
        allowed = self.client.get("/api/discovery/download?session_id=session_1")
        self.assertEqual(allowed.status_code, 200)
        self.assertIn("attachment;", allowed.headers.get("content-disposition", "").lower())
        self.assertEqual(
            self.usage_repository.sum_quantity(
                workspace_id=self.workspace["workspace_id"],
                event_type=WorkspaceUsageEventType.decision_exported.value,
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
