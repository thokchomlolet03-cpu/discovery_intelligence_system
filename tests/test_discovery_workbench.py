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
                    "uncertainty_summary": "Prediction dispersion is 0.100; higher values mean the regression estimate is less stable.",
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
            "feature_signature": "rdkit_descriptors_4_plus_morgan_fp_2048",
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
        self.assertIn("measure", candidate["final_recommendation"]["recommended_action"].lower())
        self.assertIn("ranking compatibility", candidate["normalized_explanation"]["model_judgment_summary"].lower())
        self.assertEqual(workbench["summary"]["average_confidence_label"], "Average ranking compatibility")
        self.assertEqual(workbench["summary"]["average_uncertainty_label"], "Average prediction dispersion")
        self.assertAlmostEqual(workbench["summary"]["average_predicted_value"], 6.55, places=2)
        self.assertTrue(workbench["ranking_policy"]["weight_breakdown"])
        self.assertEqual(workbench["modeling_mode"], "regression")
        self.assertEqual(workbench["decision_overview"]["groups"][0]["key"], "test_now")
        self.assertEqual(workbench["decision_overview"]["primary_group"]["key"], "test_now")
        self.assertEqual(workbench["decision_overview"]["primary_candidate"]["candidate_id"], "cand_1")
        self.assertEqual(workbench["decision_overview"]["top_shortlist"][0]["candidate_id"], "cand_1")
        self.assertEqual(workbench["trust_context"]["evidence_support_label"], "Stronger evidence support")
        self.assertIn("observed values", workbench["trust_context"]["evidence_basis_summary"].lower())
        self.assertEqual(workbench["scientific_session_truth"], {})

    def test_build_discovery_workbench_preserves_workspace_memory_annotations(self):
        decision_output = canonical_decision_output()
        decision_output["top_experiments"][0]["workspace_memory_count"] = 1
        decision_output["top_experiments"][0]["workspace_memory"] = {
            "event_count": 1,
            "session_count": 1,
            "session_ids": ["session_prior"],
            "last_status": "approved",
            "last_status_label": "Approved",
            "last_action": "approve",
            "last_action_label": "Approve",
            "last_note": "Carry this prior approval into the next run.",
            "last_reviewer": "qa",
            "last_reviewed_at": "2026-03-24T12:00:00+00:00",
            "last_reviewed_at_label": "2026-03-24 12:00 UTC",
            "last_session_id": "session_prior",
            "last_session_label": "session_prior",
            "discovery_url": "/discovery?session_id=session_prior",
        }
        decision_output["top_experiments"][0]["workspace_memory_history"] = [
            {
                "session_id": "session_prior",
                "session_label": "session_prior",
                "action": "approve",
                "action_label": "Approve",
                "status": "approved",
                "status_label": "Approved",
                "note": "Carry this prior approval into the next run.",
                "reviewer": "qa",
                "reviewed_at": "2026-03-24T12:00:00+00:00",
                "reviewed_at_label": "2026-03-24 12:00 UTC",
                "discovery_url": "/discovery?session_id=session_prior",
            }
        ]

        workbench = build_discovery_workbench(
            decision_output=decision_output,
            analysis_report={"warnings": [], "top_level_recommendation_summary": "Start with the top candidate."},
            review_queue={},
            session_id=None,
            evaluation_summary={"selected_model": {"name": "rf_isotonic", "calibration_method": "isotonic"}},
            system_version="2.0.0",
        )

        candidate = workbench["candidates"][0]
        self.assertEqual(candidate["workspace_memory_count"], 1)
        self.assertEqual(candidate["workspace_memory"]["last_session_id"], "session_prior")
        self.assertEqual(candidate["workspace_memory"]["last_note"], "Carry this prior approval into the next run.")
        self.assertEqual(candidate["workspace_memory_history"][0]["status"], "approved")
        self.assertTrue(candidate["selective_evidence_context"])
        self.assertIn("interpretation support", candidate["selective_evidence_context"][0].lower())
        self.assertTrue(candidate["controlled_reuse"]["recommendation_reuse_active"])
        self.assertIn("without retraining the model", candidate["controlled_reuse"]["recommendation_reuse_summary"].lower())
        self.assertIn("continuity across sessions", candidate["final_recommendation"]["summary"].lower())
        self.assertIn("does not retrain the model", candidate["decision_policy"]["policy_summary"].lower())
        self.assertEqual(workbench["workspace_memory"]["matched_candidate_count"], 1)
        self.assertIn("prior workspace feedback", workbench["workspace_memory"]["summary"].lower())

    def test_build_discovery_workbench_exposes_claim_refs_from_scientific_truth(self):
        scientific_truth = {
            "session_id": "session_claim_view",
            "target_definition": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
            },
            "claims_summary": {
                "claim_count": 1,
                "proposed_count": 1,
                "accepted_count": 0,
                "rejected_count": 0,
                "superseded_count": 0,
                "claims_with_active_support_count": 1,
                "claims_with_historical_support_only_count": 0,
                "claims_with_rejected_support_only_count": 0,
                "claims_with_no_governed_support_count": 0,
                "continuity_aligned_claim_count": 1,
                "new_claim_context_count": 0,
                "weak_prior_alignment_count": 0,
                "no_prior_claim_context_count": 0,
                "claims_with_active_governed_continuity_count": 1,
                "claims_with_historical_continuity_only_count": 0,
                "claims_with_sparse_prior_context_count": 0,
                "claims_with_no_useful_prior_context_count": 0,
                "claims_mostly_observed_label_grounded_count": 1,
                "claims_with_numeric_rule_based_support_count": 0,
                "claims_with_weak_basis_support_count": 0,
                "claims_with_mixed_support_basis_count": 0,
                "claims_action_ready_follow_up_count": 1,
                "claims_promising_but_need_stronger_evidence_count": 0,
                "claims_need_clarifying_experiment_count": 0,
                "claims_do_not_prioritize_yet_count": 0,
                "claims_with_insufficient_governed_basis_count": 0,
                "claims_action_ready_from_active_support_count": 1,
                "claims_historically_interesting_count": 0,
                "claims_with_mixed_current_historical_actionability_count": 0,
                "summary_text": "1 proposed claim was derived from the current shortlist. Claims remain bounded recommendation-derived assertions, not experimental confirmation.",
                "chronology_summary_text": "Claim-level support chronology remains bounded: 1 claim with active governed support.",
                "claim_support_basis_summary_text": "Claim support-basis composition remains bounded: 1 grounded mostly in observed labels.",
                "claim_actionability_summary_text": "Claim actionability remains bounded: 1 action-ready from current active support.",
                "claim_actionability_basis_summary_text": "Claim actionability basis remains bounded: 1 action-ready from current active support.",
                "read_across_summary_text": "This session mostly reinforces prior target-scoped claim context with active governed continuity. Claim read-across remains bounded.",
                "top_claims": [],
            },
            "claim_refs": [
                {
                    "claim_id": "claim_1",
                    "candidate_id": "cand_1",
                    "candidate_label": "cand_1 (CCO)",
                    "claim_type": "recommendation_assertion",
                    "claim_text": "Under the current session evidence, cand_1 (CCO) is a plausible follow-up candidate to test for higher pIC50.",
                    "support_level": "strong",
                    "status": "proposed",
                    "source_recommendation_rank": 1,
                    "claim_support_role_label": "Active governed support",
                    "current_support_count": 1,
                    "historical_support_count": 0,
                    "rejected_support_count": 0,
                    "claim_chronology_summary_text": "This claim currently has 1 active governed support change.",
                    "claim_support_basis_mix_label": "Grounded mostly in observed labels",
                    "claim_support_basis_mix_summary": "This claim's current governed support is grounded mostly in observed labels (1) and remains bounded rather than final.",
                    "claim_observed_label_support_count": 1,
                    "claim_numeric_rule_based_support_count": 0,
                    "claim_unresolved_basis_count": 0,
                    "claim_weak_basis_count": 0,
                    "claim_read_across_label": "Continuity-aligned claim",
                    "claim_read_across_summary": "This claim aligns with 2 prior target-scoped claim records for the same candidate context. Read-across remains bounded and does not confirm claim identity.",
                    "claim_prior_context_count": 2,
                    "claim_prior_support_quality_label": "Posture-governing continuity",
                    "claim_prior_support_quality_summary": "Prior continuity for this claim context includes 1 claim record backed by accepted posture-governing support.",
                    "claim_prior_active_support_count": 1,
                    "claim_prior_historical_support_count": 0,
                    "claim_actionability_label": "Action-ready from current active support",
                    "claim_actionability_summary": "cand_1 (CCO) has active governed support grounded mostly in observed labels, including 1 accepted support change, so bounded follow-up is reasonable without implying proof.",
                    "claim_actionability_basis_label": "Current active support basis",
                    "claim_actionability_basis_summary": "cand_1 (CCO)'s present actionability is grounded in current active governed support rather than historical context.",
                    "claim_historical_interest_only_flag": False,
                    "claim_next_step_label": "Follow-up experiment is reasonable now",
                    "claim_next_step_summary": "A bounded follow-up experiment is reasonable now, while keeping the claim explicitly separate from validated truth.",
                    "created_at": "2026-04-02T10:00:00+00:00",
                }
            ],
            "experiment_request_summary": {
                "request_count": 1,
                "proposed_count": 1,
                "accepted_count": 0,
                "rejected_count": 0,
                "completed_count": 0,
                "superseded_count": 0,
                "summary_text": "1 proposed experiment request was derived from the current claims. These requests recommend next experiments; they are not scheduled or completed lab work.",
                "top_requests": [],
            },
            "experiment_request_refs": [
                {
                    "experiment_request_id": "expreq_1",
                    "claim_id": "claim_1",
                    "candidate_id": "cand_1",
                    "candidate_label": "cand_1 (CCO)",
                    "requested_measurement": "pIC50",
                    "requested_direction": "measure for higher values",
                    "priority_tier": "high",
                    "status": "proposed",
                    "requested_at": "2026-04-02T10:00:00+00:00",
                }
            ],
            "linked_result_summary": {
                "result_count": 1,
                "recorded_count": 1,
                "with_numeric_value_count": 1,
                "with_label_count": 0,
                "summary_text": "1 observed result has been recorded for this session. Observed results are stored outcome records, not belief updates or causal proof.",
                "top_results": [],
            },
            "experiment_result_refs": [
                {
                    "experiment_result_id": "expres_1",
                    "source_experiment_request_id": "expreq_1",
                    "source_claim_id": "claim_1",
                    "candidate_id": "cand_1",
                    "candidate_label": "cand_1 (CCO)",
                    "observed_value": 6.7,
                    "measurement_unit": "log units",
                    "result_quality": "confirmatory",
                    "result_source": "manual_entry",
                    "ingested_at": "2026-04-02T11:00:00+00:00",
                }
            ],
            "belief_update_summary": {
                "update_count": 1,
                "active_count": 1,
                "historical_count": 0,
                "proposed_count": 1,
                "accepted_count": 0,
                "rejected_count": 0,
                "superseded_count": 0,
                "strengthened_count": 1,
                "weakened_count": 0,
                "unresolved_count": 0,
                "numeric_interpreted_count": 0,
                "numeric_unresolved_count": 0,
                "observed_label_support_count": 1,
                "numeric_rule_based_support_count": 0,
                "unresolved_basis_count": 0,
                "weak_basis_count": 0,
                "support_basis_mix_label": "Grounded mostly in observed labels",
                "support_basis_mix_summary": "Session support changes are grounded mostly in observed labels (1), with 0 bounded numeric interpretation records and 0 unresolved support basis records.",
                "summary_text": "1 belief update has been recorded for this session. These updates track bounded support changes only; they do not prove claims, imply causality, or change the model.",
                "chronology_mix_label": "Current support only",
                "chronology_summary_text": "This session currently contributes 1 active support change and no historical support records.",
                "numeric_interpretation_summary_text": "",
                "top_updates": [],
            },
            "belief_update_refs": [
                {
                    "belief_update_id": "belief_1",
                    "claim_id": "claim_1",
                    "experiment_result_id": "expres_1",
                    "candidate_id": "cand_1",
                    "candidate_label": "cand_1 (CCO)",
                    "previous_support_level": "strong",
                    "updated_support_level": "strong",
                    "update_direction": "strengthened",
                    "support_input_quality_label": "Cautious interpretation basis",
                    "support_input_quality_summary": "Result quality and context support a cautious bounded interpretation under the current observed label path.",
                    "assay_context_alignment_label": "No specific assay context expected",
                    "result_interpretation_basis": "Observed label",
                    "numeric_result_basis_label": "",
                    "numeric_result_basis_summary": "",
                    "numeric_result_resolution_label": "",
                    "numeric_result_interpretation_label": "",
                    "target_rule_alignment_label": "",
                    "governance_status": "proposed",
                    "chronology_label": "Current proposed support change",
                    "active_for_belief_state": True,
                    "created_at": "2026-04-02T12:00:00+00:00",
                }
            ],
            "belief_state_ref": {
                "belief_state_id": "beliefstate_1",
                "target_key": "pic50|regression|maximize|pic50|measurement_dataset",
                "summary_text": "Current belief state for pIC50 tracks 1 active claim: 1 strengthened, 0 weakened, and 0 unresolved.",
                "active_claim_count": 1,
                "supported_claim_count": 1,
                "weakened_claim_count": 0,
                "unresolved_claim_count": 0,
                "last_updated_at": "2026-04-02T12:05:00+00:00",
                "last_update_source": "latest belief update linked to an observed result",
                "version": 1,
            },
            "belief_state_summary": {
                "summary_text": "Current belief state for pIC50 tracks 1 active claim: 1 strengthened, 0 weakened, and 0 unresolved. This is a bounded support summary, not final scientific truth or live learning state.",
                "support_distribution_summary": "Supported 1, weakened 0, unresolved 0 across 1 currently tracked claim.",
                "governance_scope_summary": "Current picture includes 0 accepted and 1 proposed belief update; rejected and superseded updates are excluded.",
                "support_basis_mix_label": "Grounded mostly in observed labels",
                "support_basis_mix_summary": "The current support picture is grounded mostly in observed labels (1) and remains bounded rather than final.",
                "belief_state_strength_summary": "The current support picture is tentative because it is built entirely from proposed support-change records.",
                "belief_state_readiness_summary": "Read-across remains weak because the current support picture is entirely proposed.",
                "governance_mix_label": "Mostly proposed",
                "chronology_summary_text": "Current support picture relies on 1 active claim-linked support change and keeps 0 superseded plus 0 rejected historical records visible for context.",
                "active_claim_count": 1,
                "supported_claim_count": 1,
                "weakened_claim_count": 0,
                "unresolved_claim_count": 0,
                "accepted_update_count": 0,
                "proposed_update_count": 1,
                "superseded_update_count": 0,
                "rejected_update_count": 0,
                "observed_label_support_count": 1,
                "numeric_rule_based_support_count": 0,
                "unresolved_basis_count": 0,
                "weak_basis_count": 0,
                "last_updated_at": "2026-04-02T12:05:00+00:00",
                "last_update_source": "latest belief update linked to an observed result",
            },
            "belief_state_alignment_label": "Partial alignment",
            "belief_state_alignment_summary": "This session aligns with the current support picture, but the added support remains mostly proposed or otherwise limited.",
        }

        workbench = build_discovery_workbench(
            decision_output=canonical_decision_output(),
            analysis_report={"warnings": [], "top_level_recommendation_summary": "Start with the top candidate."},
            review_queue={},
            session_id=None,
            evaluation_summary={"selected_model": {"name": "rf_isotonic", "calibration_method": "isotonic"}},
            system_version="2.0.0",
            scientific_session_truth=scientific_truth,
        )

        self.assertEqual(workbench["claims_summary"]["claim_count"], 1)
        self.assertEqual(workbench["claim_refs"][0]["claim_id"], "claim_1")
        self.assertEqual(workbench["belief_update_summary"]["support_basis_mix_label"], "Grounded mostly in observed labels")
        self.assertEqual(workbench["belief_state_summary"]["support_basis_mix_label"], "Grounded mostly in observed labels")
        self.assertEqual(workbench["belief_state_summary"]["observed_label_support_count"], 1)
        self.assertIn("plausible follow-up candidate", workbench["claim_refs"][0]["claim_text"].lower())
        self.assertEqual(workbench["claim_refs"][0]["claim_support_role_label"], "Active governed support")
        self.assertEqual(workbench["claim_refs"][0]["claim_support_basis_mix_label"], "Grounded mostly in observed labels")
        self.assertEqual(workbench["claim_refs"][0]["claim_observed_label_support_count"], 1)
        self.assertIn("observed labels", workbench["claim_refs"][0]["claim_support_basis_mix_summary"].lower())
        self.assertIn("active governed support change", workbench["claim_refs"][0]["claim_chronology_summary_text"].lower())
        self.assertEqual(workbench["claim_refs"][0]["claim_actionability_label"], "Action-ready from current active support")
        self.assertEqual(workbench["claim_refs"][0]["claim_actionability_basis_label"], "Current active support basis")
        self.assertEqual(workbench["claim_refs"][0]["claim_next_step_label"], "Follow-up experiment is reasonable now")
        self.assertEqual(workbench["claim_refs"][0]["claim_read_across_label"], "Continuity-aligned claim")
        self.assertEqual(workbench["claim_refs"][0]["claim_prior_support_quality_label"], "Posture-governing continuity")
        self.assertIn("posture-governing support", workbench["claim_refs"][0]["claim_prior_support_quality_summary"].lower())
        self.assertIn("same candidate context", workbench["claim_refs"][0]["claim_read_across_summary"].lower())
        self.assertEqual(workbench["claims_summary"]["claims_with_active_support_count"], 1)
        self.assertIn("claim-level support chronology remains bounded", workbench["claims_summary"]["chronology_summary_text"].lower())
        self.assertEqual(workbench["claims_summary"]["claims_mostly_observed_label_grounded_count"], 1)
        self.assertIn("claim support-basis composition remains bounded", workbench["claims_summary"]["claim_support_basis_summary_text"].lower())
        self.assertEqual(workbench["claims_summary"]["claims_action_ready_follow_up_count"], 1)
        self.assertEqual(workbench["claims_summary"]["claims_action_ready_from_active_support_count"], 1)
        self.assertIn("claim actionability remains bounded", workbench["claims_summary"]["claim_actionability_summary_text"].lower())
        self.assertIn("claim actionability basis remains bounded", workbench["claims_summary"]["claim_actionability_basis_summary_text"].lower())
        self.assertEqual(workbench["claims_summary"]["continuity_aligned_claim_count"], 1)
        self.assertEqual(workbench["claims_summary"]["claims_with_active_governed_continuity_count"], 1)
        self.assertIn("active governed continuity", workbench["claims_summary"]["read_across_summary_text"].lower())
        self.assertEqual(workbench["experiment_request_summary"]["request_count"], 1)
        self.assertEqual(workbench["experiment_request_refs"][0]["experiment_request_id"], "expreq_1")
        self.assertEqual(workbench["experiment_request_refs"][0]["requested_measurement"], "pIC50")
        self.assertEqual(workbench["linked_result_summary"]["result_count"], 1)
        self.assertEqual(workbench["experiment_result_refs"][0]["experiment_result_id"], "expres_1")
        self.assertEqual(workbench["experiment_result_refs"][0]["result_quality"], "confirmatory")
        self.assertEqual(workbench["belief_update_summary"]["update_count"], 1)
        self.assertEqual(workbench["belief_update_summary"]["active_count"], 1)
        self.assertEqual(workbench["belief_update_refs"][0]["belief_update_id"], "belief_1")
        self.assertEqual(workbench["belief_update_refs"][0]["update_direction"], "strengthened")
        self.assertEqual(workbench["belief_update_refs"][0]["chronology_label"], "Current proposed support change")
        self.assertEqual(workbench["belief_update_refs"][0]["support_input_quality_label"], "Cautious interpretation basis")
        self.assertEqual(workbench["session_support_role_label"], "Contributed current support")
        self.assertIn("active target-scoped picture", workbench["session_support_role_summary"].lower())
        self.assertEqual(workbench["belief_update_summary"]["chronology_mix_label"], "Current support only")
        self.assertEqual(workbench["belief_state_summary"]["active_claim_count"], 1)
        self.assertIn("active claim-linked support change", workbench["belief_state_summary"]["chronology_summary_text"].lower())
        self.assertEqual(workbench["belief_state_ref"]["belief_state_id"], "beliefstate_1")
        self.assertEqual(workbench["belief_state_alignment_label"], "Partial alignment")
        self.assertIn("mostly proposed", workbench["belief_state_alignment_summary"])
        self.assertEqual(workbench["scientific_decision_summary"]["decision_status_label"], "Active governed follow-up basis")
        self.assertEqual(workbench["scientific_decision_summary"]["next_step_label"], "Bounded follow-up is reasonable now")
        self.assertEqual(workbench["scientific_decision_summary"]["result_state_label"], "Observed results recorded")

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
        self.assertIn("Observed measurement evidence", response.text)
        self.assertIn("Observed or derived data facts", response.text)
        self.assertIn("Evidence loop", response.text)
        self.assertIn("Learning boundary", response.text)

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
        self.assertIn("Observed measurement evidence", response.text)
        self.assertIn("Stronger evidence support", response.text)
        self.assertIn("Evidence loop", response.text)
        self.assertIn("Memory is not learning", response.text)

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
