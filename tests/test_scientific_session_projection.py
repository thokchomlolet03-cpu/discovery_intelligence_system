import unittest
from pathlib import Path
from unittest.mock import patch

from system.dashboard_data import build_dashboard_context
from system.discovery_workbench import build_discovery_workbench
from system.session_history import build_session_history_context
from system.services.claim_read_service import build_claim_detail_read_model
from system.services.epistemic_ui_service import (
    build_candidate_epistemic_context,
    build_candidate_epistemic_detail_reveal,
    build_focused_claim_inspection,
    build_focused_experiment_inspection,
    build_session_epistemic_detail_reveal,
    build_session_epistemic_summary,
)
from system.services.experiment_read_service import build_session_experiment_lifecycle_read_model
from system.services.epistemic_experiment_priority_service import assess_epistemic_experiment_priority
from system.services.claim_service import materialize_session_claims
from system.services.contradiction_service import build_session_contradictions
from system.services.belief_state_service import assess_belief_revision
from system.services.material_goal_service import build_material_goal_specification
from system.services.material_goal_retrieval_service import build_material_goal_evidence_result
from system.services.experiment_service import create_experiment_request, record_experiment_result
from system.services.scientific_session_projection_service import build_scientific_session_projection
from system.services.scientific_state_service import build_run_metadata_record


