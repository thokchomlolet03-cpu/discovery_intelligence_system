import os
import tempfile
import unittest
from pathlib import Path

from system.db import ensure_database_ready, reset_database_state
from system.db.repositories import BeliefUpdateRepository, ClaimRepository
from system.services.claim_service import (
    claim_refs_from_records,
    claims_summary_from_records,
    create_session_claims,
    list_session_claims,
    sync_claim_governed_review_snapshot,
)
from system.services.scientific_session_truth_service import build_scientific_session_truth


class ClaimServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        reset_database_state(f"sqlite:///{Path(self.tmpdir.name) / 'claims.db'}")
        ensure_database_ready()

    def tearDown(self):
        reset_database_state()
        os.environ.pop("DISCOVERY_ALLOWED_ARTIFACT_ROOTS", None)
        self.tmpdir.cleanup()

    def _claim_payload(self, *, session_id: str, candidate_id: str, smiles: str) -> dict[str, object]:
        return {
            "claim_id": "",
            "workspace_id": "workspace_1",
            "session_id": session_id,
            "candidate_id": candidate_id,
            "candidate_reference": {
                "candidate_id": candidate_id,
                "candidate_label": f"{candidate_id} ({smiles})",
                "canonical_smiles": smiles,
                "smiles": smiles,
                "rank": 1,
            },
            "target_definition_snapshot": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
            },
            "claim_type": "recommendation_assertion",
            "claim_text": f"Under the current session evidence, {candidate_id} ({smiles}) is a plausible follow-up candidate to test for higher pIC50.",
            "bounded_scope": "Bounded scope.",
            "support_level": "limited",
            "evidence_basis_summary": "Derived from current session evidence.",
            "source_recommendation_rank": 1,
            "status": "proposed",
            "created_at": "2026-04-03T10:00:00+00:00",
            "updated_at": "2026-04-03T10:00:00+00:00",
            "created_by": "system",
            "created_by_user_id": "",
            "reviewed_at": None,
            "reviewed_by": "",
            "metadata": {},
        }

    def test_create_session_claims_persists_bounded_claims_without_duplication(self):
        scientific_truth = {
            "session_id": "session_claims_1",
            "target_definition": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
            },
            "evidence_loop": {
                "active_modeling_evidence": ["Observed experimental values"],
                "active_ranking_evidence": ["Model predictions", "Reference chemistry context"],
            },
        }
        decision_payload = {
            "top_experiments": [
                {
                    "rank": 1,
                    "candidate_id": "cand_1",
                    "smiles": "CCO",
                    "canonical_smiles": "CCO",
                    "trust_label": "Stronger trust",
                    "rationale_primary_driver": "High ranking compatibility and moderate novelty support near-term testing.",
                    "domain_status": "in_domain",
                },
                {
                    "rank": 2,
                    "candidate_id": "cand_2",
                    "smiles": "CCN",
                    "canonical_smiles": "CCN",
                    "trust_label": "Mixed trust",
                    "rationale_primary_driver": "Prediction dispersion makes this a useful learning candidate.",
                    "domain_status": "near_boundary",
                },
            ]
        }

        created = create_session_claims(
            session_id="session_claims_1",
            workspace_id="workspace_1",
            decision_payload=decision_payload,
            scientific_truth=scientific_truth,
            created_by_user_id="user_1",
        )
        recreated = create_session_claims(
            session_id="session_claims_1",
            workspace_id="workspace_1",
            decision_payload=decision_payload,
            scientific_truth=scientific_truth,
            created_by_user_id="user_1",
        )

        claims = list_session_claims("session_claims_1", workspace_id="workspace_1")
        self.assertEqual(len(created), 2)
        self.assertEqual(len(recreated), 2)
        self.assertEqual(len(claims), 2)
        self.assertEqual(claims[0]["status"], "proposed")
        self.assertEqual(claims[0]["claim_type"], "recommendation_assertion")
        self.assertIn("plausible follow-up candidate", claims[0]["claim_text"].lower())
        self.assertIn("not experimental confirmation", claims[0]["bounded_scope"].lower())
        self.assertEqual(claims[0]["support_level"], "strong")
        self.assertEqual(claims[1]["support_level"], "moderate")
        self.assertIn("modeling uses observed experimental values", claims[0]["evidence_basis_summary"].lower())

    def test_scientific_session_truth_includes_claim_refs_when_claims_exist(self):
        decision_payload = {
            "top_experiments": [
                {
                    "rank": 1,
                    "candidate_id": "cand_1",
                    "smiles": "CCO",
                    "canonical_smiles": "CCO",
                    "trust_label": "Stronger trust",
                    "rationale_primary_driver": "High ranking compatibility supports near-term testing.",
                    "domain_status": "in_domain",
                }
            ]
        }
        scientific_truth_seed = {
            "session_id": "session_claims_2",
            "target_definition": {
                "target_name": "solubility",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
            },
            "evidence_loop": {
                "active_modeling_evidence": ["Observed experimental values"],
                "active_ranking_evidence": ["Model predictions"],
            },
        }
        create_session_claims(
            session_id="session_claims_2",
            workspace_id="workspace_1",
            decision_payload=decision_payload,
            scientific_truth=scientific_truth_seed,
            created_by_user_id="user_1",
        )

        truth = build_scientific_session_truth(
            session_id="session_claims_2",
            workspace_id="workspace_1",
            source_name="upload.csv",
            session_record={
                "session_id": "session_claims_2",
                "workspace_id": "workspace_1",
                "source_name": "upload.csv",
                "summary_metadata": {"last_job_status": "succeeded"},
            },
            analysis_report={
                "modeling_mode": "regression",
                "decision_intent": "prioritize_experiments",
                "target_definition": scientific_truth_seed["target_definition"],
                "ranking_policy": {"primary_score": "confidence", "primary_score_label": "Ranking compatibility"},
                "run_contract": {"training_scope": "session_trained"},
                "comparison_anchors": {"comparison_ready": True},
            },
            decision_payload={"summary": {"candidate_count": 1}, **decision_payload},
            review_queue={"summary": {"counts": {}}},
        )

        self.assertEqual(truth["claims_summary"]["claim_count"], 1)
        self.assertIn("bounded recommendation-derived assertions", truth["claims_summary"]["summary_text"].lower())
        self.assertEqual(truth["claim_refs"][0]["candidate_id"], "cand_1")
        self.assertEqual(truth["claim_refs"][0]["claim_support_role_label"], "No governed support yet")
        self.assertIn("does not currently have a governed support-change record", truth["claim_refs"][0]["claim_chronology_summary_text"].lower())
        self.assertEqual(truth["claim_refs"][0]["claim_support_basis_mix_label"], "No governed support yet")
        self.assertIn(
            "no current support-basis mix is recorded",
            truth["claim_refs"][0]["claim_support_basis_mix_summary"].lower(),
        )
        self.assertEqual(truth["claim_refs"][0]["claim_read_across_label"], "No prior claim context")
        self.assertIn("no strong prior target-scoped claim context", truth["claim_refs"][0]["claim_read_across_summary"].lower())
        self.assertEqual(truth["claim_refs"][0]["claim_prior_support_quality_label"], "No useful prior claim context")
        self.assertIn("no useful prior governed claim context", truth["claim_refs"][0]["claim_prior_support_quality_summary"].lower())
        self.assertEqual(truth["claim_refs"][0]["claim_actionability_label"], "No governed support yet")
        self.assertEqual(truth["claim_refs"][0]["claim_next_step_label"], "Insufficient governed basis")
        self.assertEqual(truth["claims_summary"]["claims_with_no_governed_support_count"], 1)
        self.assertIn("no governed support yet", truth["claims_summary"]["chronology_summary_text"].lower())
        self.assertIn("no governed support yet", truth["claims_summary"]["claim_support_basis_summary_text"].lower())
        self.assertEqual(truth["claims_summary"]["claims_with_insufficient_governed_basis_count"], 1)
        self.assertIn("claim actionability remains bounded", truth["claims_summary"]["claim_actionability_summary_text"].lower())
        self.assertEqual(truth["claims_summary"]["no_prior_claim_context_count"], 1)
        self.assertEqual(truth["claims_summary"]["claims_with_no_useful_prior_context_count"], 1)
        self.assertIn("no strong prior target-scoped claim context", truth["claims_summary"]["read_across_summary_text"].lower())

    def test_create_session_claims_records_initial_local_only_governed_review_snapshot(self):
        created = create_session_claims(
            session_id="session_claims_review_1",
            workspace_id="workspace_1",
            decision_payload={
                "top_experiments": [
                    {
                        "rank": 1,
                        "candidate_id": "cand_1",
                        "smiles": "CCO",
                        "canonical_smiles": "CCO",
                    }
                ]
            },
            scientific_truth={
                "target_definition": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                }
            },
        )

        refs = claim_refs_from_records(created)

        self.assertEqual(refs[0]["claim_governed_review_record_count"], 1)
        self.assertEqual(refs[0]["claim_trust_tier_label"], "Local-only evidence")
        self.assertEqual(refs[0]["claim_source_class_label"], "Unknown-origin structured input")
        self.assertIn("latest posture is not reviewed", refs[0]["claim_governed_review_history_summary"].lower())
        self.assertIn("promotion outcome is local only", refs[0]["claim_promotion_audit_summary"].lower())

    def test_sync_claim_governed_review_snapshot_records_history_when_claim_posture_changes(self):
        claim_repository = ClaimRepository()
        belief_update_repository = BeliefUpdateRepository()
        claim = claim_repository.upsert_claim(
            self._claim_payload(session_id="session_claims_review_2", candidate_id="cand_1", smiles="CCO")
        )

        first = sync_claim_governed_review_snapshot(
            claim_id=claim["claim_id"],
            workspace_id="workspace_1",
            recorded_by="system",
        )
        belief_update_repository.upsert_belief_update(
            {
                "belief_update_id": "",
                "workspace_id": "workspace_1",
                "session_id": "session_claims_review_2",
                "claim_id": claim["claim_id"],
                "experiment_result_id": "",
                "candidate_id": "cand_1",
                "candidate_label": "cand_1 (CCO)",
                "previous_support_level": "limited",
                "updated_support_level": "moderate",
                "update_direction": "strengthened",
                "update_reason": "Observed result linked to claim context.",
                "governance_status": "accepted",
                "created_at": "2026-04-03T11:00:00+00:00",
                "created_by": "scientist",
                "created_by_user_id": "",
                "metadata": {
                    "source_class_label": "Internal governed experimental source",
                    "provenance_confidence_label": "Strong provenance",
                },
            }
        )
        second = sync_claim_governed_review_snapshot(
            claim_id=claim["claim_id"],
            workspace_id="workspace_1",
            recorded_by="scientist",
        )

        refs = claim_refs_from_records(
            [claim_repository.get_claim(claim["claim_id"], workspace_id="workspace_1")],
            belief_updates=belief_update_repository.list_belief_updates(workspace_id="workspace_1"),
        )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertNotEqual(first["review_record_id"], second["review_record_id"])
        self.assertEqual(refs[0]["claim_governed_review_record_count"], 2)
        self.assertEqual(refs[0]["claim_source_class_label"], "Internal governed experimental source")
        self.assertEqual(refs[0]["claim_trust_tier_label"], "Candidate evidence")
        self.assertIn("2 governed review records", refs[0]["claim_governed_review_history_summary"].lower())

    def test_claim_summary_groups_active_and_historical_support_per_claim(self):
        claims = [
            {
                "claim_id": "claim_1",
                "candidate_id": "cand_1",
                "candidate_reference": {"candidate_label": "cand_1 (CCO)"},
                "claim_type": "recommendation_assertion",
                "claim_text": "Claim one",
                "support_level": "strong",
                "status": "proposed",
                "source_recommendation_rank": 1,
                "created_at": "2026-04-02T10:00:00+00:00",
            },
            {
                "claim_id": "claim_2",
                "candidate_id": "cand_2",
                "candidate_reference": {"candidate_label": "cand_2 (CCN)"},
                "claim_type": "recommendation_assertion",
                "claim_text": "Claim two",
                "support_level": "moderate",
                "status": "proposed",
                "source_recommendation_rank": 2,
                "created_at": "2026-04-02T10:00:00+00:00",
            },
        ]
        belief_updates = [
            {
                "claim_id": "claim_1",
                "governance_status": "accepted",
                "result_interpretation_basis": "Observed label",
                "support_input_quality_label": "Stronger interpretation basis",
                "update_direction": "strengthened",
            },
            {"claim_id": "claim_1", "governance_status": "superseded"},
            {"claim_id": "claim_2", "governance_status": "superseded"},
        ]

        refs = claim_refs_from_records(claims, belief_updates=belief_updates)
        summary = claims_summary_from_records(claims, belief_updates=belief_updates)

        self.assertEqual(refs[0]["claim_support_role_label"], "Active governed support")
        self.assertEqual(refs[0]["current_support_count"], 1)
        self.assertEqual(refs[0]["historical_support_count"], 1)
        self.assertEqual(refs[0]["claim_support_basis_mix_label"], "Grounded mostly in observed labels")
        self.assertEqual(refs[0]["claim_observed_label_support_count"], 1)
        self.assertEqual(refs[0]["claim_actionability_label"], "Action-ready from current active support")
        self.assertEqual(refs[0]["claim_actionability_basis_label"], "Current active support basis")
        self.assertEqual(
            refs[0]["claim_active_support_actionability_label"],
            "Current active support is decision-useful",
        )
        self.assertEqual(refs[0]["claim_support_quality_label"], "Decision-useful current active support")
        self.assertEqual(refs[0]["claim_governed_support_posture_label"], "Current support governs present posture")
        self.assertEqual(refs[0]["claim_support_coherence_label"], "Coherent current support")
        self.assertEqual(refs[0]["claim_support_reuse_label"], "Strongly reusable governed support")
        self.assertEqual(refs[0]["claim_broader_reuse_label"], "Support is locally meaningful, not broadly governing")
        self.assertEqual(refs[0]["claim_future_reuse_candidacy_label"], "Local-only future reuse context")
        self.assertEqual(refs[0]["claim_continuity_cluster_posture_label"], "Local-only continuity cluster")
        self.assertEqual(
            refs[0]["claim_promotion_candidate_posture_label"],
            "Context-only continuity, not a promotion candidate",
        )
        self.assertEqual(refs[0]["claim_promotion_stability_label"], "Insufficient continuity stability")
        self.assertEqual(refs[0]["claim_promotion_gate_status_label"], "Not a governed promotion candidate")
        self.assertEqual(refs[0]["claim_promotion_block_reason_label"], "Local-only meaning")
        self.assertEqual(
            refs[0]["claim_historical_support_actionability_label"],
            "Historical context remains secondary",
        )
        self.assertEqual(refs[0]["claim_next_step_label"], "Follow-up experiment is reasonable now")
        self.assertEqual(refs[1]["claim_support_role_label"], "Historical support only")
        self.assertEqual(refs[1]["claim_support_basis_mix_label"], "No governed support yet")
        self.assertEqual(refs[1]["claim_actionability_label"], "Historically interesting, not currently action-ready")
        self.assertTrue(refs[1]["claim_historical_interest_only_flag"])
        self.assertEqual(refs[1]["claim_actionability_basis_label"], "Historical interest only")
        self.assertEqual(refs[1]["claim_active_support_actionability_label"], "No current active support")
        self.assertEqual(refs[1]["claim_historical_support_actionability_label"], "Historical context only")
        self.assertEqual(refs[1]["claim_support_reuse_label"], "Historical-only for reuse")
        self.assertEqual(refs[1]["claim_broader_reuse_label"], "Support is locally meaningful, not broadly governing")
        self.assertEqual(refs[1]["claim_future_reuse_candidacy_label"], "Local-only future reuse context")
        self.assertEqual(refs[1]["claim_continuity_cluster_posture_label"], "Local-only continuity cluster")
        self.assertEqual(
            refs[1]["claim_promotion_candidate_posture_label"],
            "Context-only continuity, not a promotion candidate",
        )
        self.assertEqual(refs[1]["claim_promotion_stability_label"], "Insufficient continuity stability")
        self.assertEqual(refs[1]["claim_promotion_gate_status_label"], "Not a governed promotion candidate")
        self.assertEqual(refs[1]["claim_promotion_block_reason_label"], "Local-only meaning")
        self.assertEqual(refs[1]["claim_next_step_label"], "Historically interesting, gather fresh evidence first")
        self.assertEqual(summary["claims_with_active_support_count"], 1)
        self.assertEqual(summary["claims_with_historical_support_only_count"], 1)
        self.assertIn("active governed support", summary["chronology_summary_text"].lower())
        self.assertEqual(summary["claims_mostly_observed_label_grounded_count"], 1)
        self.assertEqual(summary["claims_with_decision_useful_active_support_count"], 1)
        self.assertEqual(summary["claims_action_ready_follow_up_count"], 1)
        self.assertEqual(summary["claims_action_ready_from_active_support_count"], 1)
        self.assertEqual(summary["claims_with_contested_current_support_count"], 0)
        self.assertEqual(summary["claims_with_active_but_limited_actionability_count"], 0)
        self.assertEqual(summary["claims_historically_interesting_count"], 1)
        self.assertEqual(summary["claims_with_mixed_current_historical_actionability_count"], 0)
        self.assertEqual(summary["claims_with_insufficient_governed_basis_count"], 1)
        self.assertEqual(summary["continuity_cluster_posture_label"], "Local-only continuity cluster")
        self.assertEqual(summary["promotion_candidate_posture_label"], "Context-only continuity, not a promotion candidate")
        self.assertEqual(summary["promotion_stability_label"], "Insufficient continuity stability")
        self.assertEqual(summary["promotion_gate_status_label"], "Not a governed promotion candidate")
        self.assertEqual(summary["promotion_block_reason_label"], "Local-only meaning")
        self.assertEqual(summary["claims_with_no_active_governed_support_actionability_count"], 0)
        self.assertEqual(summary["broader_reuse_label"], "Support is locally meaningful, not broadly governing")
        self.assertEqual(summary["broader_continuity_label"], "No broader continuity cluster")
        self.assertEqual(summary["future_reuse_candidacy_label"], "Local-only future reuse context")
        self.assertIn("claim support-basis composition remains bounded", summary["claim_support_basis_summary_text"].lower())
        self.assertIn("claim actionability remains bounded", summary["claim_actionability_summary_text"].lower())
        self.assertIn("claim actionability basis remains bounded", summary["claim_actionability_basis_summary_text"].lower())

    def test_claim_read_across_can_upgrade_broader_reuse_when_prior_continuity_is_governing(self):
        current_claim = {
            "claim_id": "claim_current",
            "candidate_id": "cand_1",
            "candidate_reference": {"candidate_label": "cand_1 (CCO)"},
            "target_definition_snapshot": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
            },
            "claim_type": "recommendation_assertion",
            "claim_text": "Current claim",
            "support_level": "strong",
            "status": "proposed",
            "source_recommendation_rank": 1,
            "created_at": "2026-04-03T10:00:00+00:00",
        }
        prior_claim = {
            "claim_id": "claim_prior",
            "candidate_id": "cand_1",
            "candidate_reference": {"candidate_label": "cand_1 (CCO)"},
            "target_definition_snapshot": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
            },
            "claim_type": "recommendation_assertion",
            "claim_text": "Prior claim",
            "support_level": "strong",
            "status": "proposed",
            "source_recommendation_rank": 1,
            "created_at": "2026-04-01T10:00:00+00:00",
        }
        current_updates = [
            {
                "claim_id": "claim_current",
                "governance_status": "accepted",
                "result_interpretation_basis": "Observed label",
                "support_input_quality_label": "Stronger interpretation basis",
                "update_direction": "strengthened",
            }
        ]
        prior_updates = [
            {
                "claim_id": "claim_prior",
                "governance_status": "accepted",
                "result_interpretation_basis": "Observed label",
                "support_input_quality_label": "Stronger interpretation basis",
                "update_direction": "strengthened",
            }
        ]

        refs = claim_refs_from_records(
            [current_claim],
            belief_updates=current_updates,
            prior_claims=[prior_claim],
            prior_belief_updates=prior_updates,
        )
        summary = claims_summary_from_records(
            [current_claim],
            belief_updates=current_updates,
            prior_claims=[prior_claim],
            prior_belief_updates=prior_updates,
        )

        self.assertEqual(refs[0]["claim_read_across_label"], "Continuity-aligned claim")
        self.assertEqual(refs[0]["claim_prior_support_quality_label"], "Posture-governing continuity")
        self.assertEqual(refs[0]["claim_broader_reuse_label"], "Broader reuse is strong under coherent current support")
        self.assertEqual(refs[0]["claim_future_reuse_candidacy_label"], "Stronger future governed reuse candidacy")
        self.assertEqual(refs[0]["claim_continuity_cluster_posture_label"], "Promotion-candidate continuity cluster")
        self.assertEqual(
            refs[0]["claim_promotion_candidate_posture_label"],
            "Stronger broader governed reuse candidate",
        )
        self.assertEqual(refs[0]["claim_promotion_stability_label"], "Stable enough for governed promotion review")
        self.assertEqual(refs[0]["claim_promotion_gate_status_label"], "Promotable under bounded governed rules")
        self.assertEqual(refs[0]["claim_promotion_block_reason_label"], "No material promotion block recorded")
        self.assertEqual(summary["broader_reuse_label"], "Broader reuse is strong under coherent current support")
        self.assertEqual(summary["broader_continuity_label"], "Coherent broader continuity cluster")
        self.assertEqual(summary["future_reuse_candidacy_label"], "Stronger future governed reuse candidacy")
        self.assertEqual(summary["continuity_cluster_posture_label"], "Promotion-candidate continuity cluster")
        self.assertEqual(summary["promotion_candidate_posture_label"], "Stronger broader governed reuse candidate")
        self.assertEqual(summary["promotion_stability_label"], "Stable enough for governed promotion review")
        self.assertEqual(summary["promotion_gate_status_label"], "Promotable under bounded governed rules")
        self.assertEqual(summary["promotion_block_reason_label"], "No material promotion block recorded")

    def test_claim_summary_adds_lightweight_cross_session_read_across(self):
        claims = [
            {
                "claim_id": "claim_1",
                "session_id": "session_current",
                "candidate_id": "cand_1",
                "candidate_reference": {"candidate_label": "cand_1 (CCO)", "candidate_id": "cand_1", "canonical_smiles": "CCO"},
                "target_definition_snapshot": {"target_name": "pIC50", "target_kind": "regression", "optimization_direction": "maximize"},
                "claim_type": "recommendation_assertion",
                "claim_text": "Claim one",
                "support_level": "strong",
                "status": "proposed",
                "source_recommendation_rank": 1,
                "created_at": "2026-04-02T10:00:00+00:00",
            },
            {
                "claim_id": "claim_2",
                "session_id": "session_current",
                "candidate_id": "cand_2",
                "candidate_reference": {"candidate_label": "cand_2 (CCN)", "candidate_id": "cand_2", "canonical_smiles": "CCN"},
                "target_definition_snapshot": {"target_name": "pIC50", "target_kind": "regression", "optimization_direction": "maximize"},
                "claim_type": "recommendation_assertion",
                "claim_text": "Claim two",
                "support_level": "moderate",
                "status": "proposed",
                "source_recommendation_rank": 2,
                "created_at": "2026-04-02T10:00:00+00:00",
            },
        ]
        prior_claims = [
            {
                "claim_id": "claim_prior_1",
                "session_id": "session_prior",
                "candidate_id": "cand_1",
                "candidate_reference": {"candidate_id": "cand_1", "canonical_smiles": "CCO"},
                "target_definition_snapshot": {"target_name": "pIC50", "target_kind": "regression", "optimization_direction": "maximize"},
            },
            {
                "claim_id": "claim_prior_2",
                "session_id": "session_prior",
                "candidate_id": "cand_3",
                "candidate_reference": {"candidate_id": "cand_3", "canonical_smiles": "CCC"},
                "target_definition_snapshot": {"target_name": "pIC50", "target_kind": "regression", "optimization_direction": "maximize"},
            },
            {
                "claim_id": "claim_prior_3",
                "session_id": "session_prior",
                "candidate_id": "cand_4",
                "candidate_reference": {"candidate_id": "cand_4", "canonical_smiles": "CCCC"},
                "target_definition_snapshot": {"target_name": "pIC50", "target_kind": "regression", "optimization_direction": "maximize"},
            },
        ]

        prior_belief_updates = [
            {"claim_id": "claim_prior_1", "governance_status": "accepted"},
            {"claim_id": "claim_prior_2", "governance_status": "superseded"},
        ]

        refs = claim_refs_from_records(claims, prior_claims=prior_claims, prior_belief_updates=prior_belief_updates)
        summary = claims_summary_from_records(
            claims,
            prior_claims=prior_claims,
            prior_belief_updates=prior_belief_updates,
        )

        self.assertEqual(refs[0]["claim_read_across_label"], "Continuity-aligned claim")
        self.assertEqual(refs[0]["claim_prior_support_quality_label"], "Posture-governing continuity")
        self.assertEqual(refs[0]["claim_prior_active_support_count"], 1)
        self.assertEqual(refs[0]["claim_prior_context_count"], 3)
        self.assertEqual(refs[1]["claim_read_across_label"], "New claim context")
        self.assertEqual(refs[1]["claim_prior_support_quality_label"], "Sparse prior claim context")
        self.assertEqual(summary["continuity_aligned_claim_count"], 1)
        self.assertEqual(summary["new_claim_context_count"], 1)
        self.assertEqual(summary["claims_with_active_governed_continuity_count"], 1)
        self.assertEqual(summary["claims_with_sparse_prior_context_count"], 1)
        self.assertIn("posture-governing continuity", summary["read_across_summary_text"].lower())

    def test_claim_actionability_basis_counts_distinguish_active_limited_mixed_and_no_active(self):
        claims = [
            {
                "claim_id": "claim_1",
                "candidate_id": "cand_1",
                "candidate_reference": {"candidate_label": "cand_1 (CCO)"},
                "claim_type": "recommendation_assertion",
                "claim_text": "Claim one",
                "support_level": "moderate",
                "status": "proposed",
                "source_recommendation_rank": 1,
                "created_at": "2026-04-02T10:00:00+00:00",
            },
            {
                "claim_id": "claim_2",
                "candidate_id": "cand_2",
                "candidate_reference": {"candidate_label": "cand_2 (CCN)"},
                "claim_type": "recommendation_assertion",
                "claim_text": "Claim two",
                "support_level": "moderate",
                "status": "proposed",
                "source_recommendation_rank": 2,
                "created_at": "2026-04-02T10:00:00+00:00",
            },
            {
                "claim_id": "claim_3",
                "candidate_id": "cand_3",
                "candidate_reference": {"candidate_label": "cand_3 (CCC)"},
                "claim_type": "recommendation_assertion",
                "claim_text": "Claim three",
                "support_level": "limited",
                "status": "proposed",
                "source_recommendation_rank": 3,
                "created_at": "2026-04-02T10:00:00+00:00",
            },
        ]
        belief_updates = [
            {
                "claim_id": "claim_1",
                "governance_status": "proposed",
                "result_interpretation_basis": "Numeric outcome under current target rule",
                "support_input_quality_label": "Cautious interpretation basis",
                "numeric_result_resolution_label": "Interpreted through current target rule",
                "update_direction": "strengthened",
            },
            {
                "claim_id": "claim_2",
                "governance_status": "accepted",
                "result_interpretation_basis": "Observed label",
                "support_input_quality_label": "Stronger interpretation basis",
                "update_direction": "strengthened",
            },
            {
                "claim_id": "claim_2",
                "governance_status": "proposed",
                "result_interpretation_basis": "Numeric outcome under current target rule",
                "support_input_quality_label": "Weak interpretation basis",
                "numeric_result_resolution_label": "Unresolved under current numeric basis",
                "update_direction": "unresolved",
            },
            {"claim_id": "claim_2", "governance_status": "superseded"},
            {"claim_id": "claim_3", "governance_status": "rejected"},
        ]

        refs = claim_refs_from_records(claims, belief_updates=belief_updates)
        summary = claims_summary_from_records(claims, belief_updates=belief_updates)

        refs_by_id = {item["claim_id"]: item for item in refs}
        self.assertEqual(refs_by_id["claim_1"]["claim_actionability_label"], "Promising but needs stronger evidence")
        self.assertEqual(refs_by_id["claim_1"]["claim_governed_support_posture_label"], "Current support remains tentative")
        self.assertEqual(
            refs_by_id["claim_1"]["claim_active_support_actionability_label"],
            "Current active support remains limited",
        )
        self.assertEqual(refs_by_id["claim_1"]["claim_historical_support_actionability_label"], "No historical support context")
        self.assertEqual(refs_by_id["claim_2"]["claim_support_coherence_label"], "Current support is contested")
        self.assertEqual(refs_by_id["claim_2"]["claim_support_reuse_label"], "Reuse with contradiction caution")
        self.assertEqual(refs_by_id["claim_2"]["claim_actionability_label"], "Mixed basis, needs clarifying experiment")
        self.assertEqual(refs_by_id["claim_2"]["claim_actionability_basis_label"], "Contested current basis")
        self.assertEqual(
            refs_by_id["claim_2"]["claim_historical_support_actionability_label"],
            "Historical context still contributes",
        )
        self.assertEqual(refs_by_id["claim_3"]["claim_actionability_label"], "No active governed support")
        self.assertEqual(refs_by_id["claim_3"]["claim_active_support_actionability_label"], "No current active support")
        self.assertEqual(summary["claims_action_ready_from_active_support_count"], 0)
        self.assertEqual(summary["claims_with_active_but_limited_actionability_count"], 1)
        self.assertEqual(summary["claims_with_mixed_current_historical_actionability_count"], 0)
        self.assertEqual(summary["claims_with_contested_current_support_count"], 1)
        self.assertEqual(summary["claims_with_contradiction_limited_reuse_count"], 1)
        self.assertEqual(summary["claims_with_no_active_governed_support_actionability_count"], 1)
        self.assertIn("active support that remains limited", summary["claim_actionability_basis_summary_text"].lower())
        self.assertIn("no active governed support at all", summary["claim_actionability_basis_summary_text"].lower())


if __name__ == "__main__":
    unittest.main()
