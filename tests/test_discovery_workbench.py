import unittest
import os
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as discovery_app
from system.auth import hash_password
from system.db import ensure_database_ready, reset_database_state
from system.db.repositories import ArtifactRepository, SessionRepository, UserRepository, WorkspaceRepository
from system.discovery_workbench import build_discovery_workbench


def canonical_decision_output() -> dict:
    return {
        "session_id": "session_1",
        "iteration": 3,
        "generated_at": "2026-03-25T12:00:00+00:00",
        "artifact_state": "ok",
        "source_path": "data/decision_output.json",
        "source_updated_at": "2026-03-25T12:00:00+00:00",
        "summary": {
            "top_k": 1,
            "candidate_count": 1,
            "risk_counts": {"low": 1},
            "top_experiment_value": 0.72,
        },
        "top_experiments": [
            {
                "session_id": "session_1",
                "rank": 1,
                "candidate_id": "cand_1",
                "smiles": "CCO",
                "canonical_smiles": "CCO",
                "confidence": 0.91,
                "uncertainty": 0.1,
                "novelty": 0.58,
                "acquisition_score": 0.77,
                "experiment_value": 0.72,
                "priority_score": 0.78,
                "bucket": "exploit",
                "risk": "low",
                "status": "suggested",
                "max_similarity": 0.63,
                "observed_value": 6.4,
                "assay": "screen_a",
                "target": "target_a",
                "explanation": ["High confidence makes this a practical exploit candidate for review."],
                "score_breakdown": [
                    {
                        "key": "confidence",
                        "label": "Confidence",
                        "raw_value": 0.91,
                        "weight": 0.30,
                        "weight_percent": 30.0,
                        "contribution": 0.273,
                    },
                    {
                        "key": "experiment_value",
                        "label": "Experiment value",
                        "raw_value": 0.72,
                        "weight": 0.35,
                        "weight_percent": 35.0,
                        "contribution": 0.252,
                    },
                ],
                "rationale": {
                    "summary": "This candidate is being prioritized mainly because confidence is carrying the shortlist position.",
                    "why_now": "Confidence is the largest contributor to the current priority score.",
                    "trust_label": "Stronger trust",
                    "trust_summary": "Confidence is relatively stable and the chemistry remains within stronger domain coverage.",
                    "recommended_action": "Use this as a near-term testing candidate because the signal is relatively stable.",
                    "primary_driver": "confidence",
                    "session_context": [
                        "Priority score ranks #1 out of 1 scored candidates in this run."
                    ],
                    "strengths": [
                        "Confidence is relatively strong at 0.910.",
                        "Reference similarity is strong enough to support more confident near-term review.",
                    ],
                    "cautions": [],
                    "evidence_lines": [
                        "This candidate is being prioritized mainly because confidence is carrying the shortlist position.",
                        "Confidence is the largest contributor to the current priority score.",
                    ],
                },
                "data_facts": {
                    "observed_value": 6.4,
                    "measurement_column": "pic50",
                    "label_column": "",
                    "dataset_type": "measurement_dataset",
                    "assay": "screen_a",
                    "target": "target_a",
                    "source_name": "upload.csv",
                },
                "model_judgment": {
                    "target_kind": "regression",
                    "predicted_value": 6.55,
                    "prediction_dispersion": 0.18,
                    "uncertainty": 0.1,
                    "uncertainty_kind": "ensemble_prediction_std",
                    "model_summary": "The model produced a continuous target prediction and a dispersion-based uncertainty estimate.",
                },
                "applicability_domain": {
                    "status": "in_domain",
                    "max_reference_similarity": 0.63,
                    "support_band": "Within stronger chemistry support",
                    "summary": "Reference similarity is strong enough to support more confident near-term review.",
                    "evidence": ["Similarity support remains above the current in-domain threshold."],
                },
                "novelty_signal": {
                    "novelty_score": 0.58,
                    "reference_similarity": 0.63,
                    "batch_similarity": 0.41,
                    "summary": "This candidate adds some structural novelty without leaving known chemistry entirely.",
                },
                "decision_policy": {
                    "bucket": "exploit",
                    "priority_score": 0.78,
                    "acquisition_score": 0.77,
                    "experiment_value": 0.72,
                    "selection_reason": "confidence-dominant shortlist position",
                    "policy_summary": "The decision policy is prioritizing this candidate for near-term testing based on current score stability.",
                },
                "final_recommendation": {
                    "recommended_action": "Use this as a near-term testing candidate because the signal is relatively stable.",
                    "summary": "Recommendation details are strongest for near-term review and testing.",
                    "follow_up_experiment": "Run the next confirmatory assay against this candidate.",
                    "trust_cautions": [],
                },
                "normalized_explanation": {
                    "why_this_candidate": "This candidate is included because it remains competitive under the current decision policy.",
                    "why_now": "Confidence is the largest contributor to the current priority score.",
                    "supporting_evidence": [
                        "This candidate is being prioritized mainly because confidence is carrying the shortlist position."
                    ],
                    "model_judgment_summary": "The model predicts a continuous value of 6.550 for target_a.",
                    "uncertainty_summary": "Uncertainty is 0.100.",
                    "novelty_summary": "This candidate adds some structural novelty without leaving known chemistry entirely.",
                    "decision_policy_reason": "The decision policy is prioritizing this candidate for near-term testing based on current score stability.",
                    "recommended_followup": "Run the next confirmatory assay against this candidate.",
                    "trust_cautions": [],
                },
                "domain_status": "in_domain",
                "domain_label": "Within stronger chemistry range",
                "domain_summary": "Reference similarity is strong enough to support more confident near-term review.",
                "provenance": {
                    "text": "Scored directly from user-uploaded dataset upload.csv. Model version: rf_isotonic:isotonic.",
                    "source_name": "upload.csv",
                    "source_type": "uploaded",
                    "parent_molecule": "",
                    "model_version": "rf_isotonic:isotonic",
                },
                "feasibility": {"is_feasible": True, "reason": ""},
                "created_at": "2026-03-25T12:00:00+00:00",
                "model_metadata": {
                    "version": "rf_isotonic:isotonic",
                    "family": "random_forest",
                    "calibration_method": "isotonic",
                },
                "target_definition": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_column": "pic50",
                    "scientific_meaning": "Higher predicted values are treated as more favorable for pIC50.",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                    "success_definition": "Success means prioritizing molecules expected to achieve higher pIC50 values.",
                },
            }
        ],
        "target_definition": {
            "target_name": "pIC50",
            "target_kind": "regression",
            "optimization_direction": "maximize",
            "measurement_column": "pic50",
            "scientific_meaning": "Higher predicted values are treated as more favorable for pIC50.",
            "dataset_type": "measurement_dataset",
            "mapping_confidence": "medium",
            "success_definition": "Success means prioritizing molecules expected to achieve higher pIC50 values.",
        },
        "modeling_mode": "regression",
        "decision_intent": "prioritize_experiments",
        "run_contract": {
            "session_id": "session_1",
            "source_name": "upload.csv",
            "input_type": "measurement_dataset",
            "requested_intent": "rank_uploaded_molecules",
            "decision_intent": "prioritize_experiments",
            "modeling_mode": "regression",
            "scoring_mode": "balanced",
            "target_definition": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "measurement_column": "pic50",
                "scientific_meaning": "Higher predicted values are treated as more favorable for pIC50.",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
                "success_definition": "Success means prioritizing molecules expected to achieve higher pIC50 values.",
            },
            "target_model_available": True,
            "selected_model_name": "rf_regression",
            "selected_model_family": "random_forest",
            "training_scope": "session_trained",
            "label_source": "continuous_measurement",
            "feature_signature": "rdkit_descriptors_plus_morgan_fp_2048",
            "reference_basis": {
                "novelty_reference": "reference_dataset_similarity",
                "applicability_reference": "reference_dataset_similarity",
            },
            "contract_versions": {
                "target_contract_version": "target_definition.v1",
                "model_contract_version": "model_contract.v1",
                "run_contract_version": "run_contract.v1",
            },
        },
        "comparison_anchors": {
            "session_id": "session_1",
            "source_name": "upload.csv",
            "input_type": "measurement_dataset",
            "target_name": "pIC50",
            "target_kind": "regression",
            "optimization_direction": "maximize",
            "measurement_column": "pic50",
            "dataset_type": "measurement_dataset",
            "mapping_confidence": "medium",
            "column_mapping": {"smiles": "smiles", "value": "pic50"},
            "label_source": "continuous_measurement",
            "decision_intent": "prioritize_experiments",
            "modeling_mode": "regression",
            "scoring_mode": "balanced",
            "selected_model_name": "rf_regression",
            "training_scope": "session_trained",
            "target_contract_version": "target_definition.v1",
            "model_contract_version": "model_contract.v1",
            "scoring_policy_version": "scoring_policy.v1",
            "explanation_contract_version": "normalized_explanation.v1",
            "run_contract_version": "run_contract.v1",
            "comparison_ready": True,
        },
    }