class ScientificSessionProjectionTest(unittest.TestCase):
    def test_material_goal_specification_requires_clarification_when_critical_constraints_are_missing(self):
        spec = build_material_goal_specification(
            session_id="session_goal",
            workspace_id="workspace_1",
            raw_user_goal="I need a biodegradable polymer for packaging.",
        )

        self.assertEqual(spec["requirement_status"], "insufficient_needs_clarification")
        self.assertIn("desired_properties", spec["missing_critical_requirements"])
        self.assertIn("operating_environment", spec["missing_critical_requirements"])
        self.assertGreater(len(spec["clarification_questions"]), 0)
        self.assertFalse(spec["provenance_markers"]["silent_fill_of_critical_requirements"])

    def test_material_goal_specification_builds_structured_target_when_sufficient(self):
        spec = build_material_goal_specification(
            session_id="session_goal",
            workspace_id="workspace_1",
            raw_user_goal=(
                "Need a polymer packaging film with oxygen barrier and moisture barrier "
                "for humid food packaging, stable for 6 months and compostable after use."
            ),
        )

        self.assertEqual(spec["requirement_status"], "sufficiently_specified")
        self.assertEqual(spec["missing_critical_requirements"], [])
        self.assertIn("packaging", spec["structured_requirements"]["target_material_function"])
        self.assertIn("barrier", " ".join(spec["structured_requirements"]["desired_properties"]))
        self.assertIn("humid", " ".join(spec["structured_requirements"]["operating_environment"]))
        self.assertIn("months", " ".join(spec["structured_requirements"]["lifecycle_window"]))

    def test_material_goal_retrieval_blocks_when_goal_is_not_sufficiently_specified(self):
        goal_spec = build_material_goal_specification(
            session_id="session_goal",
            workspace_id="workspace_1",
            raw_user_goal="Need a biodegradable polymer for packaging.",
        )

        retrieval = build_material_goal_evidence_result(
            session_id="session_goal",
            workspace_id="workspace_1",
            goal_specification=goal_spec,
            evidence_records=[],
            model_outputs=[],
            recommendations=[],
            claims=[],
            contradictions=[],
        )

        self.assertEqual(retrieval["retrieval_status"], "blocked_goal_insufficient")
        self.assertEqual(retrieval["retrieval_sufficiency"], "no_grounded_evidence")
        self.assertEqual(retrieval["candidate_material_directions"], [])
        self.assertIn("clarified", retrieval["limitation_lines"][0].lower())

    def test_material_goal_retrieval_organizes_grounded_candidate_directions(self):
        goal_spec = build_material_goal_specification(
            session_id="session_goal",
            workspace_id="workspace_1",
            raw_user_goal=(
                "Need a polymer packaging film with oxygen barrier and moisture barrier "
                "for humid food packaging, stable for 6 months and compostable after use."
            ),
        )

        retrieval = build_material_goal_evidence_result(
            session_id="session_goal",
            workspace_id="workspace_1",
            goal_specification=goal_spec,
            evidence_records=[
                {
                    "record_id": 1,
                    "candidate_id": "cand_pack",
                    "canonical_smiles": "CCO",
                    "evidence_type": "observed_measurement",
                    "assay": "humid food packaging barrier test",
                    "observed_value": 0.12,
                    "payload": {
                        "material_family": "compostable polyester film",
                        "application": "food packaging film",
                        "properties": ["oxygen barrier", "moisture barrier"],
                        "environment": "humid storage",
                        "lifecycle": "stable for months before composting",
                    },
                }
            ],
            model_outputs=[
                {
                    "record_id": 2,
                    "candidate_id": "cand_pack",
                    "canonical_smiles": "CCO",
                    "predicted_value": 0.81,
                    "confidence": 0.74,
                    "payload": {
                        "material_family": "compostable polyester film",
                        "application": "humid food packaging",
                    },
                }
            ],
            recommendations=[
                {
                    "record_id": 3,
                    "candidate_id": "cand_pack",
                    "canonical_smiles": "CCO",
                    "rank": 1,
                    "bucket": "learn",
                    "rationale_summary": "Packaging film direction with oxygen barrier and compostable end-of-life context.",
                    "payload": {
                        "material_family": "compostable polyester film",
                        "application": "food packaging film",
                    },
                }
            ],
            claims=[{"claim_id": "claim_1", "candidate_id": "cand_pack", "canonical_smiles": "CCO"}],
            contradictions=[],
        )

        self.assertEqual(retrieval["retrieval_status"], "retrieval_complete")
        self.assertEqual(retrieval["retrieval_sufficiency"], "candidate_directions_available")
        self.assertEqual(len(retrieval["candidate_material_directions"]), 1)
        self.assertIn("compostable polyester film", retrieval["candidate_material_directions"][0]["direction_label"])
        self.assertGreaterEqual(len(retrieval["candidate_material_directions"][0]["supporting_evidence_lines"]), 2)

    def test_material_goal_retrieval_surfaces_weak_partial_evidence_without_claiming_answer(self):
        goal_spec = build_material_goal_specification(
            session_id="session_goal",
            workspace_id="workspace_1",
            raw_user_goal=(
                "Need a polymer packaging film with oxygen barrier and moisture barrier "
                "for humid food packaging, stable for 6 months and compostable after use."
            ),
        )

        retrieval = build_material_goal_evidence_result(
            session_id="session_goal",
            workspace_id="workspace_1",
            goal_specification=goal_spec,
            evidence_records=[],
            model_outputs=[
                {
                    "record_id": 2,
                    "candidate_id": "cand_partial",
                    "canonical_smiles": "CCC",
                    "predicted_value": 0.61,
                    "confidence": 0.59,
                    "payload": {
                        "application": "humid packaging film",
                        "properties": ["oxygen barrier"],
                    },
                }
            ],
            recommendations=[],
            claims=[],
            contradictions=[],
        )

        self.assertEqual(retrieval["retrieval_sufficiency"], "weak_partial_evidence")
        self.assertEqual(len(retrieval["candidate_material_directions"]), 1)
        self.assertIn("does not yet justify a best-supported material answer", " ".join(retrieval["limitation_lines"]).lower())

    def test_contradiction_aware_belief_revision_keeps_mixed_structure_unresolved(self):
        revision = assess_belief_revision(
            claim={"claim_id": "claim_1", "claim_text": "Candidate cand_1 should remain prioritized."},
            experiment_result={"result_id": "res_1", "outcome": "supportive"},
            current_belief_state={"current_state": "unresolved", "current_strength": "tentative"},
            contradictions=[
                {
                    "contradiction_id": "contr_1",
                    "status": "active",
                    "contradiction_type": "result_vs_claim",
                }
            ],
            claim_links=[
                {"relation_type": "supports"},
                {"relation_type": "weakens"},
                {"relation_type": "derived_from"},
            ],
            prior_updates=[],
        )

        self.assertEqual(revision["current_state"], "unresolved")
        self.assertEqual(revision["current_strength"], "mixed")
        self.assertEqual(revision["contradiction_pressure"], "moderate")
        self.assertIn("active contradiction", revision["revision_rationale"].lower())

    def test_contradiction_materialization_is_conservative_and_grounded(self):
        contradictions = build_session_contradictions(
            session_id="session_1",
            workspace_id="workspace_1",
            claims=[
                {
                    "claim_id": "claim_1",
                    "claim_scope": "candidate",
                    "claim_text": "Candidate cand_1 should remain prioritized.",
                }
            ],
            claim_evidence_links=[
                {
                    "claim_id": "claim_1",
                    "link_id": "link_weak_1",
                    "linked_object_type": "evidence",
                    "linked_object_id": "21",
                    "relation_type": "weakens",
                    "summary": "Observed measurement undercuts the current candidate-priority claim.",
                    "provenance_markers": {"link_source": "test"},
                },
                {
                    "claim_id": "claim_1",
                    "link_id": "link_ctx_1",
                    "linked_object_type": "recommendation",
                    "linked_object_id": "9",
                    "relation_type": "context_only",
                    "summary": "Recommendation context only.",
                },
            ],
            experiment_results=[
                {
                    "result_id": "res_1",
                    "request_id": "req_1",
                    "claim_id": "claim_1",
                    "outcome": "contradictory",
                    "result_summary": {"summary": "Observed result contradicts expected potency."},
                    "provenance_markers": {"result_source": "test"},
                }
            ],
            belief_updates=[
                {
                    "update_id": "upd_1",
                    "claim_id": "claim_1",
                    "deterministic_rule": "contradictory_result_challenges_claim",
                    "post_belief_state": {"current_state": "challenged"},
                    "update_reason": "Contradictory result recorded.",
                    "provenance_markers": {"update_source": "test"},
                }
            ],
        )

        self.assertEqual(len(contradictions), 3)
        self.assertEqual(
            {item["contradiction_type"] for item in contradictions},
            {"evidence_vs_claim", "result_vs_claim", "belief_transition_conflict"},
        )
        self.assertEqual(sum(1 for item in contradictions if item["status"] == "active"), 2)
        self.assertEqual(sum(1 for item in contradictions if item["status"] == "unresolved"), 1)

    def test_epistemic_experiment_priority_assessment_favors_unresolved_thinly_supported_claims(self):
        request = {
            "request_id": "req_priority",
            "claim_id": "claim_priority",
            "tested_claim_id": "claim_priority",
            "experiment_intent": "claim_test",
            "expected_learning_value": "Reduce uncertainty around whether the recommendation-derived claim should remain trusted.",
            "linked_claim_evidence_snapshot": [
                {
                    "linked_object_type": "recommendation",
                    "relation_type": "derived_from",
                    "summary": "Derived from ranked recommendation cand_1.",
                }
            ],
        }
        claim = {"claim_id": "claim_priority", "claim_scope": "candidate"}
        weak_links = [
            {
                "claim_id": "claim_priority",
                "relation_type": "derived_from",
                "linked_object_type": "recommendation",
            }
        ]
        strong_links = [
            {
                "claim_id": "claim_priority",
                "relation_type": "supports",
                "linked_object_type": "evidence",
            },
            {
                "claim_id": "claim_priority",
                "relation_type": "supports",
                "linked_object_type": "model_output",
            },
            {
                "claim_id": "claim_priority",
                "relation_type": "context_only",
                "linked_object_type": "recommendation",
            },
        ]

        unresolved_priority = assess_epistemic_experiment_priority(
            request=request,
            claim=claim,
            belief_state={
                "current_state": "unresolved",
                "contradiction_pressure": "moderate",
                "support_balance_summary": "1 supporting line(s), 1 weakening line(s), 0 context-only line(s), 1 derived line(s); current attached structure is mixed.",
                "latest_revision_rationale": "Belief remains unresolved because contradiction pressure is still active.",
            },
            claim_links=weak_links,
            unresolved_state="no_result_recorded",
            result_count=0,
            has_belief_update=False,
        )
        settled_priority = assess_epistemic_experiment_priority(
            request=request,
            claim=claim,
            belief_state={
                "current_state": "supported",
                "contradiction_pressure": "low",
                "support_balance_summary": "2 supporting line(s), 0 weakening line(s), 1 context-only line(s), 0 derived line(s); current attached structure leans supportive.",
                "latest_revision_rationale": "A supportive result increased support because contradiction pressure is currently low.",
            },
            claim_links=strong_links,
            unresolved_state="belief_updated",
            result_count=1,
            has_belief_update=True,
        )

        self.assertEqual(unresolved_priority["epistemic_priority_band"], "high")
        self.assertGreater(unresolved_priority["epistemic_priority_score"], settled_priority["epistemic_priority_score"])
        self.assertGreater(unresolved_priority["support_weakness_signal"], settled_priority["support_weakness_signal"])
        self.assertGreater(unresolved_priority["belief_change_opportunity_signal"], settled_priority["belief_change_opportunity_signal"])
        self.assertGreater(unresolved_priority["contradiction_attention_signal"], settled_priority["contradiction_attention_signal"])
        self.assertGreater(unresolved_priority["unresolved_mixed_structure_signal"], settled_priority["unresolved_mixed_structure_signal"])

    def test_claim_detail_includes_grouped_claim_evidence_links(self):
        claim = {
            "claim_id": "claim_candidate",
            "session_id": "session_1",
            "workspace_id": "workspace_1",
            "claim_scope": "candidate",
            "claim_type": "candidate_experiment_priority",
            "claim_text": "Candidate cand_1 is a priority experimental candidate.",
            "status": "active",
            "support_links": {},
            "source_basis": "recommended",
            "provenance_markers": {},
        }
        with patch(
            "system.services.claim_read_service.scientific_state_repository.get_claim",
            return_value=claim,
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_candidate_states",
            return_value=[{"candidate_id": "cand_1", "canonical_smiles": "CCO"}],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.get_run_metadata",
            return_value={},
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_experiment_requests",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_experiment_results",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_belief_updates",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.get_belief_state",
            side_effect=FileNotFoundError("missing"),
        ), patch(
            "system.services.claim_read_service.build_session_experiment_lifecycle_read_model",
            return_value={"claim_items": [], "experiment_items": []},
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_claim_evidence_links",
            return_value=[
                {
                    "link_id": "link_1",
                    "linked_object_type": "recommendation",
                    "linked_object_id": "11",
                    "relation_type": "derived_from",
                    "summary": "Derived from recommendation",
                },
                {
                    "link_id": "link_2",
                    "linked_object_type": "evidence",
                    "linked_object_id": "21",
                    "relation_type": "context_only",
                    "summary": "Observed measurement context",
                },
            ],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_contradictions",
            return_value=[
                {
                    "contradiction_id": "contr_1",
                    "claim_id": "claim_candidate",
                    "contradiction_scope": "claim",
                    "contradiction_type": "result_vs_claim",
                    "source_object_type": "experiment_result",
                    "source_object_id": "res_9",
                    "status": "active",
                    "summary": "Recorded result conflicts with the current claim.",
                    "provenance_markers": {"materialization_rule": "test"},
                }
            ],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_evidence_records",
            return_value=[
                {
                    "record_id": 21,
                    "evidence_type": "observed_measurement",
                    "source_row_index": 3,
                    "source_column": "pic50",
                    "assay": "assay_a",
                    "target_name": "pIC50",
                    "observed_value": 7.2,
                }
            ],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_model_outputs",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_recommendations",
            return_value=[
                {
                    "record_id": 11,
                    "rank": 1,
                    "bucket": "exploit",
                    "risk": "low",
                    "status": "approved",
                    "priority_score": 0.82,
                    "experiment_value": 0.71,
                }
            ],
        ):
            detail = build_claim_detail_read_model(claim_id="claim_candidate")

        self.assertEqual(detail["attachment_context"]["claim_evidence_link_count"], 2)
        self.assertEqual(detail["attachment_context"]["contradiction_count"], 1)
        self.assertEqual(detail["attachment_context"]["active_contradiction_count"], 1)
        self.assertEqual(detail["attachment_context"]["claim_evidence_relation_counts"]["derived_from"], 1)
        self.assertEqual(detail["attachment_context"]["claim_evidence_links"][0]["object_summary"]["label"], "recommendation")
        self.assertEqual(detail["attachment_context"]["contradictions"][0]["contradiction_type"], "result_vs_claim")

    def test_focused_claim_inspection_exposes_claim_evidence_link_groups(self):
        focused = build_focused_claim_inspection(
            claim_detail_items=[
                {
                    "claim_id": "claim_candidate",
                    "claim": {
                        "claim_type": "candidate_experiment_priority",
                        "claim_status": "active",
                        "claim_scope": "candidate",
                        "claim_text": "Candidate cand_1 is a priority experimental candidate.",
                    },
                    "attachment_context": {
                        "support_basis_summary": "Supported by recommendation record.",
                        "claim_evidence_link_count": 2,
                        "claim_evidence_relation_counts": {"derived_from": 1, "context_only": 1},
                        "contradiction_count": 1,
                        "active_contradiction_count": 1,
                        "claim_evidence_links": [
                            {
                                "relation_type": "derived_from",
                                "linked_object_type": "recommendation",
                                "summary": "Derived from recommendation",
                                "object_summary": {"label": "recommendation", "context_bits": ["rank 1", "exploit"]},
                            },
                            {
                                "relation_type": "context_only",
                                "linked_object_type": "evidence",
                                "summary": "Observed value context",
                                "object_summary": {"label": "observed measurement", "context_bits": ["row 3", "value 7.2"]},
                            },
                        ],
                        "contradictions": [
                            {
                                "contradiction_id": "contr_1",
                                "contradiction_type": "result_vs_claim",
                                "status": "active",
                                "summary": "Recorded result conflicts with the current claim.",
                                "object_summary": {"label": "experiment result", "context_bits": ["outcome contradictory"]},
                            }
                        ],
                        "candidate_context": {"candidate_id": "cand_1"},
                        "run_context": {},
                    },
                    "experiment_detail": {"request_count": 0, "result_count": 0, "pending_request_count": 0},
                    "current_belief_state": {
                        "current_state": "unresolved",
                        "current_strength": "tentative",
                        "contradiction_pressure": "moderate",
                        "support_balance_summary": "1 supporting line(s), 1 weakening line(s), 0 context-only line(s), 0 derived line(s); current attached structure is mixed.",
                        "latest_revision_rationale": "Belief remains unresolved because contradiction pressure is still active.",
                    },
                    "belief_update_summary": {
                        "update_count": 1,
                        "items": [
                            {
                                "revision_rationale": "Belief remains unresolved because contradiction pressure is still active.",
                                "triggering_contradiction_ids": ["contr_1"],
                            }
                        ],
                    },
                    "diagnostics": {"experiment_lifecycle_unresolved_state": "no_experiment_request"},
                }
            ]
        )

        self.assertEqual(focused["claim_evidence_link_count"], 2)
        self.assertEqual(focused["contradiction_count"], 1)
        self.assertEqual(focused["active_contradiction_count"], 1)
        self.assertEqual(focused["belief_contradiction_pressure"], "moderate")
        self.assertIn("contradiction pressure", focused["latest_revision_rationale"].lower())
        self.assertEqual(focused["latest_triggering_contradiction_ids"], ["contr_1"])
        self.assertEqual(len(focused["contradictions_by_status"]["active"]), 1)
        self.assertEqual(len(focused["claim_evidence_links_by_relation"]["derived_from"]), 1)
        self.assertEqual(focused["claim_choices"][0]["claim_evidence_relation_counts"]["context_only"], 1)

    def test_projection_prefers_canonical_state_and_keeps_legacy_dependencies_explicit(self):
        canonical_state = {
            "session_id": "session_1",
            "target_definition": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "measurement_column": "pic50",
                "dataset_type": "measurement_dataset",
            },
            "evidence_records": [
                {"evidence_type": "structure_input"},
                {"evidence_type": "observed_measurement"},
                {"evidence_type": "observed_label"},
            ],
            "model_outputs": [
                {
                    "candidate_id": "cand_1",
                    "confidence": 0.81,
                    "uncertainty": 0.12,
                    "baseline_fallback_used": True,
                    "bridge_state_summary": "Legacy baseline bundle reused for this session.",
                }
            ],
            "recommendations": [
                {
                    "candidate_id": "cand_1",
                    "canonical_smiles": "CCO",
                    "rank": 1,
                    "bucket": "exploit",
                    "risk": "medium",
                    "status": "approved",
                    "priority_score": 0.78,
                    "experiment_value": 0.72,
                    "rationale": {"trust_label": "Stronger trust"},
                    "governance": {"review_summary": {"status": "approved", "reviewed_at": "2026-04-01T10:00:00+00:00"}},
                }
            ],
            "carryover_records": [
                {
                    "source_session_id": "session_old",
                    "canonical_smiles": "CCO",
                    "source_reviewed_at": "2026-03-30T10:00:00+00:00",
                }
            ],
        }
        analysis_report = {
            "modeling_mode": "regression",
            "decision_intent": "prioritize_experiments",
            "ranking_policy": {"primary_score_label": "Priority score"},
            "run_contract": {"modeling_mode": "regression", "scoring_mode": "balanced"},
            "comparison_anchors": {"comparison_ready": True, "target_name": "pIC50", "target_kind": "regression"},
            "ranking_diagnostics": {"out_of_domain_rate": 0.2},
            "top_level_recommendation_summary": "Start with cand_1.",
        }
        decision_payload = {
            "artifact_state": "ok",
            "top_experiments": [{"candidate_id": "cand_1", "canonical_smiles": "CCO"}],
            "decision_intent": "prioritize_experiments",
            "modeling_mode": "regression",
        }

        with patch(
            "system.services.scientific_session_projection_service.load_canonical_session_scientific_state",
            return_value=canonical_state,
        ), patch(
            "system.services.scientific_session_projection_service.load_analysis_report_payload",
            return_value=analysis_report,
        ), patch(
            "system.services.scientific_session_projection_service.load_decision_artifact_payload",
            return_value=decision_payload,
        ):
            projection = build_scientific_session_projection(
                session_record={"session_id": "session_1", "workspace_id": "workspace_1", "source_name": "upload.csv"},
                workspace_id="workspace_1",
            )

        self.assertEqual(projection["target_definition"]["target_name"], "pIC50")
        self.assertEqual(projection["measurement_summary"]["rows_with_values"], 1)
        self.assertEqual(projection["governance_summary"]["approved"], 1)
        self.assertEqual(projection["carryover_summary"]["source_session_count"], 1)
        self.assertTrue(projection["diagnostics"]["canonical_projection_used"])
        self.assertEqual(projection["diagnostics"]["field_provenance"]["run_contract"], "legacy_artifact")
        self.assertTrue(projection["diagnostics"]["baseline_model_fallback_visible"])
        self.assertEqual(projection["ranking_diagnostics"]["diagnostic_source"], "legacy_analysis_report")

    def test_projection_falls_back_to_legacy_when_canonical_state_missing(self):
        analysis_report = {
            "target_definition": {
                "target_name": "solubility",
                "target_kind": "regression",
                "measurement_column": "solubility",
                "dataset_type": "measurement_dataset",
            },
            "measurement_summary": {"rows_with_values": 4, "rows_with_labels": 0},
            "modeling_mode": "regression",
            "decision_intent": "prioritize_experiments",
            "comparison_anchors": {"comparison_ready": False},
        }
        decision_payload = {
            "artifact_state": "ok",
            "top_experiments": [
                {"candidate_id": "cand_9", "canonical_smiles": "CCN", "rank": 1, "bucket": "learn", "status": "suggested"}
            ],
            "target_definition": {
                "target_name": "solubility",
                "target_kind": "regression",
                "measurement_column": "solubility",
                "dataset_type": "measurement_dataset",
            },
            "decision_intent": "prioritize_experiments",
            "modeling_mode": "regression",
        }

        with patch(
            "system.services.scientific_session_projection_service.load_canonical_session_scientific_state",
            side_effect=FileNotFoundError("missing"),
        ), patch(
            "system.services.scientific_session_projection_service.load_analysis_report_payload",
            return_value=analysis_report,
        ), patch(
            "system.services.scientific_session_projection_service.load_decision_artifact_payload",
            return_value=decision_payload,
        ):
            projection = build_scientific_session_projection(
                session_record={"session_id": "legacy_session", "workspace_id": "workspace_1", "source_name": "legacy.csv"},
                workspace_id="workspace_1",
            )

        self.assertTrue(projection["diagnostics"]["legacy_fallback_used"])
        self.assertEqual(projection["target_definition"]["target_name"], "solubility")
        self.assertEqual(len(projection["recommendations"]), 1)
        self.assertIn("recommendations", projection["diagnostics"]["legacy_merge_fields"])

    def test_projection_preserves_visible_recommendation_and_review_conclusions(self):
        canonical_state = {
            "session_id": "session_parity",
            "target_definition": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "measurement_column": "pic50",
                "dataset_type": "measurement_dataset",
            },
            "evidence_records": [
                {"evidence_type": "structure_input"},
                {"evidence_type": "structure_input"},
                {"evidence_type": "observed_measurement"},
            ],
            "model_outputs": [],
            "recommendations": [
                {
                    "candidate_id": "cand_1",
                    "canonical_smiles": "CCO",
                    "rank": 1,
                    "bucket": "exploit",
                    "risk": "low",
                    "status": "approved",
                    "priority_score": 0.8,
                    "experiment_value": 0.7,
                    "rationale": {"trust_label": "Stronger trust"},
                    "governance": {"review_summary": {"status": "approved", "reviewed_at": "2026-04-01T10:00:00+00:00"}},
                },
                {
                    "candidate_id": "cand_2",
                    "canonical_smiles": "CCN",
                    "rank": 2,
                    "bucket": "learn",
                    "risk": "high",
                    "status": "suggested",
                    "priority_score": 0.5,
                    "experiment_value": 0.6,
                    "rationale": {"trust_label": "High caution"},
                    "governance": {},
                },
            ],
            "carryover_records": [],
        }
        analysis_report = {
            "modeling_mode": "regression",
            "decision_intent": "prioritize_experiments",
            "comparison_anchors": {"comparison_ready": True, "target_name": "pIC50", "target_kind": "regression"},
            "run_contract": {"modeling_mode": "regression", "scoring_mode": "balanced"},
            "ranking_policy": {"primary_score_label": "Priority score"},
            "ranking_diagnostics": {"out_of_domain_rate": 0.2},
        }
        decision_payload = {
            "artifact_state": "ok",
            "summary": {"candidate_count": 2, "top_experiment_value": 0.7},
            "top_experiments": [
                {"candidate_id": "cand_1", "bucket": "exploit", "status": "approved"},
                {"candidate_id": "cand_2", "bucket": "learn", "status": "suggested"},
            ],
            "decision_intent": "prioritize_experiments",
            "modeling_mode": "regression",
        }

        with patch(
            "system.services.scientific_session_projection_service.load_canonical_session_scientific_state",
            return_value=canonical_state,
        ), patch(
            "system.services.scientific_session_projection_service.load_analysis_report_payload",
            return_value=analysis_report,
        ), patch(
            "system.services.scientific_session_projection_service.load_decision_artifact_payload",
            return_value=decision_payload,
        ):
            projection = build_scientific_session_projection(
                session_record={"session_id": "session_parity", "workspace_id": "workspace_1", "source_name": "upload.csv"},
                workspace_id="workspace_1",
            )

        self.assertEqual(projection["measurement_summary"]["rows_with_values"], 1)
        self.assertEqual(projection["outcome_profile"]["leading_bucket"], "exploit")
        self.assertEqual(projection["governance_summary"]["approved"], 1)
        self.assertEqual(projection["governance_summary"]["pending_review"], 1)

    def test_projection_synthesizes_run_level_fields_when_legacy_artifacts_do_not_supply_them(self):
        canonical_state = {
            "session_id": "session_synth",
            "target_definition": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "measurement_column": "pic50",
                "dataset_type": "measurement_dataset",
            },
            "evidence_records": [
                {"evidence_type": "structure_input"},
                {"evidence_type": "observed_measurement"},
            ],
            "model_outputs": [
                {
                    "candidate_id": "cand_1",
                    "canonical_smiles": "CCO",
                    "model_name": "rf_regressor",
                    "model_family": "random_forest",
                    "training_scope": "session_trained",
                    "confidence": 0.71,
                    "uncertainty": 0.21,
                    "novelty": 0.44,
                    "applicability": {"status": "out_of_domain"},
                    "diagnostics": {},
                }
            ],
            "recommendations": [
                {
                    "candidate_id": "cand_1",
                    "canonical_smiles": "CCO",
                    "rank": 1,
                    "bucket": "learn",
                    "risk": "high",
                    "status": "suggested",
                    "priority_score": 0.63,
                    "experiment_value": 0.69,
                    "rationale": {"trust_label": "High caution"},
                    "governance": {},
                }
            ],
            "carryover_records": [],
        }

        with patch(
            "system.services.scientific_session_projection_service.load_canonical_session_scientific_state",
            return_value=canonical_state,
        ), patch(
            "system.services.scientific_session_projection_service.load_analysis_report_payload",
            return_value={"modeling_mode": "regression"},
        ), patch(
            "system.services.scientific_session_projection_service.load_decision_artifact_payload",
            return_value={"artifact_state": "ok", "decision_intent": "prioritize_experiments", "modeling_mode": "regression"},
        ):
            projection = build_scientific_session_projection(
                session_record={"session_id": "session_synth", "workspace_id": "workspace_1", "source_name": "upload.csv"},
                workspace_id="workspace_1",
            )

        self.assertEqual(projection["diagnostics"]["field_provenance"]["run_contract"], "projection_synthesized")
        self.assertEqual(projection["diagnostics"]["field_provenance"]["comparison_anchors"], "projection_synthesized")
        self.assertEqual(projection["diagnostics"]["field_provenance"]["ranking_policy"], "projection_synthesized")
        self.assertEqual(projection["diagnostics"]["field_provenance"]["ranking_diagnostics"], "projection_synthesized")
        self.assertEqual(projection["ranking_diagnostics"]["high_caution_count"], 1)
        self.assertEqual(projection["candidate_projection_rows"][0]["carryover_summary"]["record_count"], 0)

    def test_projection_prefers_canonical_persisted_run_metadata_over_legacy_fields(self):
        canonical_state = {
            "session_id": "session_runmeta",
            "target_definition": {
                "target_name": "solubility",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "measurement_column": "solubility",
                "dataset_type": "measurement_dataset",
            },
            "evidence_records": [{"evidence_type": "structure_input"}],
            "model_outputs": [],
            "recommendations": [],
            "carryover_records": [],
            "candidate_states": [],
            "run_metadata": {
                "run_contract": {"selected_model_name": "canonical_model", "modeling_mode": "regression"},
                "comparison_anchors": {"target_name": "solubility", "comparison_ready": True},
                "ranking_policy": {"primary_score_label": "Canonical policy"},
                "ranking_diagnostics": {"out_of_domain_rate": 0.42},
                "trust_summary": {"bridge_state_summary": "Canonical fallback summary."},
            },
        }
        analysis_report = {
            "run_contract": {"selected_model_name": "legacy_model"},
            "comparison_anchors": {"target_name": "legacy_target", "comparison_ready": False},
            "ranking_policy": {"primary_score_label": "Legacy policy"},
            "ranking_diagnostics": {"out_of_domain_rate": 0.9},
        }

        with patch(
            "system.services.scientific_session_projection_service.load_canonical_session_scientific_state",
            return_value=canonical_state,
        ), patch(
            "system.services.scientific_session_projection_service.load_analysis_report_payload",
            return_value=analysis_report,
        ), patch(
            "system.services.scientific_session_projection_service.load_decision_artifact_payload",
            return_value={"artifact_state": "ok"},
        ):
            projection = build_scientific_session_projection(
                session_record={"session_id": "session_runmeta", "workspace_id": "workspace_1"},
                workspace_id="workspace_1",
            )

        self.assertEqual(projection["run_contract"]["selected_model_name"], "canonical_model")
        self.assertEqual(projection["comparison_anchors"]["target_name"], "solubility")
        self.assertEqual(projection["ranking_policy"]["primary_score_label"], "Canonical policy")
        self.assertEqual(projection["ranking_diagnostics"]["out_of_domain_rate"], 0.42)
        self.assertEqual(projection["diagnostics"]["field_provenance"]["run_contract"], "canonical_persisted_run_metadata")
        self.assertEqual(projection["diagnostics"]["field_provenance"]["comparison_anchors"], "canonical_persisted_run_metadata")
        self.assertEqual(projection["diagnostics"]["field_provenance"]["ranking_policy"], "canonical_persisted_run_metadata")
        self.assertEqual(projection["diagnostics"]["field_provenance"]["ranking_diagnostics"], "canonical_persisted_run_metadata")

    def test_run_metadata_record_builds_deterministic_canonical_payload(self):
        payload = build_run_metadata_record(
            session_id="session_build",
            workspace_id="workspace_1",
            created_by_user_id="user_1",
            result={
                "source_name": "upload.csv",
                "input_type": "structure_only_screening",
                "decision_intent": "prioritize_experiments",
                "modeling_mode": "regression",
                "scoring_mode": "balanced",
                "run_contract": {"selected_model_name": "rf_regressor", "training_scope": "session_trained"},
                "comparison_anchors": {"target_name": "pIC50", "comparison_ready": True},
                "analysis_report": {"ranking_policy": {"primary_score_label": "Priority score"}},
                "contract_versions": {"run_contract_version": "run_contract.v1"},
                "scientific_contract": {"fallback_reason": ""},
            },
            target_definition={"target_name": "pIC50", "target_kind": "regression"},
            model_outputs=[
                {
                    "candidate_id": "cand_1",
                    "uncertainty": 0.2,
                    "applicability": {"status": "out_of_domain"},
                    "baseline_fallback_used": False,
                }
            ],
            recommendations=[
                {"candidate_id": "cand_1", "risk": "high"},
                {"candidate_id": "cand_2", "risk": "medium"},
            ],
        )

        self.assertEqual(payload["session_id"], "session_build")
        self.assertEqual(payload["run_contract"]["selected_model_name"], "rf_regressor")
        self.assertEqual(payload["comparison_anchors"]["target_name"], "pIC50")
        self.assertEqual(payload["ranking_policy"]["primary_score_label"], "Priority score")
        self.assertEqual(payload["ranking_diagnostics"]["high_caution_count"], 1)
        self.assertEqual(payload["provenance_markers"]["run_contract_source"], "pipeline_result")

    def test_projection_prefers_canonical_candidate_state_for_candidate_overlays(self):
        canonical_state = {
            "session_id": "session_candidate_state",
            "target_definition": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "measurement_column": "pic50",
                "dataset_type": "measurement_dataset",
            },
            "evidence_records": [],
            "model_outputs": [],
            "recommendations": [
                {
                    "candidate_id": "cand_1",
                    "canonical_smiles": "CCO",
                    "rank": 1,
                    "bucket": "exploit",
                    "risk": "low",
                    "status": "suggested",
                    "priority_score": 0.7,
                    "experiment_value": 0.6,
                }
            ],
            "carryover_records": [],
            "candidate_states": [
                {
                    "candidate_id": "cand_1",
                    "smiles": "CCO",
                    "canonical_smiles": "CCO",
                    "rank": 1,
                    "predictive_summary": {"confidence": 0.91, "uncertainty": 0.14, "novelty": 0.22},
                    "recommendation_summary": {
                        "bucket": "learn",
                        "risk": "high",
                        "status": "approved",
                        "priority_score": 0.88,
                        "experiment_value": 0.77,
                        "rationale": {"trust_label": "High caution"},
                    },
                    "governance_summary": {
                        "status": "approved",
                        "review_summary": {"status": "approved", "reviewed_at": "2026-04-01T10:00:00+00:00"},
                    },
                    "carryover_summary": {"record_count": 3, "continuity_source": "canonical_carryover"},
                    "trust_summary": {"trust_label": "High caution", "trust_summary": "Stored canonical caution summary."},
                    "provenance_markers": {"predictive_source": "model_output_records"},
                }
            ],
            "run_metadata": {},
        }

        with patch(
            "system.services.scientific_session_projection_service.load_canonical_session_scientific_state",
            return_value=canonical_state,
        ), patch(
            "system.services.scientific_session_projection_service.load_analysis_report_payload",
            return_value={"modeling_mode": "regression"},
        ), patch(
            "system.services.scientific_session_projection_service.load_decision_artifact_payload",
            return_value={"artifact_state": "ok"},
        ):
            projection = build_scientific_session_projection(
                session_record={"session_id": "session_candidate_state", "workspace_id": "workspace_1"},
                workspace_id="workspace_1",
            )

        row = projection["candidate_projection_rows"][0]
        self.assertEqual(row["bucket"], "learn")
        self.assertEqual(row["status"], "approved")
        self.assertEqual(row["carryover_summary"]["record_count"], 3)
        self.assertEqual(row["candidate_state_provenance"], "canonical_persisted_candidate_state")

    def test_discovery_workbench_prefers_projection_summaries_when_available(self):
        projection = {
            "target_definition": {"target_name": "pIC50", "target_kind": "regression"},
            "measurement_summary": {"rows_with_values": 3, "rows_with_labels": 0},
            "predictive_summary": {"average_uncertainty": 0.22, "baseline_fallback_used": True},
            "governance_summary": {"approved": 1, "pending_review": 1},
            "ranking_diagnostics": {"out_of_domain_rate": 0.3, "diagnostic_source": "projection_synthesized"},
            "recommendation_summary": "Start with cand_1 as the strongest near-term testing candidate for pIC50.",
            "ranking_policy": {"primary_score_label": "Priority score"},
            "run_contract": {"modeling_mode": "regression", "scoring_mode": "balanced"},
            "comparison_anchors": {"target_name": "pIC50", "target_kind": "regression"},
            "run_provenance": {"bridge_state_active": True, "bridge_state_summary": "Baseline fallback still visible."},
            "trust_context": {"bridge_state_summary": "Baseline fallback still visible."},
            "metric_interpretation": [{"label": "Priority score", "meaning": "Higher is better."}],
            "diagnostics": {"canonical_projection_used": True, "legacy_merge_fields": ["run_contract"]},
            "candidate_projection_rows": [
                {
                    "candidate_id": "cand_1",
                    "canonical_smiles": "CCO",
                    "bucket": "learn",
                    "risk": "high",
                    "status": "approved",
                    "rationale": {"trust_label": "High caution"},
                    "carryover_summary": {"record_count": 2},
                    "candidate_state_provenance": "canonical_persisted_candidate_state",
                    "candidate_field_provenance": {"predictive_source": "model_output_records"},
                    "candidate_trust_summary": {"trust_label": "High caution", "trust_summary": "Stored canonical caution summary."},
                }
            ],
        }
        decision_output = {
            "artifact_state": "ok",
            "source_updated_at": "2026-04-17T10:00:00+00:00",
            "top_experiments": [
                {
                    "candidate_id": "cand_1",
                    "bucket": "exploit",
                    "risk": "low",
                    "status": "approved",
                    "confidence": 0.8,
                    "uncertainty": 0.2,
                    "novelty": 0.3,
                    "experiment_value": 0.7,
                    "priority_score": 0.8,
                    "smiles": "CCO",
                    "canonical_smiles": "CCO",
                    "explanation": ["Top candidate"],
                }
            ],
        }

        workbench = build_discovery_workbench(
            decision_output=decision_output,
            analysis_report={"top_level_recommendation_summary": "Legacy narrative"},
            review_queue={"summary": {"counts": {"approved": 1, "suggested": 1}}},
            session_id="session_projection",
            evaluation_summary=None,
            system_version="test",
            scientific_session_projection=projection,
        )

        self.assertEqual(workbench["recommendation_summary"], projection["recommendation_summary"])
        self.assertEqual(workbench["measurement_summary"]["rows_with_values"], 3)
        self.assertTrue(workbench["projection_diagnostics"]["canonical_projection_used"])
        self.assertEqual(workbench["governance_summary"]["approved"], 1)
        self.assertEqual(workbench["ranking_diagnostics"]["diagnostic_source"], "projection_synthesized")
        self.assertEqual(workbench["candidates"][0]["carryover_summary"]["record_count"], 2)
        self.assertEqual(workbench["candidates"][0]["bucket"], "learn")
        self.assertEqual(workbench["candidates"][0]["candidate_state_provenance"], "canonical_persisted_candidate_state")
        self.assertEqual(workbench["candidates"][0]["trust_summary"], "Stored canonical caution summary.")

    def test_claim_materialization_is_conservative_and_grounded_in_candidate_and_run_state(self):
        claims = materialize_session_claims(
            session_id="session_claims",
            workspace_id="workspace_1",
            created_by_user_id="user_1",
            run_metadata={
                "trust_summary": {
                    "bridge_state_summary": "Bridge-state fallback remains active for this run.",
                    "baseline_fallback_visible": True,
                },
                "comparison_anchors": {"comparison_ready": False},
            },
            candidate_states=[
                {
                    "candidate_id": "cand_1",
                    "canonical_smiles": "CCO",
                    "rank": 1,
                    "identity_context": {"target_name": "pIC50"},
                    "recommendation_summary": {"bucket": "exploit", "risk": "low"},
                    "trust_summary": {"trust_label": "Stronger trust"},
                },
                {
                    "candidate_id": "cand_2",
                    "canonical_smiles": "CCN",
                    "rank": 2,
                    "identity_context": {"target_name": "pIC50"},
                    "recommendation_summary": {"bucket": "learn", "risk": "high"},
                    "trust_summary": {"trust_label": "High caution"},
                },
            ],
        )

        self.assertEqual(len(claims), 3)
        self.assertEqual(claims[0]["claim_type"], "candidate_experiment_priority")
        self.assertEqual(claims[-1]["claim_type"], "run_interpretation_caution")

    def test_experiment_result_triggers_deterministic_belief_update(self):
        claim = {
            "claim_id": "claim_1",
            "session_id": "session_1",
            "workspace_id": "workspace_1",
            "candidate_id": "cand_1",
            "canonical_smiles": "CCO",
        }
        request_store: dict[str, dict] = {}
        belief_state_store = {
            "belief_state_id": "belief_1",
            "claim_id": "claim_1",
            "session_id": "session_1",
            "workspace_id": "workspace_1",
            "current_state": "unresolved",
            "current_strength": "tentative",
            "support_basis_summary": "No experimental result has updated this claim yet.",
            "latest_update_id": "",
            "status": "active",
            "provenance_markers": {},
        }

        with patch("system.services.experiment_service.scientific_state_repository.record_experiment_request") as record_request, patch(
            "system.services.experiment_service.scientific_state_repository.get_claim",
            return_value=claim,
        ), patch(
            "system.services.experiment_service.scientific_state_repository.list_claim_evidence_links",
            return_value=[
                {
                    "linked_object_type": "recommendation",
                    "relation_type": "derived_from",
                    "summary": "Derived from ranked recommendation cand_1.",
                },
                {
                    "linked_object_type": "evidence",
                    "relation_type": "context_only",
                    "summary": "Observed assay row for cand_1 is attached as context.",
                },
            ],
        ), patch(
            "system.services.experiment_service.scientific_state_repository.record_experiment_result"
        ) as record_result, patch(
            "system.services.experiment_service.scientific_state_repository.update_experiment_request_status",
            side_effect=lambda request_id, status: {**request_store.get(request_id, {}), "request_id": request_id, "status": status},
        ), patch(
            "system.services.belief_state_service.scientific_state_repository.get_belief_state",
            return_value=belief_state_store,
        ), patch(
            "system.services.belief_state_service.scientific_state_repository.upsert_belief_state",
            side_effect=lambda payload: {**payload},
        ), patch(
            "system.services.belief_state_service.scientific_state_repository.record_belief_update",
            side_effect=lambda payload: {**payload},
        ):
            record_request.side_effect = lambda payload: request_store.setdefault(payload["request_id"], payload)
            record_result.side_effect = lambda payload: payload
            request = create_experiment_request(
                claim=claim,
                requested_measurement="pIC50",
                rationale="Validate the leading candidate claim.",
                created_by_user_id="user_1",
            )
            result, belief_update, belief_state = record_experiment_result(
                request=request,
                outcome="supportive",
                observed_value=7.1,
                result_summary={"note": "Supportive assay result."},
                created_by_user_id="user_1",
            )

        self.assertEqual(request["tested_claim_id"], "claim_1")
        self.assertEqual(request["experiment_intent"], "claim_test")
        self.assertIn("Reduce uncertainty around the linked claim", request["epistemic_goal_summary"])
        self.assertIn("Claim basis", request["existing_context_summary"])
        self.assertIn("would strengthen", request["strengthening_outcome_description"])
        self.assertIn("would weaken or challenge", request["weakening_outcome_description"])
        self.assertEqual(len(request["linked_claim_evidence_snapshot"]), 2)
        self.assertEqual(result["outcome"], "supportive")
        self.assertEqual(belief_update["deterministic_rule"], "supportive_result_strengthens_claim")
        self.assertEqual(belief_state["current_state"], "supported")

    def test_belief_read_model_exposes_absence_and_candidate_linkage_explicitly(self):
        with patch(
            "system.services.belief_read_service.scientific_state_repository.list_claims",
            return_value=[],
        ), patch(
            "system.services.belief_read_service.scientific_state_repository.list_candidate_states",
            return_value=[],
        ):
            model = build_session_belief_read_model(session_id="session_empty", workspace_id="workspace_1")

        self.assertFalse(model["session_summary"]["has_belief_layer"])
        self.assertEqual(model["session_summary"]["absence_reason"], "no_claims_materialized")
        self.assertEqual(model["diagnostics"]["belief_read_source"], "absent")

    def test_belief_read_model_shapes_candidate_and_run_claim_summaries(self):
        claims = [
            {
                "claim_id": "claim_candidate",
                "candidate_id": "cand_1",
                "canonical_smiles": "CCO",
                "claim_scope": "candidate",
                "claim_type": "candidate_experiment_priority",
                "claim_text": "Candidate cand_1 is a priority experimental candidate.",
                "status": "active",
            },
            {
                "claim_id": "claim_run",
                "candidate_id": "",
                "canonical_smiles": "",
                "claim_scope": "run",
                "claim_type": "run_interpretation_caution",
                "claim_text": "Bridge-state fallback remains active.",
                "status": "active",
            },
        ]
        candidate_states = [{"candidate_id": "cand_1", "canonical_smiles": "CCO"}]

        def list_requests(*, claim_id=None, session_id=None):
            if claim_id == "claim_candidate":
                return [{"request_id": "req_1", "claim_id": "claim_candidate"}]
            return []

        def list_results(*, request_id=None, claim_id=None):
            if request_id == "req_1":
                return [{"result_id": "res_1", "request_id": "req_1"}]
            return []

        def get_belief_state(*, claim_id):
            if claim_id == "claim_candidate":
                return {"current_state": "supported", "current_strength": "strengthened", "support_basis_summary": "Supportive experiment result recorded."}
            raise FileNotFoundError("missing")

        with patch(
            "system.services.belief_read_service.scientific_state_repository.list_claims",
            return_value=claims,
        ), patch(
            "system.services.belief_read_service.scientific_state_repository.list_candidate_states",
            return_value=candidate_states,
        ), patch(
            "system.services.belief_read_service.scientific_state_repository.list_experiment_requests",
            side_effect=list_requests,
        ), patch(
            "system.services.belief_read_service.scientific_state_repository.list_experiment_results",
            side_effect=list_results,
        ), patch(
            "system.services.belief_read_service.scientific_state_repository.get_belief_state",
            side_effect=get_belief_state,
        ):
            model = build_session_belief_read_model(session_id="session_1", workspace_id="workspace_1")

        self.assertEqual(model["session_summary"]["claim_count"], 2)
        self.assertEqual(model["session_summary"]["belief_state_count"], 1)
        self.assertEqual(model["candidate_items"][0]["claim_count"], 1)
        self.assertTrue(model["candidate_items"][0]["has_experiment_request"])
        self.assertTrue(model["candidate_items"][0]["has_experiment_result"])
        self.assertEqual(model["run_items"][0]["claim_type"], "run_interpretation_caution")

    def test_projection_exposes_belief_layer_summary_without_inflating_absent_states(self):
        canonical_state = {
            "session_id": "session_belief",
            "target_definition": {"target_name": "pIC50", "target_kind": "regression"},
            "evidence_records": [],
            "model_outputs": [],
            "recommendations": [],
            "carryover_records": [],
            "candidate_states": [],
            "claims": [],
            "run_metadata": {},
        }
        belief_read_model = {
            "session_summary": {
                "claim_count": 0,
                "active_claim_count": 0,
                "claim_categories": [],
                "belief_state_count": 0,
                "supported_claim_count": 0,
                "challenged_claim_count": 0,
                "unresolved_claim_count": 0,
                "experiment_request_count": 0,
                "experiment_result_count": 0,
                "has_belief_layer": False,
                "absence_reason": "no_claims_materialized",
            },
            "candidate_items": [],
            "run_items": [],
            "claim_items": [],
            "diagnostics": {"belief_read_source": "absent"},
            }

        with patch(
            "system.services.scientific_session_projection_service.load_canonical_session_scientific_state",
            return_value=canonical_state,
        ), patch(
            "system.services.scientific_session_projection_service.load_analysis_report_payload",
            return_value={},
        ), patch(
            "system.services.scientific_session_projection_service.load_decision_artifact_payload",
            return_value={"artifact_state": "ok"},
        ), patch(
            "system.services.scientific_session_projection_service.build_session_belief_read_model",
            return_value=belief_read_model,
        ):
            projection = build_scientific_session_projection(
                session_record={"session_id": "session_belief", "workspace_id": "workspace_1"},
                workspace_id="workspace_1",
            )

        self.assertFalse(projection["belief_layer_summary"]["has_belief_layer"])
        self.assertEqual(projection["belief_read_model"]["diagnostics"]["belief_read_source"], "absent")

    def test_claim_detail_read_model_keeps_absence_and_linkage_explicit(self):
        claim = {
            "claim_id": "claim_candidate",
            "session_id": "session_1",
            "workspace_id": "workspace_1",
            "candidate_id": "cand_1",
            "canonical_smiles": "CCO",
            "claim_scope": "candidate",
            "claim_type": "candidate_experiment_priority",
            "claim_text": "Candidate cand_1 is a priority experiment candidate.",
            "claim_summary": {"priority_basis": "top_ranked_recommendation"},
            "source_basis": "recommended",
            "support_links": {"candidate_state": True, "recommendation_record": True},
            "status": "active",
            "provenance_markers": {"claim_source": "canonical_candidate_state"},
            "created_at": "2026-04-17T10:00:00+00:00",
            "updated_at": "2026-04-17T10:00:00+00:00",
        }
        candidate_states = [
            {
                "candidate_id": "cand_1",
                "canonical_smiles": "CCO",
                "rank": 1,
                "predictive_summary": {"confidence": 0.82, "uncertainty": 0.18},
                "recommendation_summary": {"bucket": "exploit", "risk": "low", "status": "approved"},
                "governance_summary": {"status": "approved"},
                "carryover_summary": {"record_count": 0, "continuity_source": "canonical_carryover"},
                "trust_summary": {"trust_label": "Stronger trust", "trust_summary": "Canonical support looks strong."},
            }
        ]
        requests = [
            {
                "request_id": "req_1",
                "status": "requested",
                "objective": "Validate potency",
                "rationale": "Top ranked candidate",
                "requested_measurement": "pIC50",
                "created_at": "2026-04-17T11:00:00+00:00",
                "updated_at": "2026-04-17T11:00:00+00:00",
            }
        ]

        with patch(
            "system.services.claim_read_service.scientific_state_repository.get_claim",
            return_value=claim,
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_candidate_states",
            return_value=candidate_states,
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.get_run_metadata",
            side_effect=FileNotFoundError("missing"),
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_experiment_requests",
            return_value=requests,
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_experiment_results",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_belief_updates",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.get_belief_state",
            side_effect=FileNotFoundError("missing"),
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_claim_evidence_links",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_evidence_records",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_model_outputs",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_recommendations",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_contradictions",
            return_value=[],
        ):
            detail = build_claim_detail_read_model(claim_id="claim_candidate")

        self.assertTrue(detail["available"])
        self.assertEqual(detail["claim"]["claim_scope"], "candidate")
        self.assertTrue(detail["attachment_context"]["candidate_context"]["available"])
        self.assertFalse(detail["attachment_context"]["run_context"]["available"])
        self.assertTrue(detail["experiment_detail"]["has_requests"])
        self.assertFalse(detail["experiment_detail"]["has_results"])
        self.assertEqual(detail["belief_update_summary"]["absence_reason"], "no_belief_updates")
        self.assertEqual(detail["current_belief_state"]["absence_reason"], "belief_state_absent")

    def test_claim_detail_read_model_shapes_run_linked_belief_history(self):
        claim = {
            "claim_id": "claim_run",
            "session_id": "session_run",
            "workspace_id": "workspace_1",
            "candidate_id": "",
            "canonical_smiles": "",
            "claim_scope": "run",
            "claim_type": "run_interpretation_caution",
            "claim_text": "Bridge-state fallback remains active.",
            "claim_summary": {"reason": "baseline_fallback_visible"},
            "source_basis": "derived",
            "support_links": {"run_metadata": True},
            "status": "active",
            "provenance_markers": {"claim_source": "canonical_run_metadata"},
            "created_at": "2026-04-17T10:00:00+00:00",
            "updated_at": "2026-04-17T10:00:00+00:00",
        }
        run_metadata = {
            "session_id": "session_run",
            "modeling_mode": "regression",
            "scoring_mode": "balanced",
            "comparison_anchors": {"comparison_ready": True, "target_name": "pIC50", "target_kind": "regression"},
            "trust_summary": {"bridge_state_summary": "Baseline fallback visible.", "baseline_fallback_visible": True},
        }
        updates = [
            {
                "update_id": "upd_1",
                "result_id": "res_1",
                "update_reason": "Supportive result recorded",
                "deterministic_rule": "supportive_result_strengthens_claim",
                "pre_belief_state": {"current_state": "tentative"},
                "post_belief_state": {"current_state": "supported"},
                "created_at": "2026-04-17T12:00:00+00:00",
                "updated_at": "2026-04-17T12:00:00+00:00",
            }
        ]
        belief_state = {
            "current_state": "supported",
            "current_strength": "strengthened",
            "support_basis_summary": "Supportive result observed.",
            "latest_update_id": "upd_1",
            "status": "active",
            "updated_at": "2026-04-17T12:00:00+00:00",
        }

        with patch(
            "system.services.claim_read_service.scientific_state_repository.get_claim",
            return_value=claim,
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_candidate_states",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.get_run_metadata",
            return_value=run_metadata,
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_experiment_requests",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_experiment_results",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_belief_updates",
            return_value=updates,
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.get_belief_state",
            return_value=belief_state,
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_claim_evidence_links",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_evidence_records",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_model_outputs",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_recommendations",
            return_value=[],
        ), patch(
            "system.services.claim_read_service.scientific_state_repository.list_contradictions",
            return_value=[],
        ):
            detail = build_claim_detail_read_model(claim_id="claim_run")

        self.assertEqual(detail["claim"]["claim_scope"], "run")
        self.assertTrue(detail["attachment_context"]["run_context"]["available"])
        self.assertEqual(detail["belief_update_summary"]["items"][0]["deterministic_rule"], "supportive_result_strengthens_claim")
        self.assertEqual(detail["current_belief_state"]["current_state"], "supported")

    def test_projection_and_workbench_expose_claim_detail_surface_without_inflation(self):
        canonical_state = {
            "session_id": "session_claim_detail",
            "target_definition": {"target_name": "pIC50", "target_kind": "regression"},
            "evidence_records": [
                {
                    "record_id": 1,
                    "candidate_id": "cand_1",
                    "canonical_smiles": "CCO",
                    "evidence_type": "observed_measurement",
                    "assay": "humid packaging barrier assay",
                    "observed_value": 0.14,
                    "payload": {
                        "material_family": "compostable polyester film",
                        "application": "food packaging film",
                        "properties": ["moisture barrier", "biodegradable"],
                        "environment": "humid",
                        "lifecycle": "months",
                    },
                }
            ],
            "model_outputs": [
                {
                    "record_id": 2,
                    "candidate_id": "cand_1",
                    "canonical_smiles": "CCO",
                    "predicted_value": 0.79,
                    "confidence": 0.82,
                    "payload": {
                        "material_family": "compostable polyester film",
                        "application": "humid packaging film",
                    },
                }
            ],
            "recommendations": [
                {
                    "record_id": 3,
                    "candidate_id": "cand_1",
                    "canonical_smiles": "CCO",
                    "rank": 1,
                    "bucket": "learn",
                    "rationale_summary": "Packaging film direction with moisture barrier context.",
                    "payload": {
                        "material_family": "compostable polyester film",
                        "application": "food packaging film",
                    },
                }
            ],
            "carryover_records": [],
            "candidate_states": [],
            "claims": [{"claim_id": "claim_candidate"}],
            "material_goal_specification": {
                "goal_id": "goal_1",
                "raw_user_goal": "Need a biodegradable packaging film with moisture barrier for humid use.",
                "domain_scope": "polymer_material",
                "requirement_status": "insufficient_needs_clarification",
                "structured_requirements": {
                    "target_material_function": ["packaging", "film"],
                    "desired_properties": ["biodegradable", "barrier", "moisture"],
                    "operating_environment": ["humid"],
                },
                "missing_critical_requirements": ["lifecycle_window"],
                "clarification_questions": ["What stability or lifetime window is required before degradation becomes acceptable?"],
                "scientific_target_summary": "Material goal remains insufficiently specified for scientific retrieval because critical constraints are still missing.",
            },
            "run_metadata": {},
        }
        belief_read_model = {
            "session_summary": {"claim_count": 1, "has_belief_layer": True, "absence_reason": ""},
            "candidate_items": [{"candidate_id": "cand_1", "canonical_smiles": "CCO", "claim_count": 1}],
            "run_items": [],
            "claim_items": [{"claim_id": "claim_candidate"}],
            "experiment_lifecycle_summary": {"experiment_request_count": 1, "pending_count": 1},
            "diagnostics": {"belief_read_source": "canonical_belief_objects"},
        }
        experiment_lifecycle_model = {
            "session_summary": {"experiment_request_count": 1, "pending_count": 1, "has_experiments": True, "provenance": "canonical_experiment_lifecycle"},
            "claim_items": [{"claim_id": "claim_candidate", "unresolved_state": "pending_result"}],
            "candidate_items": [{"candidate_id": "cand_1", "pending_request_count": 1}],
            "run_items": [{"session_id": "session_claim_detail", "absence_reason": "run_linked_experiment_context_absent"}],
            "experiment_items": [{"request_id": "req_1", "status": "requested", "unresolved_state": "no_result_recorded"}],
            "diagnostics": {"experiment_summary_present": True},
        }
        claim_detail_items = [
            {
                "available": True,
                "claim_id": "claim_candidate",
                "claim": {"claim_scope": "candidate", "claim_type": "candidate_experiment_priority"},
                "attachment_context": {
                    "candidate_context": {"available": True, "candidate_id": "cand_1", "canonical_smiles": "CCO"},
                    "run_context": {"available": False},
                },
                "experiment_detail": {"has_requests": True, "has_results": False},
                "belief_update_summary": {"has_updates": False},
                "current_belief_state": {"available": False},
                "diagnostics": {"detail_source": "canonical_epistemic_objects"},
            }
        ]

        with patch(
            "system.services.scientific_session_projection_service.load_canonical_session_scientific_state",
            return_value=canonical_state,
        ), patch(
            "system.services.scientific_session_projection_service.load_analysis_report_payload",
            return_value={},
        ), patch(
            "system.services.scientific_session_projection_service.load_decision_artifact_payload",
            return_value={"artifact_state": "ok"},
        ), patch(
            "system.services.scientific_session_projection_service.build_session_belief_read_model",
            return_value=belief_read_model,
        ), patch(
            "system.services.scientific_session_projection_service.build_session_experiment_lifecycle_read_model",
            return_value=experiment_lifecycle_model,
        ), patch(
            "system.services.scientific_session_projection_service.build_session_claim_detail_items",
            return_value=claim_detail_items,
        ):
            projection = build_scientific_session_projection(
                session_record={"session_id": "session_claim_detail", "workspace_id": "workspace_1"},
                workspace_id="workspace_1",
            )

        self.assertTrue(projection["claim_detail_summary"]["has_claim_detail_surface"])
        self.assertEqual(projection["diagnostics"]["claim_detail_source"], "canonical_epistemic_objects")
        self.assertEqual(projection["experiment_lifecycle_summary"]["pending_count"], 1)
        self.assertTrue(projection["diagnostics"]["experiment_lifecycle_present"])
        self.assertEqual(projection["session_epistemic_summary"]["status"], "pending_experiments")
        self.assertTrue(projection["epistemic_entry_points"]["claim_detail_available"])
        self.assertTrue(projection["session_epistemic_detail_reveal"]["available"])
        self.assertTrue(projection["focused_claim_inspection"]["available"])
        self.assertTrue(projection["focused_experiment_inspection"]["available"])
        self.assertTrue(projection["material_goal_specification"]["available"])
        self.assertEqual(projection["material_goal_specification"]["requirement_status"], "insufficient_needs_clarification")
        self.assertTrue(projection["material_goal_retrieval"]["available"])
        self.assertEqual(projection["material_goal_retrieval"]["retrieval_status"], "blocked_goal_insufficient")

        workbench = build_discovery_workbench(
            decision_output={
                "artifact_state": "ok",
                "source_updated_at": "2026-04-17T10:00:00+00:00",
                "top_experiments": [
                    {
                        "candidate_id": "cand_1",
                        "bucket": "exploit",
                        "risk": "low",
                        "status": "approved",
                        "confidence": 0.8,
                        "uncertainty": 0.2,
                        "novelty": 0.3,
                        "experiment_value": 0.7,
                        "priority_score": 0.8,
                        "smiles": "CCO",
                        "canonical_smiles": "CCO",
                        "explanation": ["Top candidate"],
                    }
                ],
            },
            analysis_report={},
            review_queue={},
            session_id="session_claim_detail",
            evaluation_summary=None,
            system_version="test",
            scientific_session_projection=projection,
        )

        self.assertEqual(workbench["claim_detail_summary"]["claim_detail_count"], 1)
        self.assertEqual(workbench["candidates"][0]["claim_detail_items"][0]["claim_id"], "claim_candidate")
        self.assertEqual(workbench["experiment_lifecycle_summary"]["experiment_request_count"], 1)
        self.assertEqual(workbench["material_goal_specification"]["requirement_status"], "insufficient_needs_clarification")
        self.assertEqual(workbench["material_goal_retrieval"]["retrieval_status"], "blocked_goal_insufficient")
        self.assertEqual(workbench["session_epistemic_summary"]["pending_experiment_count"], 1)
        self.assertEqual(workbench["candidates"][0]["candidate_epistemic_context"]["status"], "pending_experiment")

    def test_workbench_surfaces_epistemic_attention_ahead_of_policy_only_ordering(self):
        projection = {
            "target_definition": {"target_name": "pIC50", "target_kind": "regression"},
            "measurement_summary": {"rows_with_values": 2, "rows_with_labels": 0},
            "predictive_summary": {},
            "governance_summary": {},
            "ranking_diagnostics": {},
            "recommendation_summary": "Start with the most decision-ready candidate, but keep unresolved claim pressure visible.",
            "ranking_policy": {"primary_score_label": "Policy priority score", "primary_score": "priority_score"},
            "run_contract": {"modeling_mode": "regression", "scoring_mode": "balanced"},
            "comparison_anchors": {"target_name": "pIC50", "target_kind": "regression"},
            "run_provenance": {},
            "trust_context": {},
            "metric_interpretation": [],
            "diagnostics": {"canonical_projection_used": True},
            "candidate_projection_rows": [
                {
                    "candidate_id": "cand_a",
                    "canonical_smiles": "CCO",
                    "bucket": "learn",
                    "risk": "medium",
                    "status": "suggested",
                    "priority_score": 0.60,
                    "experiment_value": 0.50,
                },
                {
                    "candidate_id": "cand_b",
                    "canonical_smiles": "CCN",
                    "bucket": "exploit",
                    "risk": "low",
                    "status": "suggested",
                    "priority_score": 0.90,
                    "experiment_value": 0.82,
                },
            ],
            "belief_layer_summary": {},
            "belief_read_model": {},
            "experiment_lifecycle_summary": {"experiment_request_count": 1, "pending_count": 1},
            "experiment_lifecycle_model": {
                "experiment_items": [
                    {
                        "request_id": "req_a",
                        "scope_context": {"candidate_id": "cand_a", "canonical_smiles": "CCO", "claim_scope": "candidate"},
                        "epistemic_priority": {
                            "epistemic_priority_score": 0.95,
                            "epistemic_priority_band": "high",
                            "summary_rationale": "Prioritized because the claim remains unresolved in the current session.",
                        },
                        "unresolved_state": "no_result_recorded",
                    }
                ]
            },
            "claim_detail_summary": {},
            "claim_detail_items": [
                {
                    "claim_id": "claim_a",
                    "claim": {"claim_scope": "candidate", "claim_type": "candidate_experiment_priority"},
                    "attachment_context": {"candidate_context": {"available": True, "candidate_id": "cand_a", "canonical_smiles": "CCO"}},
                    "experiment_detail": {"has_requests": True, "has_results": False},
                    "belief_update_summary": {"has_updates": True},
                    "current_belief_state": {
                        "available": True,
                        "current_state": "unresolved",
                        "current_strength": "mixed",
                        "contradiction_pressure": "moderate",
                        "support_balance_summary": "1 supporting line(s), 1 weakening line(s), 0 context-only line(s), 0 derived line(s); current attached structure is mixed.",
                        "latest_revision_rationale": "Belief remains unresolved because contradiction pressure is still active.",
                    },
                    "diagnostics": {"detail_source": "canonical_epistemic_objects"},
                }
            ],
            "session_epistemic_summary": {},
            "epistemic_entry_points": {},
            "session_epistemic_detail_reveal": {},
            "focused_claim_inspection": {},
            "focused_experiment_inspection": {},
        }

        workbench = build_discovery_workbench(
            decision_output={
                "artifact_state": "ok",
                "source_updated_at": "2026-04-20T09:00:00+00:00",
                "top_experiments": [
                    {
                        "candidate_id": "cand_b",
                        "bucket": "exploit",
                        "risk": "low",
                        "status": "suggested",
                        "confidence": 0.91,
                        "uncertainty": 0.12,
                        "novelty": 0.22,
                        "experiment_value": 0.82,
                        "priority_score": 0.90,
                        "smiles": "CCN",
                        "canonical_smiles": "CCN",
                        "explanation": ["Higher policy-ranked candidate."],
                    },
                    {
                        "candidate_id": "cand_a",
                        "bucket": "learn",
                        "risk": "medium",
                        "status": "suggested",
                        "confidence": 0.62,
                        "uncertainty": 0.48,
                        "novelty": 0.41,
                        "experiment_value": 0.50,
                        "priority_score": 0.60,
                        "smiles": "CCO",
                        "canonical_smiles": "CCO",
                        "explanation": ["Lower policy-ranked candidate with unresolved claim pressure."],
                    },
                ],
            },
            analysis_report={},
            review_queue={},
            session_id="session_attention",
            evaluation_summary=None,
            system_version="test",
            scientific_session_projection=projection,
        )

        self.assertEqual(workbench["candidates"][0]["candidate_id"], "cand_a")
        self.assertTrue(workbench["candidates"][0]["surfaced_attention_active"])
        self.assertEqual(workbench["candidates"][0]["surfaced_attention_bucket"], "epistemic_attention")
        self.assertGreater(workbench["candidates"][0]["belief_attention_signal"], 0.7)
        self.assertIn("contradiction pressure", workbench["candidates"][0]["belief_informed_attention_reason"].lower())
        self.assertEqual(workbench["candidates"][0]["priority_score"], 0.6)
        self.assertEqual(workbench["candidates"][1]["candidate_id"], "cand_b")
        self.assertEqual(workbench["surfaced_attention_summary"]["belief_feedback_count"], 1)
        self.assertEqual(workbench["surfaced_attention_summary"]["default_sort"], "surfaced_order_score")
        self.assertEqual(workbench["decision_overview"]["primary_candidate"]["candidate_id"], "cand_a")
        self.assertTrue(workbench["session_epistemic_detail_reveal"]["available"])
        self.assertTrue(workbench["candidates"][0]["focused_claim_inspection"]["available"])
        self.assertTrue(workbench["candidates"][0]["focused_experiment_inspection"]["available"])

    def test_experiment_lifecycle_read_model_exposes_pending_completed_and_unresolved_states(self):
        claims = [
            {
                "claim_id": "claim_candidate_pending",
                "claim_scope": "candidate",
                "claim_type": "candidate_experiment_priority",
                "candidate_id": "cand_1",
                "canonical_smiles": "CCO",
                "session_id": "session_exp",
                "workspace_id": "workspace_1",
            },
            {
                "claim_id": "claim_candidate_no_request",
                "claim_scope": "candidate",
                "claim_type": "candidate_experiment_priority",
                "candidate_id": "cand_2",
                "canonical_smiles": "CCN",
                "session_id": "session_exp",
                "workspace_id": "workspace_1",
            },
            {
                "claim_id": "claim_run_done",
                "claim_scope": "run",
                "claim_type": "run_interpretation_caution",
                "candidate_id": "",
                "canonical_smiles": "",
                "session_id": "session_exp",
                "workspace_id": "workspace_1",
            },
        ]
        requests = [
                {
                    "request_id": "req_pending",
                    "claim_id": "claim_candidate_pending",
                "candidate_id": "cand_1",
                "canonical_smiles": "CCO",
                "session_id": "session_exp",
                "workspace_id": "workspace_1",
                    "objective": "Test candidate priority",
                    "rationale": "Pending confirmation",
                    "requested_measurement": "pIC50",
                    "expected_learning_value": "Reduce uncertainty around a mixed and contradiction-exposed claim.",
                    "linked_claim_evidence_snapshot": [
                        {"linked_object_type": "recommendation", "relation_type": "derived_from", "summary": "Derived from recommendation context."}
                    ],
                    "status": "requested",
                    "provenance_markers": {"request_source": "test"},
                },
            {
                "request_id": "req_done",
                "claim_id": "claim_run_done",
                "candidate_id": "",
                "canonical_smiles": "",
                "session_id": "session_exp",
                "workspace_id": "workspace_1",
                "objective": "Check run-level caution",
                "rationale": "Bridge-state check",
                "requested_measurement": "pIC50",
                "status": "completed",
                "provenance_markers": {"request_source": "test"},
            },
        ]
        results_by_request = {
            "req_pending": [],
            "req_done": [
                {
                    "result_id": "res_done",
                    "request_id": "req_done",
                    "outcome": "supportive",
                    "status": "recorded",
                    "result_summary": {"summary": "Supportive assay result."},
                    "provenance_markers": {"result_source": "test"},
                    "created_at": "2026-04-17T12:00:00+00:00",
                }
            ],
        }
        updates_by_result = {
            "res_done": [
                {
                    "update_id": "upd_done",
                    "result_id": "res_done",
                    "update_reason": "Supportive result recorded",
                    "provenance_markers": {"update_source": "test"},
                    "created_at": "2026-04-17T12:05:00+00:00",
                }
            ]
        }

        def list_results(*, request_id=None, claim_id=None):
            if request_id is not None:
                return results_by_request.get(request_id, [])
            if claim_id == "claim_run_done":
                return results_by_request["req_done"]
            return []

        def list_updates(*, claim_id=None, result_id=None):
            if result_id is not None:
                return updates_by_result.get(result_id, [])
            return []

        def get_belief_state(*, claim_id):
            if claim_id == "claim_run_done":
                return {
                    "current_state": "supported",
                    "current_strength": "strengthened",
                    "support_basis_summary": "Supportive result observed.",
                    "contradiction_pressure": "low",
                    "support_balance_summary": "2 supporting line(s), 0 weakening line(s), 0 context-only line(s), 0 derived line(s); current attached structure leans supportive.",
                    "latest_revision_rationale": "A supportive result increased support because contradiction pressure is currently low.",
                }
            if claim_id == "claim_candidate_pending":
                return {
                    "current_state": "unresolved",
                    "current_strength": "mixed",
                    "support_basis_summary": "Belief remains unresolved because contradiction pressure is still active.",
                    "contradiction_pressure": "moderate",
                    "support_balance_summary": "1 supporting line(s), 1 weakening line(s), 0 context-only line(s), 1 derived line(s); current attached structure is mixed.",
                    "latest_revision_rationale": "Belief remains unresolved because contradiction pressure is still active.",
                }
            raise FileNotFoundError("missing")

        with patch(
            "system.services.experiment_read_service.scientific_state_repository.list_claims",
            return_value=claims,
        ), patch(
            "system.services.experiment_read_service.scientific_state_repository.list_experiment_requests",
            return_value=requests,
        ), patch(
            "system.services.experiment_read_service.scientific_state_repository.list_claim_evidence_links",
            return_value=[
                {
                    "claim_id": "claim_candidate_pending",
                    "relation_type": "derived_from",
                    "linked_object_type": "recommendation",
                },
                {
                    "claim_id": "claim_run_done",
                    "relation_type": "supports",
                    "linked_object_type": "evidence",
                },
                {
                    "claim_id": "claim_run_done",
                    "relation_type": "supports",
                    "linked_object_type": "model_output",
                },
            ],
        ), patch(
            "system.services.experiment_read_service.scientific_state_repository.list_experiment_results",
            side_effect=list_results,
        ), patch(
            "system.services.experiment_read_service.scientific_state_repository.list_belief_updates",
            side_effect=list_updates,
        ), patch(
            "system.services.experiment_read_service.scientific_state_repository.get_belief_state",
            side_effect=get_belief_state,
        ), patch(
            "system.services.experiment_read_service.scientific_state_repository.list_contradictions",
            return_value=[
                {
                    "contradiction_id": "contr_pending",
                    "claim_id": "claim_candidate_pending",
                    "contradiction_type": "support_structure_conflict",
                    "status": "unresolved",
                    "summary": "The claim remains exposed to unresolved contradiction pressure.",
                }
            ],
        ):
            model = build_session_experiment_lifecycle_read_model(
                session_id="session_exp",
                workspace_id="workspace_1",
            )

        self.assertEqual(model["session_summary"]["experiment_request_count"], 2)
        self.assertEqual(model["session_summary"]["pending_count"], 1)
        self.assertEqual(model["session_summary"]["completed_count"], 1)
        self.assertEqual(model["session_summary"]["result_recorded_count"], 1)
        self.assertEqual(model["session_summary"]["belief_updated_count"], 1)
        self.assertEqual(model["claim_items"][0]["unresolved_state"], "pending_result")
        self.assertEqual(model["claim_items"][1]["unresolved_state"], "no_experiment_request")
        self.assertEqual(model["claim_items"][2]["unresolved_state"], "belief_updated")
        self.assertEqual(model["candidate_items"][0]["pending_request_count"], 1)
        self.assertEqual(model["candidate_items"][1]["claim_without_experiment_count"], 1)
        self.assertEqual(model["run_items"][0]["belief_updated_count"], 1)
        self.assertEqual(model["experiment_items"][0]["unresolved_state"], "no_result_recorded")
        self.assertEqual(model["experiment_items"][0]["active_contradiction_count"], 1)
        self.assertEqual(model["experiment_items"][1]["latest_belief_impact_summary"]["update_id"], "upd_done")
        self.assertEqual(model["experiment_items"][0]["epistemic_priority"]["epistemic_priority_band"], "high")
        self.assertGreater(model["experiment_items"][0]["epistemic_priority"]["belief_attention_signal"], 0.7)
        self.assertGreater(model["experiment_items"][0]["epistemic_priority"]["contradiction_attention_signal"], 0.7)
        self.assertGreater(
            model["experiment_items"][0]["epistemic_priority"]["epistemic_priority_score"],
            model["experiment_items"][1]["epistemic_priority"]["epistemic_priority_score"],
        )
        self.assertEqual(model["session_summary"]["high_epistemic_priority_count"], 1)
        self.assertIn("req_pending", model["diagnostics"]["requests_without_results"])

    def test_experiment_lifecycle_read_model_marks_absent_state_explicitly(self):
        with patch(
            "system.services.experiment_read_service.scientific_state_repository.list_claims",
            return_value=[],
        ), patch(
            "system.services.experiment_read_service.scientific_state_repository.list_experiment_requests",
            return_value=[],
        ), patch(
            "system.services.experiment_read_service.scientific_state_repository.list_claim_evidence_links",
            return_value=[],
        ), patch(
            "system.services.experiment_read_service.scientific_state_repository.list_contradictions",
            return_value=[],
        ):
            model = build_session_experiment_lifecycle_read_model(
                session_id="session_empty",
                workspace_id="workspace_1",
            )

        self.assertFalse(model["session_summary"]["has_experiments"])
        self.assertEqual(model["session_summary"]["absence_reason"], "no_experiments_in_session")
        self.assertEqual(model["run_items"][0]["absence_reason"], "run_linked_experiment_context_absent")
        self.assertTrue(model["diagnostics"]["experiment_summary_absent"])

    def test_session_epistemic_summary_keeps_absent_and_unresolved_states_explicit(self):
        summary = build_session_epistemic_summary(
            belief_layer_summary={"claim_count": 0, "active_claim_count": 0, "belief_state_count": 0, "has_belief_layer": False},
            experiment_lifecycle_summary={"experiment_request_count": 0, "pending_count": 0, "result_recorded_count": 0, "claim_linked_unresolved_count": 0, "belief_updated_count": 0, "has_experiments": False},
            claim_detail_summary={"has_claim_detail_surface": False, "claim_detail_count": 0},
        )

        self.assertFalse(summary["available"])
        self.assertEqual(summary["status"], "no_epistemic_layer")
        self.assertEqual(summary["absence_reason"], "no_claims_or_experiments_or_belief_state")

        unresolved = build_session_epistemic_summary(
            belief_layer_summary={"claim_count": 2, "active_claim_count": 2, "belief_state_count": 1, "has_belief_layer": True},
            experiment_lifecycle_summary={"experiment_request_count": 1, "pending_count": 0, "result_recorded_count": 1, "claim_linked_unresolved_count": 1, "belief_updated_count": 0, "has_experiments": True},
            claim_detail_summary={"has_claim_detail_surface": True, "claim_detail_count": 2},
        )

        self.assertTrue(unresolved["available"])
        self.assertEqual(unresolved["status"], "unresolved_epistemic_state")
        self.assertEqual(unresolved["unresolved_count"], 1)

    def test_candidate_epistemic_context_stays_compact_and_boundary_safe(self):
        pending = build_candidate_epistemic_context(
            claim_summary={
                "claim_count": 1,
                "has_experiment_request": True,
                "has_experiment_result": False,
                "experiment_lifecycle_summary": {"pending_request_count": 1, "belief_updated_count": 0, "unresolved_experiment_count": 1},
            },
            claim_detail_items=[{"claim_id": "claim_1"}],
        )

        self.assertTrue(pending["available"])
        self.assertEqual(pending["status"], "pending_experiment")
        self.assertNotIn("recommended", pending["summary_line"].lower())

        absent = build_candidate_epistemic_context(
            claim_summary={},
            claim_detail_items=[],
        )

        self.assertFalse(absent["available"])
        self.assertEqual(absent["status"], "no_epistemic_objects")
        self.assertEqual(absent["absence_reason"], "candidate_has_no_epistemic_layer_objects")

    def test_epistemic_detail_reveal_keeps_absence_and_unresolved_states_explicit(self):
        reveal = build_session_epistemic_detail_reveal(
            session_epistemic_summary={"available": True, "unresolved_count": 1},
            epistemic_entry_points={"claim_detail_available": True, "experiment_lifecycle_available": True},
            claim_detail_items=[
                {
                    "claim_id": "claim_1",
                    "claim": {"claim_type": "candidate_experiment_priority", "claim_text": "Candidate should be prioritized."},
                    "experiment_detail": {"pending_request_count": 1, "has_results": False},
                    "current_belief_state": {"current_state": "unresolved"},
                    "diagnostics": {"experiment_lifecycle_unresolved_state": "pending_result"},
                }
            ],
            experiment_lifecycle_model={
                "experiment_items": [
                    {
                        "request_id": "req_1",
                        "status": "requested",
                        "objective_summary": "Measure pIC50.",
                        "result_summary": {"status": "absent", "summary_text": ""},
                        "latest_belief_impact_summary": {"summary_text": ""},
                        "unresolved_state": "no_result_recorded",
                    }
                ]
            },
        )

        self.assertTrue(reveal["available"])
        self.assertEqual(reveal["claim_items"][0]["unresolved_state"], "pending_result")
        self.assertEqual(reveal["experiment_items"][0]["unresolved_state"], "no_result_recorded")

        absent = build_session_epistemic_detail_reveal(
            session_epistemic_summary={"available": False, "absence_reason": "no_claims_or_experiments_or_belief_state"},
            epistemic_entry_points={"claim_detail_available": False, "experiment_lifecycle_available": False, "absence_reason": "no_claim_detail_or_experiment_lifecycle"},
            claim_detail_items=[],
            experiment_lifecycle_model={},
        )

        self.assertFalse(absent["available"])
        self.assertEqual(absent["absence_reason"], "no_claims_or_experiments_or_belief_state")

    def test_candidate_detail_reveal_is_built_from_compact_and_canonical_inputs(self):
        detail = build_candidate_epistemic_detail_reveal(
            candidate_epistemic_context={
                "available": True,
                "status": "pending_experiment",
                "claim_count": 1,
                "has_pending_experiment": True,
                "has_recorded_result": False,
                "has_belief_update": False,
                "has_belief_state": True,
                "unresolved_count": 1,
            },
            claim_summary={"experiment_lifecycle_summary": {"unresolved_experiment_count": 1}},
            claim_detail_items=[
                {
                    "claim_id": "claim_1",
                    "claim": {"claim_type": "candidate_experiment_priority", "claim_text": "Prioritize this candidate."},
                    "experiment_detail": {"pending_request_count": 1, "has_results": False},
                    "current_belief_state": {"current_state": "unresolved"},
                    "diagnostics": {"experiment_lifecycle_unresolved_state": "pending_result"},
                }
            ],
        )

        self.assertTrue(detail["available"])
        self.assertEqual(detail["status"], "pending_experiment")
        self.assertEqual(detail["claim_items"][0]["unresolved_state"], "pending_result")

    def test_focused_claim_and_experiment_inspection_shape_one_object_at_a_time(self):
        claim_items = [
            {
                "claim_id": "claim_1",
                "claim": {
                    "claim_type": "candidate_experiment_priority",
                    "claim_status": "active",
                    "claim_scope": "candidate",
                    "claim_text": "Prioritize this candidate.",
                },
                "attachment_context": {
                    "support_basis_summary": "Supported by canonical candidate state.",
                    "contradiction_count": 1,
                    "active_contradiction_count": 1,
                    "contradictions": [
                        {
                            "contradiction_id": "contr_1",
                            "contradiction_type": "result_vs_claim",
                            "status": "active",
                            "summary": "A recorded result conflicts with the current claim.",
                            "object_summary": {"label": "experiment result", "context_bits": ["outcome contradictory"]},
                        }
                    ],
                },
                "experiment_detail": {"request_count": 1, "result_count": 0, "pending_request_count": 1},
                "belief_update_summary": {
                    "update_count": 1,
                    "items": [
                        {
                            "revision_rationale": "Belief remains unresolved because contradiction pressure is still active.",
                            "triggering_contradiction_ids": ["contr_1"],
                        }
                    ],
                },
                "current_belief_state": {
                    "current_state": "unresolved",
                    "current_strength": "tentative",
                    "contradiction_pressure": "moderate",
                    "support_balance_summary": "1 supporting line(s), 1 weakening line(s), 0 context-only line(s), 0 derived line(s); current attached structure is mixed.",
                    "latest_revision_rationale": "Belief remains unresolved because contradiction pressure is still active.",
                },
                "diagnostics": {"experiment_lifecycle_unresolved_state": "pending_result"},
            },
            {
                "claim_id": "claim_2",
                "claim": {"claim_type": "run_interpretation_caution", "claim_status": "active", "claim_scope": "run", "claim_text": "Fallback visible."},
                "attachment_context": {
                    "support_basis_summary": "Supported by run metadata.",
                    "contradiction_count": 0,
                    "active_contradiction_count": 0,
                    "contradictions": [],
                },
                "experiment_detail": {"request_count": 0, "result_count": 0, "pending_request_count": 0},
                "belief_update_summary": {"update_count": 0},
                "current_belief_state": {
                    "current_state": "absent",
                    "current_strength": "absent",
                    "contradiction_pressure": "none",
                    "support_balance_summary": "",
                    "latest_revision_rationale": "",
                },
                "diagnostics": {"experiment_lifecycle_unresolved_state": "no_experiment_request"},
            },
        ]
        focused_claim = build_focused_claim_inspection(
            claim_detail_items=claim_items,
            selected_claim_id="claim_2",
        )
        self.assertTrue(focused_claim["available"])
        self.assertEqual(focused_claim["selected_claim_id"], "claim_2")
        self.assertEqual(focused_claim["claim_scope"], "run")
        self.assertEqual(focused_claim["choice_count"], 2)
        self.assertTrue(focused_claim["multiple_available"])
        self.assertFalse(focused_claim["default_first_fallback_used"])
        self.assertEqual(focused_claim["contradiction_count"], 0)
        self.assertEqual(focused_claim["belief_contradiction_pressure"], "none")
        self.assertEqual(len(focused_claim["claim_choices"]), 2)
        self.assertTrue(any(choice["selected"] and choice["claim_id"] == "claim_2" for choice in focused_claim["claim_choices"]))

        fallback_claim = build_focused_claim_inspection(
            claim_detail_items=claim_items,
        )
        self.assertTrue(fallback_claim["available"])
        self.assertEqual(fallback_claim["selected_claim_id"], "claim_1")
        self.assertTrue(fallback_claim["default_first_fallback_used"])

        experiment_model = {
            "experiment_items": [
                {
                    "request_id": "req_1",
                    "linked_claim_ids": ["claim_1"],
                    "tested_claim_id": "claim_1",
                    "scope_context": {"claim_scope": "candidate", "candidate_id": "cand_1", "session_id": "session_1"},
                    "status": "requested",
                    "objective_summary": "Measure pIC50.",
                    "rationale_summary": "Confirm priority.",
                    "requested_measurement": "pIC50",
                    "experiment_intent": "claim_test",
                    "epistemic_goal_summary": "Reduce uncertainty around claim_1.",
                    "existing_context_summary": "Claim has recommendation-derived context and one uploaded evidence row.",
                    "strengthening_outcome_description": "A supportive pIC50 result would strengthen the claim.",
                    "weakening_outcome_description": "A contradictory pIC50 result would weaken the claim.",
                    "expected_learning_value": "Clarifies whether recommendation-derived support should remain trusted.",
                    "protocol_context_summary": "Candidate scope is anchored to CCO.",
                    "linked_claim_evidence_snapshot": [
                        {"linked_object_type": "recommendation", "relation_type": "derived_from", "summary": "Derived from ranked recommendation cand_1."},
                        {"linked_object_type": "evidence", "relation_type": "context_only", "summary": "Observed assay row for cand_1 is attached as context."},
                    ],
                    "epistemic_priority": {
                        "epistemic_priority_score": 0.88,
                        "epistemic_priority_band": "high",
                        "summary_rationale": "Prioritized because the claim remains unresolved and attached support is still weak or one-sided.",
                        "unresolved_claim_signal": 0.95,
                        "support_weakness_signal": 0.9,
                        "belief_change_opportunity_signal": 0.95,
                        "context_thinness_signal": 0.65,
                    },
                    "contradiction_count": 1,
                    "active_contradiction_count": 1,
                    "has_active_contradiction": True,
                    "has_result": False,
                    "result_summary": {"status": "absent", "summary_text": ""},
                    "has_belief_update": False,
                    "latest_belief_impact_summary": {
                        "summary_text": "",
                        "belief_state": "absent",
                        "belief_strength": "absent",
                        "contradiction_pressure": "moderate",
                        "revision_rationale": "",
                        "support_balance_summary": "",
                        "triggering_contradiction_ids": [],
                    },
                    "unresolved_state": "no_result_recorded",
                },
                {
                    "request_id": "req_2",
                    "linked_claim_ids": ["claim_2"],
                    "tested_claim_id": "claim_2",
                    "scope_context": {"claim_scope": "run", "session_id": "session_1"},
                    "status": "completed",
                    "objective_summary": "Check fallback behavior.",
                    "rationale_summary": "Run caution review.",
                    "requested_measurement": "fallback_review",
                    "experiment_intent": "claim_test",
                    "epistemic_goal_summary": "Clarify whether fallback behavior remains acceptable.",
                    "existing_context_summary": "Run-level caution claim is based on bridge-state metadata.",
                    "strengthening_outcome_description": "A consistent fallback review would strengthen the caution claim.",
                    "weakening_outcome_description": "A review that removes the caution basis would weaken the claim.",
                    "expected_learning_value": "Clarifies whether the current caution should remain attached to the run.",
                    "protocol_context_summary": "",
                    "linked_claim_evidence_snapshot": [
                        {"linked_object_type": "recommendation", "relation_type": "derived_from", "summary": "Run caution references the current recommendation set."},
                    ],
                    "epistemic_priority": {
                        "epistemic_priority_score": 0.46,
                        "epistemic_priority_band": "low",
                        "summary_rationale": "Prioritized because the claim still deserves follow-up against its current attached context.",
                        "unresolved_claim_signal": 0.35,
                        "support_weakness_signal": 0.3,
                        "belief_change_opportunity_signal": 0.25,
                        "context_thinness_signal": 0.85,
                    },
                    "contradiction_count": 0,
                    "active_contradiction_count": 0,
                    "has_active_contradiction": False,
                    "has_result": True,
                    "result_summary": {"status": "recorded", "summary_text": "Supportive assay result."},
                    "has_belief_update": True,
                    "latest_belief_impact_summary": {
                        "summary_text": "Supportive result recorded.",
                        "belief_state": "supported",
                        "belief_strength": "strengthened",
                        "contradiction_pressure": "low",
                        "revision_rationale": "A supportive result increased support because contradiction pressure is currently low.",
                        "support_balance_summary": "2 supporting line(s), 0 weakening line(s), 0 context-only line(s), 1 derived line(s); current attached structure leans supportive.",
                        "triggering_contradiction_ids": [],
                    },
                    "unresolved_state": "belief_updated",
                },
            ]
        }
        focused_experiment = build_focused_experiment_inspection(
            experiment_lifecycle_model=experiment_model,
            selected_request_id="req_2",
        )
        self.assertTrue(focused_experiment["available"])
        self.assertEqual(focused_experiment["selected_request_id"], "req_2")
        self.assertEqual(focused_experiment["status"], "completed")
        self.assertTrue(focused_experiment["has_belief_update"])
        self.assertEqual(focused_experiment["choice_count"], 2)
        self.assertTrue(focused_experiment["multiple_available"])
        self.assertFalse(focused_experiment["default_first_fallback_used"])
        self.assertEqual(focused_experiment["tested_claim_id"], "claim_2")
        self.assertEqual(focused_experiment["experiment_intent"], "claim_test")
        self.assertIn("Clarify whether fallback behavior", focused_experiment["epistemic_goal_summary"])
        self.assertEqual(focused_experiment["epistemic_priority_band"], "low")
        self.assertEqual(focused_experiment["epistemic_priority_score"], 0.46)
        self.assertIn("deserves follow-up", focused_experiment["epistemic_priority_summary"])
        self.assertFalse(focused_experiment["has_active_contradiction"])
        self.assertEqual(focused_experiment["belief_contradiction_pressure"], "low")
        self.assertIn("supportive result increased support", focused_experiment["belief_revision_rationale"].lower())
        self.assertEqual(len(focused_experiment["linked_claim_evidence_snapshot"]), 1)
        self.assertEqual(len(focused_experiment["experiment_choices"]), 2)
        self.assertTrue(
            any(choice["selected"] and choice["request_id"] == "req_2" for choice in focused_experiment["experiment_choices"])
        )

        fallback_experiment = build_focused_experiment_inspection(
            experiment_lifecycle_model=experiment_model,
        )
        self.assertTrue(fallback_experiment["available"])
        self.assertEqual(fallback_experiment["selected_request_id"], "req_1")
        self.assertTrue(fallback_experiment["default_first_fallback_used"])
        self.assertTrue(fallback_experiment["has_active_contradiction"])

        absent_experiment = build_focused_experiment_inspection(
            experiment_lifecycle_model={},
            selected_request_id="req_missing",
        )
        self.assertFalse(absent_experiment["available"])
        self.assertEqual(absent_experiment["absence_reason"], "no_experiment_available_for_focused_inspection")
        self.assertFalse(absent_experiment["selected_available"])

    def test_dashboard_and_session_history_expose_compact_epistemic_surfaces(self):
        projection = {
            "decision_payload": {"artifact_state": "ok", "summary": {"candidate_count": 1, "top_experiment_value": 0.7}, "top_experiments": []},
            "analysis_report": {"warnings": [], "decision_intent": "prioritize_experiments"},
            "target_definition": {"target_name": "pIC50", "target_kind": "regression"},
            "measurement_summary": {"rows_with_values": 1, "rows_with_labels": 0, "semantic_mode": "measurement_dataset", "value_column": "pic50"},
            "comparison_anchors": {},
            "run_provenance": {},
            "ranking_policy": {},
            "candidate_preview": [],
            "outcome_profile": {},
            "belief_layer_summary": {"claim_count": 2, "active_claim_count": 2, "belief_state_count": 1, "has_belief_layer": True},
            "experiment_lifecycle_summary": {"experiment_request_count": 1, "pending_count": 1, "result_recorded_count": 0, "claim_linked_unresolved_count": 1, "belief_updated_count": 0, "has_experiments": True},
            "claim_detail_summary": {"has_claim_detail_surface": True, "claim_detail_count": 2, "candidate_linked_count": 1, "run_linked_count": 1},
            "session_epistemic_summary": {"status": "pending_experiments", "pending_experiment_count": 1, "available": True},
            "epistemic_entry_points": {"claim_detail_available": True, "experiment_lifecycle_available": True},
            "diagnostics": {"session_epistemic_summary_available": True},
            "recommendation_summary": "Start with cand_1.",
        }

        with patch("system.dashboard_data.build_scientific_session_projection", return_value=projection), patch(
            "system.dashboard_data._load_csv",
            return_value=None,
        ), patch(
            "system.dashboard_data.build_review_queue",
            return_value={"summary": {"pending_review": 0}, "queue": []},
        ):
            dashboard = build_dashboard_context(session_id="session_epistemic", workspace_id="workspace_1")

        self.assertEqual(dashboard["session_epistemic_summary"]["status"], "pending_experiments")
        self.assertTrue(dashboard["epistemic_entry_points"]["claim_detail_available"])

        session_record = {
            "session_id": "session_epistemic",
            "workspace_id": "workspace_1",
            "source_name": "upload.csv",
            "input_type": "csv",
            "created_at": "2026-04-17T10:00:00+00:00",
            "updated_at": "2026-04-17T11:00:00+00:00",
            "upload_metadata": {"validation_summary": {"total_rows": 1, "valid_smiles_count": 1, "duplicate_count": 0}},
            "summary_metadata": {},
        }

        with patch("system.session_history.build_scientific_session_projection", return_value=projection), patch(
            "system.session_history.load_analysis_report_payload",
            return_value={},
        ), patch(
            "system.session_history.load_decision_artifact_payload",
            return_value={"artifact_state": "ok", "summary": {"candidate_count": 1, "top_experiment_value": 0.7}},
        ), patch(
            "system.session_history.build_session_workspace_memory",
            return_value={},
        ):
            history = build_session_history_context(
                sessions=[session_record],
                workspace_id="workspace_1",
                latest_session_id="session_epistemic",
                active_session_id="session_epistemic",
            )

        self.assertEqual(history["items"][0]["session_epistemic_summary"]["status"], "pending_experiments")
        self.assertTrue(history["items"][0]["epistemic_entry_points"]["experiment_lifecycle_available"])

    def test_templates_render_compact_epistemic_partials(self):
        repo_root = Path(__file__).resolve().parents[1]
        discovery_template = (repo_root / "templates" / "discovery.html").read_text()
        dashboard_template = (repo_root / "templates" / "dashboard.html").read_text()
        sessions_template = (repo_root / "templates" / "sessions.html").read_text()
        base_template = (repo_root / "templates" / "base.html").read_text()
        reveal_template = (repo_root / "templates" / "_epistemic_detail_reveal.html").read_text()
        claim_focus_template = (repo_root / "templates" / "_claim_focus_inspection.html").read_text()
        experiment_focus_template = (repo_root / "templates" / "_experiment_focus_inspection.html").read_text()

        self.assertIn("workbench.session_epistemic_summary", discovery_template)
        self.assertIn("workbench.epistemic_entry_points", discovery_template)
        self.assertIn('"_epistemic_session_summary.html"', discovery_template)
        self.assertIn("workbench.session_epistemic_detail_reveal", discovery_template)
        self.assertIn("workbench.focused_claim_inspection", discovery_template)
        self.assertIn("workbench.focused_experiment_inspection", discovery_template)
        self.assertIn("dashboard.session_epistemic_summary", dashboard_template)
        self.assertIn("dashboard.epistemic_entry_points", dashboard_template)
        self.assertIn("dashboard.session_epistemic_detail_reveal", dashboard_template)
        self.assertIn("dashboard.focused_claim_inspection", dashboard_template)
        self.assertIn("dashboard.focused_experiment_inspection", dashboard_template)
        self.assertIn("item.session_epistemic_summary", sessions_template)
        self.assertIn("item.epistemic_entry_points", sessions_template)
        self.assertIn("item.session_epistemic_detail_reveal", sessions_template)
        self.assertIn("/epistemic_focus.js", base_template)
        self.assertIn('data-epistemic-rendered="detail-reveal"', reveal_template)
        self.assertIn('data-epistemic-rendered="focused-claim-inspection"', claim_focus_template)
        self.assertIn('data-epistemic-rendered="focused-claim-selector"', claim_focus_template)
        self.assertIn("data-epistemic-focus-root", claim_focus_template)
        self.assertIn("data-epistemic-focus-select", claim_focus_template)
        self.assertIn("data-epistemic-focus-panel", claim_focus_template)
        self.assertIn("data-claim-choice-panel", claim_focus_template)
        self.assertIn('data-epistemic-rendered="focused-experiment-inspection"', experiment_focus_template)
        self.assertIn('data-epistemic-rendered="focused-experiment-selector"', experiment_focus_template)
        self.assertIn("data-epistemic-focus-root", experiment_focus_template)
        self.assertIn("data-epistemic-focus-select", experiment_focus_template)
        self.assertIn("data-epistemic-focus-panel", experiment_focus_template)
        self.assertIn("data-experiment-choice-panel", experiment_focus_template)

    def test_discovery_frontend_uses_compact_candidate_epistemic_context(self):
        repo_root = Path(__file__).resolve().parents[1]
        discovery_js = (repo_root / "static" / "discovery.js").read_text()
        focus_js = (repo_root / "static" / "epistemic_focus.js").read_text()

        self.assertIn("candidate.candidate_epistemic_context", discovery_js)
        self.assertIn("candidate.candidate_epistemic_detail_reveal", discovery_js)
        self.assertIn("candidate.focused_claim_inspection", discovery_js)
        self.assertIn("candidate.focused_experiment_inspection", discovery_js)
        self.assertIn("claim.claim_choices", discovery_js)
        self.assertIn("experiment.experiment_choices", discovery_js)
        self.assertIn('data-epistemic-rendered="candidate-context"', discovery_js)
        self.assertIn('data-epistemic-rendered="candidate-detail-reveal"', discovery_js)
        self.assertIn('data-epistemic-rendered="focused-claim-inspection"', discovery_js)
        self.assertIn('data-epistemic-rendered="focused-experiment-inspection"', discovery_js)
        self.assertIn('data-epistemic-rendered="focused-claim-selector"', discovery_js)
        self.assertIn('data-epistemic-rendered="focused-experiment-selector"', discovery_js)
        self.assertIn("window.discoveryEpistemicFocus?.enhance(root)", discovery_js)
        self.assertIn("window.discoveryEpistemicFocus?.enhance(contentNode)", discovery_js)
        self.assertIn("data-epistemic-focus-root", discovery_js)
        self.assertNotIn("candidate.claim_detail_items[0]", discovery_js)
        self.assertIn("selectionState", focus_js)
        self.assertIn("data-epistemic-focus-select", focus_js)


if __name__ == "__main__":
    unittest.main()
