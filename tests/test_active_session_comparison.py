import unittest
from unittest.mock import patch

from system.services.active_session_comparison_service import build_active_session_comparison_context


class ActiveSessionComparisonServiceTest(unittest.TestCase):
    @patch("system.services.active_session_comparison_service.load_decision_artifact_payload")
    @patch("system.services.active_session_comparison_service.load_analysis_report_payload")
    def test_build_active_session_comparison_context_prefers_directly_comparable_baseline(
        self,
        mock_load_analysis_report,
        mock_load_decision_artifact,
    ):
        def _analysis_payload(session_id: str | None = None, **_: object):
            if session_id == "baseline_direct":
                return {
                    "target_definition": {
                        "target_name": "pIC50",
                        "target_kind": "regression",
                        "optimization_direction": "maximize",
                        "measurement_column": "pic50",
                        "dataset_type": "measurement_dataset",
                        "mapping_confidence": "high",
                    },
                    "decision_intent": "prioritize_experiments",
                    "modeling_mode": "regression",
                    "mode_used": "balanced",
                    "ranking_diagnostics": {"out_of_domain_rate": 0.1},
                }
            return {
                "target_definition": {
                    "target_name": "solubility",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_column": "solubility",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                },
                "decision_intent": "prioritize_experiments",
                "modeling_mode": "regression",
                "mode_used": "balanced",
                "ranking_diagnostics": {"out_of_domain_rate": 0.45},
            }

        def _decision_payload(session_id: str | None = None, **_: object):
            if session_id == "baseline_direct":
                return {
                    "artifact_state": "ok",
                    "summary": {"candidate_count": 4, "top_experiment_value": 0.68},
                    "top_experiments": [
                        {"candidate_id": "base_1", "smiles": "CCO", "canonical_smiles": "CCO", "bucket": "exploit", "risk": "low"},
                        {"candidate_id": "base_2", "smiles": "CCN", "canonical_smiles": "CCN", "bucket": "exploit", "risk": "low"},
                        {"candidate_id": "base_3", "smiles": "CCC", "canonical_smiles": "CCC", "bucket": "learn", "risk": "low"},
                        {"candidate_id": "base_4", "smiles": "CCCl", "canonical_smiles": "CCCl", "bucket": "explore", "risk": "low"},
                    ],
                    "target_definition": {
                        "target_name": "pIC50",
                        "target_kind": "regression",
                        "optimization_direction": "maximize",
                        "measurement_column": "pic50",
                        "dataset_type": "measurement_dataset",
                        "mapping_confidence": "high",
                    },
                    "decision_intent": "prioritize_experiments",
                    "modeling_mode": "regression",
                    "comparison_anchors": {
                        "target_name": "pIC50",
                        "target_kind": "regression",
                        "optimization_direction": "maximize",
                        "measurement_column": "pic50",
                        "dataset_type": "measurement_dataset",
                        "mapping_confidence": "high",
                        "decision_intent": "prioritize_experiments",
                        "modeling_mode": "regression",
                        "scoring_policy_version": "scoring_policy.v1",
                        "comparison_ready": True,
                    },
                }
            return {
                "artifact_state": "ok",
                "summary": {"candidate_count": 3, "top_experiment_value": 0.55},
                "top_experiments": [
                    {"candidate_id": "other_1", "smiles": "NNO", "canonical_smiles": "NNO", "bucket": "explore", "risk": "high", "domain_status": "out_of_domain"},
                    {"candidate_id": "other_2", "smiles": "NNN", "canonical_smiles": "NNN", "bucket": "learn", "risk": "low"},
                    {"candidate_id": "other_3", "smiles": "NNC", "canonical_smiles": "NNC", "bucket": "learn", "risk": "low"},
                ],
                "target_definition": {
                    "target_name": "solubility",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_column": "solubility",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                },
                "decision_intent": "prioritize_experiments",
                "modeling_mode": "regression",
                "comparison_anchors": {
                    "target_name": "solubility",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_column": "solubility",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                    "decision_intent": "prioritize_experiments",
                    "modeling_mode": "regression",
                    "scoring_policy_version": "scoring_policy.v1",
                    "comparison_ready": True,
                },
            }

        mock_load_analysis_report.side_effect = _analysis_payload
        mock_load_decision_artifact.side_effect = _decision_payload

        context = build_active_session_comparison_context(
            current_session_record={
                "session_id": "current",
                "source_name": "current.csv",
                "created_at": "2026-04-01T10:00:00+00:00",
                "upload_metadata": {
                    "validation_summary": {"total_rows": 10, "rows_with_values": 10},
                    "selected_mapping": {"smiles": "smiles", "value": "pic50"},
                },
            },
            current_analysis_report={
                "target_definition": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_column": "pic50",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "high",
                },
                "decision_intent": "prioritize_experiments",
                "modeling_mode": "regression",
                "mode_used": "balanced",
                "ranking_diagnostics": {"out_of_domain_rate": 0.25},
            },
            current_decision_payload={
                "artifact_state": "ok",
                "summary": {"candidate_count": 5, "top_experiment_value": 0.74},
                "top_experiments": [
                    {"candidate_id": "curr_1", "smiles": "CCN", "canonical_smiles": "CCN", "bucket": "exploit", "risk": "low"},
                    {"candidate_id": "curr_2", "smiles": "CCO", "canonical_smiles": "CCO", "bucket": "exploit", "risk": "low"},
                    {"candidate_id": "curr_3", "smiles": "CCBr", "canonical_smiles": "CCBr", "bucket": "exploit", "risk": "low"},
                    {"candidate_id": "curr_4", "smiles": "CCC", "canonical_smiles": "CCC", "bucket": "learn", "risk": "low"},
                    {"candidate_id": "curr_5", "smiles": "CC(=O)O", "canonical_smiles": "CC(=O)O", "bucket": "learn", "risk": "high", "domain_status": "out_of_domain"},
                ],
                "target_definition": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_column": "pic50",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "high",
                },
                "decision_intent": "prioritize_experiments",
                "modeling_mode": "regression",
                "comparison_anchors": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_column": "pic50",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "high",
                    "decision_intent": "prioritize_experiments",
                    "modeling_mode": "regression",
                    "scoring_policy_version": "scoring_policy.v1",
                    "comparison_ready": True,
                },
            },
            workspace_sessions=[
                {"session_id": "baseline_other", "source_name": "other.csv", "updated_at": "2026-03-29T00:00:00+00:00"},
                {"session_id": "baseline_direct", "source_name": "baseline.csv", "updated_at": "2026-03-30T00:00:00+00:00"},
            ],
            workspace_id="workspace_1",
        )

        self.assertTrue(context["available"])
        self.assertEqual(context["comparison"]["status"], "directly_comparable")
        self.assertEqual(context["baseline"]["session_id"], "baseline_direct")
        self.assertIn("higher by 0.060", " ".join(context["delta_lines"]))
        self.assertIn("Weak-support rate is higher by 15.0%", " ".join(context["delta_lines"]))
        self.assertIn("Weak-support rate is higher by 15.0%", " ".join(context["comparison"]["outcome_differences"]))
        self.assertIn("shared across the compared shortlist previews", context["comparison"]["candidate_comparison_summary"])
        self.assertTrue(any("Lead candidate changed" in item for item in context["comparison"]["candidate_differences"]))


if __name__ == "__main__":
    unittest.main()
