import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from system.auth import hash_password
from system.db import ensure_database_ready, reset_database_state
from system.db.repositories import ArtifactRepository, SessionRepository, UserRepository, WorkspaceRepository
from system.review_manager import record_review_action
from system.services.artifact_service import uploaded_session_dir
from system.upload_parser import load_session_dataframe, load_session_metadata


class HardeningBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        reset_database_state(f"sqlite:///{Path(self.tmpdir.name) / 'control_plane.db'}")
        ensure_database_ready()

        self.user_repository = UserRepository()
        self.workspace_repository = WorkspaceRepository()
        self.session_repository = SessionRepository()
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

    def tearDown(self):
        reset_database_state()
        os.environ.pop("DISCOVERY_ALLOWED_ARTIFACT_ROOTS", None)
        self.tmpdir.cleanup()

    def test_workspace_scoped_legacy_session_fallback_requires_owned_session(self):
        session_id = "legacy_session_a"
        session_path = uploaded_session_dir(session_id, create=True)
        self.addCleanup(lambda: shutil.rmtree(session_path, ignore_errors=True))

        self.session_repository.upsert_session(
            session_id=session_id,
            workspace_id=self.workspace_a["workspace_id"],
            created_by_user_id=self.user_a["user_id"],
            source_name="legacy.csv",
            input_type="experimental_results",
            upload_metadata={},
        )
        (session_path / "raw_upload.csv").write_text("smiles,biodegradable\nCCO,1\n", encoding="utf-8")
        (session_path / "inspect_summary.json").write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "created_at": "2026-03-26T12:00:00+00:00",
                    "filename": "legacy.csv",
                    "input_type": "experimental_results",
                    "columns": ["smiles", "biodegradable"],
                    "preview_rows": [{"smiles": "CCO", "biodegradable": "1"}],
                    "inferred_mapping": {"smiles": "smiles", "biodegradable": "biodegradable"},
                    "validation_summary": {
                        "total_rows": 1,
                        "valid_smiles_count": 1,
                        "invalid_smiles_count": 0,
                        "duplicate_count": 0,
                        "rows_with_labels": 1,
                        "rows_without_labels": 0,
                        "positive_label_count": 1,
                        "negative_label_count": 0,
                        "unlabeled_label_count": 0,
                        "label_counts": {"positive": 1, "negative": 0, "unlabeled": 0},
                        "missing_fields": [],
                        "warnings": [],
                        "can_run_analysis": True,
                    },
                    "free_tier_assessment": {},
                }
            ),
            encoding="utf-8",
        )

        metadata = load_session_metadata(session_id, workspace_id=self.workspace_a["workspace_id"])
        dataframe = load_session_dataframe(session_id, workspace_id=self.workspace_a["workspace_id"])

        self.assertEqual(metadata["filename"], "legacy.csv")
        self.assertEqual(len(dataframe), 1)

        with self.assertRaises(FileNotFoundError):
            load_session_metadata(session_id, workspace_id=self.workspace_b["workspace_id"])
        with self.assertRaises(FileNotFoundError):
            load_session_dataframe(session_id, workspace_id=self.workspace_b["workspace_id"])

    def test_review_transition_rejects_invalid_reversal_from_ingested(self):
        record_review_action(
            session_id="session_a",
            workspace_id=self.workspace_a["workspace_id"],
            candidate_id="cand_1",
            smiles="CCO",
            action="ingest",
            status="ingested",
            note="Added to the learning set",
            reviewer="Owner A",
            actor_user_id=self.user_a["user_id"],
        )

        with self.assertRaises(ValueError):
            record_review_action(
                session_id="session_a",
                workspace_id=self.workspace_a["workspace_id"],
                candidate_id="cand_1",
                smiles="CCO",
                action="approve",
                status="approved",
                note="Trying to move backwards",
                reviewer="Owner A",
                actor_user_id=self.user_a["user_id"],
            )

    def test_artifact_repository_rejects_paths_outside_allowed_roots(self):
        with self.assertRaises(ValueError):
            self.artifact_repository.register_artifact(
                artifact_type="result_json",
                path=Path("/etc/passwd"),
                session_id="session_a",
                workspace_id=self.workspace_a["workspace_id"],
                created_by_user_id=self.user_a["user_id"],
            )


if __name__ == "__main__":
    unittest.main()