class DiscoveryWorkbenchTest(unittest.TestCase):
    def test_build_discovery_workbench_loads_canonical_artifact(self):
        workbench = build_discovery_workbench(
            decision_output=canonical_decision_output(),
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
        self.assertEqual(candidate["candidate_id"], "cand_1")
        self.assertEqual(candidate["bucket"], "exploit")
        self.assertEqual(candidate["risk"], "low")
        self.assertEqual(candidate["status"], "suggested")
        self.assertIn("upload.csv", candidate["provenance"])
        self.assertEqual(candidate["canonical_smiles"], "CCO")
        self.assertEqual(candidate["model_version"], "rf_isotonic:isotonic")
        self.assertEqual(candidate["acquisition_score"], 0.77)
        self.assertEqual(candidate["decision_category"], "test_now")
        self.assertEqual(candidate["decision_label"], "Recommended for immediate testing")
        self.assertEqual(candidate["priority_score"], 0.78)
        self.assertEqual(candidate["primary_score_name"], "priority_score")
        self.assertEqual(candidate["domain_status"], "in_domain")
        self.assertEqual(candidate["observed_value"], 6.4)
        self.assertEqual(workbench["comparison_anchors"]["target_name"], "pIC50")
        self.assertEqual(workbench["run_contract"]["selected_model_name"], "rf_regression")
        self.assertTrue(workbench["run_provenance"]["comparison_ready"])
        self.assertIn("rf_regression", workbench["run_provenance"]["model_summary"])
        self.assertEqual(candidate["assay"], "screen_a")
        self.assertEqual(candidate["target"], "target_a")
        self.assertEqual(candidate["trust_label"], "Stronger trust")
        self.assertIn("confidence", candidate["rationale_primary_driver"])
        self.assertTrue(candidate["rationale_session_context"])
        self.assertTrue(candidate["rationale_summary"])
        self.assertTrue(candidate["rationale_evidence_lines"])
        self.assertEqual(candidate["data_facts"]["dataset_type"], "measurement_dataset")
        self.assertEqual(candidate["applicability_domain"]["status"], "in_domain")
        self.assertEqual(candidate["novelty_signal"]["novelty_score"], 0.58)
        self.assertEqual(candidate["decision_policy"]["bucket"], "exploit")
        self.assertEqual(candidate["final_recommendation"]["recommended_action"], "Use this as a near-term testing candidate because the signal is relatively stable.")
        self.assertIn("continuous value", candidate["normalized_explanation"]["model_judgment_summary"])
        self.assertTrue(workbench["ranking_policy"]["weight_breakdown"])
        self.assertEqual(workbench["modeling_mode"], "regression")
        self.assertEqual(workbench["decision_overview"]["groups"][0]["key"], "test_now")
        self.assertEqual(workbench["decision_overview"]["primary_group"]["key"], "test_now")
        self.assertEqual(workbench["decision_overview"]["primary_candidate"]["candidate_id"], "cand_1")
        self.assertEqual(workbench["decision_overview"]["top_shortlist"][0]["candidate_id"], "cand_1")

    def test_build_discovery_workbench_reports_contract_error_for_missing_required_fields(self):
        invalid_decision_output = {
            "iteration": 3,
            "generated_at": "2026-03-25T12:00:00+00:00",
            "summary": {"top_k": 1, "candidate_count": 1, "risk_counts": {}, "top_experiment_value": 0.72},
            "top_experiments": [
                {
                    "candidate_id": "cand_1",
                    "smiles": "CCO",
                    "confidence": 0.91,
                    "uncertainty": 0.1,
                    "novelty": 0.58,
                    "experiment_value": 0.72,
                }
            ],
        }

        workbench = build_discovery_workbench(
            decision_output=invalid_decision_output,
            analysis_report={"warnings": [], "top_level_recommendation_summary": "Start with the top candidate."},
            review_queue={},
            session_id=None,
            evaluation_summary={"selected_model": {"name": "rf_isotonic", "calibration_method": "isotonic"}},
            system_version="2.0.0",
        )

        self.assertEqual(workbench["state"]["kind"], "error")
        self.assertIn("contract", workbench["state"]["message"].lower())

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
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        reset_database_state(f"sqlite:///{Path(self.tmpdir.name) / 'control_plane.db'}")
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
        self.client = TestClient(discovery_app.app)
        login_page = self.client.get("/login")
        csrf_token = self._extract_csrf_token(login_page.text)
        response = self.client.post(
            "/login",
            data={"email": self.user["email"], "password": "secret123", "csrf_token": csrf_token, "next": "/discovery"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)

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

    def _authenticated_csrf(self, path: str = "/discovery") -> str:
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return self._extract_csrf_token(response.text)

    def _store_result_only_session(self, session_id: str) -> None:
        SessionRepository().upsert_session(
            session_id=session_id,
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
            source_name="upload.csv",
            input_type="measurement_dataset",
            latest_job_id="job_1",
            summary_metadata={"last_job_status": "succeeded"},
        )
        session_dir = Path(self.tmpdir.name) / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        result_path = session_dir / "result.json"
        result_path.write_text(
            discovery_app.json.dumps(
                {
                    "decision_output": canonical_decision_output(),
                    "analysis_report": {
                        "warnings": [],
                        "top_level_recommendation_summary": "Start with the top candidate.",
                        "measurement_summary": {"semantic_mode": "measurement_dataset", "rows_with_values": 12},
                        "ranking_diagnostics": {"out_of_domain_rate": 0.2},
                    },
                }
            )
        )
        ArtifactRepository().register_artifact(
            artifact_type="result_json",
            path=result_path,
            session_id=session_id,
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )

    def _store_legacy_measurement_session(self, session_id: str) -> None:
        SessionRepository().upsert_session(
            session_id=session_id,
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
            source_name="measurement.csv",
            input_type="measurement_dataset",
            latest_job_id="job_legacy",
            upload_metadata={
                "session_id": session_id,
                "created_at": "2026-03-31T02:00:00+00:00",
                "filename": "measurement.csv",
                "input_type": "measurement_dataset",
                "file_type": "csv",
                "semantic_mode": "measurement_dataset",
                "columns": ["compound_id", "smiles", "pic50"],
                "preview_rows": [
                    {"compound_id": "cmp1", "smiles": "CCO", "pic50": "6.4"},
                    {"compound_id": "cmp2", "smiles": "CCN", "pic50": "5.8"},
                ],
                "inferred_mapping": {
                    "entity_id": "compound_id",
                    "smiles": "smiles",
                    "value": "pic50",
                    "label": None,
                    "target": None,
                    "assay": None,
                    "source": None,
                    "notes": None,
                },
                "selected_mapping": {
                    "entity_id": "compound_id",
                    "smiles": "smiles",
                    "value": "pic50",
                    "label": None,
                    "target": None,
                    "assay": None,
                    "source": None,
                    "notes": None,
                },
                "validation_summary": {
                    "total_rows": 12,
                    "valid_smiles_count": 12,
                    "invalid_smiles_count": 0,
                    "duplicate_count": 0,
                    "rows_with_labels": 0,
                    "rows_without_labels": 12,
                    "rows_with_values": 12,
                    "rows_without_values": 0,
                    "value_column": "pic50",
                    "semantic_mode": "measurement_dataset",
                    "file_type": "csv",
                    "label_source": "missing",
                    "can_run_analysis": True,
                    "warnings": [],
                },
            },
            summary_metadata={"last_job_status": "succeeded"},
        )
        session_dir = Path(self.tmpdir.name) / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        result_path = session_dir / "result.json"
        result_path.write_text(
            discovery_app.json.dumps(
                {
                    "decision_output": canonical_decision_output(),
                    "analysis_report": {
                        "warnings": [],
                        "top_level_recommendation_summary": "Start with the top candidate.",
                        "measurement_summary": {
                            "semantic_mode": "",
                            "value_column": "",
                            "rows_with_values": 0,
                            "label_source": "",
                        },
                        "ranking_diagnostics": {"out_of_domain_rate": 0.2},
                    },
                }
            )
        )
        ArtifactRepository().register_artifact(
            artifact_type="result_json",
            path=result_path,
            session_id=session_id,
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )

    def test_discovery_page_renders_workbench_sections(self):
        response = self.client.get("/discovery")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Discovery Results", response.text)
        self.assertIn("Filter And Sort", response.text)
        self.assertIn("Review Workflow Summary", response.text)

    def test_discovery_page_uses_latest_completed_session_when_no_query_is_provided(self):
        self._store_result_only_session("session_latest")

        response = self.client.get("/discovery")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Viewing the latest completed session", response.text)
        self.assertIn("session_latest", response.text)
        self.assertIn("cand_1", response.text)
        self.assertIn("Decision Guidance", response.text)
        self.assertIn("Recommended next step", response.text)
        self.assertIn("Priority score", response.text)
        self.assertIn("Recommended for immediate testing", response.text)

    def test_discovery_page_can_reopen_session_from_nested_result_payload(self):
        self._store_result_only_session("session_result_only")

        response = self.client.get("/discovery?session_id=session_result_only")

        self.assertEqual(response.status_code, 200)
        self.assertIn("cand_1", response.text)
        self.assertIn("measurement_dataset", response.text)
        self.assertNotIn("Current decision artifact could not be loaded", response.text)

    def test_dashboard_page_uses_latest_completed_session_when_no_query_is_provided(self):
        self._store_result_only_session("session_dashboard_latest")

        response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Viewing the latest completed session dashboard.", response.text)
        self.assertIn("session_dashboard_latest", response.text)
        self.assertIn("Model Insight Summary", response.text)
        self.assertIn("cand_1", response.text)

    def test_dashboard_page_can_reopen_session_from_nested_result_payload(self):
        self._store_result_only_session("session_dashboard_result_only")

        response = self.client.get("/dashboard?session_id=session_dashboard_result_only")

        self.assertEqual(response.status_code, 200)
        self.assertIn("session_dashboard_result_only", response.text)
        self.assertIn("measurement_dataset", response.text)
        self.assertIn("Shortlist Reading", response.text)
        self.assertIn("Priority Score", response.text)

    def test_discovery_page_backfills_measurement_context_from_upload_metadata(self):
        self._store_legacy_measurement_session("session_legacy_discovery")

        response = self.client.get("/discovery?session_id=session_legacy_discovery")

        self.assertEqual(response.status_code, 200)
        self.assertIn("measurement_dataset", response.text)
        self.assertIn("pic50", response.text)
        self.assertIn(">12<", response.text)

    def test_dashboard_page_backfills_measurement_context_from_upload_metadata(self):
        self._store_legacy_measurement_session("session_legacy_dashboard")

        response = self.client.get("/dashboard?session_id=session_legacy_dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn("measurement_dataset", response.text)
        self.assertIn("pic50", response.text)
        self.assertIn(">12<", response.text)
        self.assertIn("cand_1", response.text)

    def test_reviews_api_accepts_bulk_payload(self):
        SessionRepository().upsert_session(
            session_id="session_1",
            workspace_id=self.workspace["workspace_id"],
            created_by_user_id=self.user["user_id"],
        )
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
            patch.object(
                discovery_app,
                "annotate_candidates_with_reviews",
                side_effect=lambda candidates, session_id=None, workspace_id=None: candidates,
            ),
            patch.object(discovery_app, "persist_review_queue", return_value={"summary": {"counts": {"approved": 1}}}),
        ):
            response = self.client.post(
                "/api/reviews",
                json={
                    "session_id": "session_1",
                    "items": [{"candidate_id": "cand_1", "smiles": "CCO", "action": "approve", "status": "approved"}],
                },
                headers={"X-CSRF-Token": self._authenticated_csrf()},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("reviews", response.json())
        mock_record.assert_called_once()


if __name__ == "__main__":
    unittest.main()
