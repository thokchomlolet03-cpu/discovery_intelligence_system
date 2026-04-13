import unittest

from system.contracts import (
    validate_comparison_anchors,
    validate_belief_state_record,
    validate_belief_state_summary,
    validate_belief_update_record,
    validate_candidate_score_semantics,
    ContractValidationError,
    validate_claim_reference,
    validate_claim_record,
    validate_claims_summary,
    validate_decision_artifact,
    validate_experiment_result_record,
    validate_experiment_request_record,
    validate_label_builder_config,
    validate_predictive_evaluation_contract,
    validate_review_event_record,
    validate_run_contract,
    validate_scientific_decision_summary,
    validate_session_identity,
    validate_target_definition,
    validate_governed_review_record,
    validate_governance_inbox,
    validate_governance_inbox_item,
    validate_governance_inbox_summary,
)


def canonical_decision_artifact() -> dict:
    return {
        "session_id": "session_1",
        "iteration": 1,
        "generated_at": "2026-03-25T12:00:00+00:00",
        "summary": {
            "top_k": 1,
            "candidate_count": 1,
            "risk_counts": {"medium": 1},
            "top_experiment_value": 0.64,
        },
        "top_experiments": [
            {
                "session_id": "session_1",
                "rank": 1,
                "candidate_id": "cand_1",
                "smiles": "CCO",
                "canonical_smiles": "CCO",
                "confidence": 0.74,
                "uncertainty": 0.26,
                "novelty": 0.48,
                "acquisition_score": 0.62,
                "experiment_value": 0.64,
                "priority_score": 0.66,
                "bucket": "exploit",
                "risk": "medium",
                "status": "suggested",
                "explanation": ["Balanced scores make this a reasonable candidate for expert review."],
                "score_breakdown": [
                    {
                        "key": "confidence",
                        "label": "Confidence",
                        "raw_value": 0.74,
                        "weight": 0.30,
                        "weight_percent": 30.0,
                        "contribution": 0.222,
                    }
                ],
                "rationale": {
                    "summary": "This candidate is being prioritized mainly because confidence is carrying the shortlist position.",
                    "why_now": "Confidence is the largest contributor to the current priority score.",
                    "trust_label": "Mixed trust",
                    "trust_summary": "The shortlist is useful for prioritization, but still needs scientist review before becoming a bench commitment.",
                    "recommended_action": "Keep this in expert review before moving it into the next testing round.",
                    "primary_driver": "confidence",
                    "session_context": ["Priority score ranks #1 out of 1 scored candidates in this run."],
                    "strengths": ["Confidence is relatively strong at 0.740."],
                    "cautions": ["No uploaded observed value is available for direct cross-checking in this session."],
                    "evidence_lines": ["This candidate is being prioritized mainly because confidence is carrying the shortlist position."],
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
            }
        ],
    }


class ContractValidationTest(unittest.TestCase):
    def test_valid_decision_artifact_passes_schema_validation(self):
        validated = validate_decision_artifact(canonical_decision_artifact())

        self.assertEqual(validated["session_id"], "session_1")
        self.assertEqual(validated["top_experiments"][0]["candidate_id"], "cand_1")
        self.assertEqual(validated["top_experiments"][0]["bucket"], "exploit")
        self.assertEqual(validated["top_experiments"][0]["rationale"]["primary_driver"], "confidence")
        self.assertTrue(validated["top_experiments"][0]["rationale"]["session_context"])

    def test_malformed_decision_artifact_fails_schema_validation(self):
        invalid = canonical_decision_artifact()
        invalid["top_experiments"][0].pop("bucket")

        with self.assertRaises(ContractValidationError):
            validate_decision_artifact(invalid)

    def test_review_record_validates_correctly(self):
        review = validate_review_event_record(
            {
                "session_id": "session_1",
                "candidate_id": "cand_1",
                "smiles": "CCO",
                "action": "approve",
                "previous_status": "suggested",
                "status": "approved",
                "note": "Looks reasonable",
                "timestamp": "2026-03-25T12:00:00+00:00",
                "reviewed_at": "2026-03-25T12:00:00+00:00",
                "actor": "qa",
                "reviewer": "qa",
                "metadata": {"origin": "unit_test"},
            }
        )

        self.assertEqual(review["status"], "approved")
        self.assertEqual(review["previous_status"], "suggested")
        self.assertEqual(review["reviewer"], "qa")

    def test_governed_review_record_validates_manual_review_fields(self):
        review = validate_governed_review_record(
            {
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "subject_type": "belief_state",
                "subject_id": "belief::target_1",
                "review_origin_label": "manual",
                "manual_action_label": "blocked_by_reviewer",
                "reviewer_label": "Owner",
                "review_status_label": "Reviewed and blocked",
                "review_reason_label": "Contradiction-heavy current posture",
                "review_reason_summary": "Owner manually blocked broader carryover after reviewing contradiction-heavy current posture.",
                "decision_summary": "Belief-state broader carryover is manually blocked under bounded human review.",
                "recorded_at": "2026-04-10T12:00:00+00:00",
                "recorded_by": "Owner",
            }
        )

        self.assertEqual(review["review_origin_label"], "manual")
        self.assertEqual(review["manual_action_label"], "blocked_by_reviewer")
        self.assertEqual(review["reviewer_label"], "Owner")

    def test_candidate_score_semantics_contract_validates_bounded_score_layers(self):
        semantics = validate_candidate_score_semantics(
            {
                "raw_predictive_signal": 0.72,
                "raw_predictive_signal_label": "Confidence",
                "heuristic_policy_score": 0.66,
                "heuristic_adjustment_delta": -0.06,
                "raw_signal_weight": 0.62,
                "heuristic_weight": 0.38,
                "blended_priority_score": 0.698,
                "representation_support_factor": 0.93,
                "representation_adjustment": -0.046,
                "final_priority_score": 0.614,
                "governance_effect_summary": "Governance is applied after candidate scoring.",
                "heuristic_summary": "Heuristic shortlist policy is only moderately adjusting the raw predictive signal.",
                "representation_summary": "Representation support is mildly reduced because the candidate is near the edge of current chemistry coverage.",
                "summary": "Raw predictive signal is confidence 0.720. Heuristic shortlist policy moves that to 0.660, and representation support adjusts the final priority to 0.614.",
                "failure_modes": ["representation_edge_of_domain"],
            }
        )

        self.assertEqual(semantics["raw_predictive_signal_label"], "Confidence")
        self.assertAlmostEqual(semantics["representation_support_factor"], 0.93)
        self.assertAlmostEqual(semantics["raw_signal_weight"], 0.62)

    def test_predictive_evaluation_contract_validates_reusable_evaluation_foundation_fields(self):
        contract = validate_predictive_evaluation_contract(
            {
                "evaluation_ready": True,
                "evaluation_summary": "Offline ranking evaluation now records candidate-level separation and reusable comparison cohorts.",
                "benchmark_summary": "2 benchmark candidate configuration(s) were saved for model selection.",
                "ranking_metric_summary": "Saved shortlist rank alignment is Spearman 0.410.",
                "candidate_separation_summary": "Candidate separation is usable but still bounded.",
                "ranking_stability_summary": "Top-of-shortlist stability is bounded.",
                "closeness_band_summary": "The shortlist contains a noticeable weak-separation band where nearby candidates are difficult to distinguish confidently.",
                "top_k_quality_summary": "Top-k quality is usable but still bounded.",
                "heuristic_influence_summary": "Heuristic shortlist policy is still doing substantial ranking work relative to the raw predictive signal.",
                "sensitivity_summary": "Some candidates are still being downweighted by thin representation support.",
                "calibration_awareness_summary": "Confidence should still be read as signal-relative rather than calibrated certainty.",
                "calibration_band_summary": "Higher raw-signal bands do not yet map cleanly to stronger internal shortlist reliability.",
                "comparison_cohort_summary": "Comparison cohort for this run is bounded by regression ranking, session trained, extra trees, and rdkit descriptors 4 plus morgan fp 2048.",
                "cohort_diagnostic_summary": "A reusable signal-led cohort is now available for later version comparison.",
                "evaluation_subset_summary": "3 reusable evaluation subsets are now recorded: Top shortlist, Signal-led cohort, Representation-supported cohort.",
                "session_variation_summary": "Cross-session comparison is possible, but ranking reliability across session variation remains only partly established.",
                "cross_session_comparison_summary": "Cross-session evaluation is anchored by pIC50, regression ranking, prioritize experiments, regression, balanced, and session trained.",
                "version_comparison_summary": "Offline model comparison selected extra trees ahead of random forest for this run.",
                "representation_support_summary": "Representation support still limits part of the shortlist, but most candidates remain within stronger chemistry coverage.",
                "representation_evaluation_summary": "Representation-aware evaluation suggests stronger chemistry coverage improves ranking quality in this run.",
                "representation_condition_summary": "Representation-conditioned evaluation suggests stronger-covered chemistry regions are more reliable in this run.",
                "cross_run_comparison_summary": "Cross-run comparison remains bounded by saved target, training-scope, and feature-contract anchors.",
                "engine_strength_summary": "Engine strengths are becoming more reusable: signal-led cohorts are now reusable across runs.",
                "engine_weakness_summary": "Engine weaknesses remain visible: representation-limited cohorts still degrade ranking quality.",
                "tracked_metrics": ["holdout_rmse", "holdout_mae"],
                "offline_ranking_evaluation": {
                    "schema_version": "offline_ranking_evaluation.v3",
                    "comparison_cohorts": [],
                    "evaluation_subsets": [],
                },
            }
        )

        self.assertEqual(contract["schema_version"], "predictive_evaluation_contract.v3")
        self.assertIn("reusable evaluation subsets", contract["evaluation_subset_summary"].lower())
        self.assertIn("cross-session evaluation", contract["cross_session_comparison_summary"].lower())
        self.assertIn("representation-conditioned evaluation", contract["representation_condition_summary"].lower())

    def test_governance_inbox_contracts_validate_bounded_workflow_payloads(self):
        item = validate_governance_inbox_item(
            {
                "item_id": "belief_state:belief::target_1",
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "session_label": "session_1",
                "source_name": "upload.csv",
                "subject_type": "belief_state",
                "subject_id": "belief::target_1",
                "layer_label": "Belief-state",
                "priority_rank": 1,
                "priority_label": "Immediate attention",
                "attention_label": "Needs review",
                "attention_summary": "Belief-state needs attention because derived posture suggests reviewed and deferred, but the current manual posture is reviewed and blocked.",
                "effective_review_status_label": "Reviewed and blocked",
                "effective_review_status_summary": "Belief-state broader carryover is blocked under the current effective reviewed posture.",
                "effective_review_origin_label": "manual",
                "effective_review_origin_summary": "Current effective posture is explicitly controlled by explicit human review.",
                "derived_review_status_label": "Reviewed and deferred",
                "manual_review_status_label": "Reviewed and blocked",
                "manual_review_action_label": "blocked_by_reviewer",
                "manual_review_reviewer_label": "Owner",
                "manual_review_note": "Blocked until provenance is stronger.",
                "manual_review_note_summary": "Blocked until provenance is stronger.",
                "manual_review_reopen_revise_summary": "This layer has reopen/revise history.",
                "reviewer_attribution_summary": "Manual review currently governs this layer through Owner.",
                "trust_tier_label": "Governed-trusted evidence",
                "provenance_confidence_label": "Strong provenance",
                "source_class_label": "Internal governed experimental source",
                "local_usefulness_summary": "Locally useful belief-state posture remains available.",
                "broader_carryover_summary": "Broader carryover is blocked at belief-state level.",
                "future_influence_summary": "Future broader influence remains bounded until stronger review support exists.",
                "contradiction_context_summary": "Contradiction-heavy current posture is limiting broader carryover.",
                "carryover_guardrail_summary": "Weak multiplicity does not simulate stronger broader carryover.",
                "carryover_effect_summary": "Broader carryover remains blocked until review changes.",
                "consistency_summary": "Manual override remains visible while derived posture stays inspectable.",
                "promotion_gate_status_label": "Promotable under bounded governed rules",
                "promotion_block_reason_label": "Contradiction-heavy current posture",
                "review_record_count": 3,
                "manual_review_record_count": 2,
                "related_session_count": 1,
                "manual_mismatch_flag": True,
                "reason_tags": ["manual_governance", "manual_vs_derived_mismatch"],
                "detail_url": "/governance?session_id=session_1&item_id=belief_state:belief::target_1",
                "discovery_url": "/discovery?session_id=session_1",
                "dashboard_url": "/dashboard?session_id=session_1",
            }
        )
        summary = validate_governance_inbox_summary(
            {
                "generated_at": "2026-04-10T12:00:00+00:00",
                "item_count": 1,
                "immediate_attention_count": 1,
                "review_soon_count": 0,
                "watch_list_count": 0,
                "manual_override_count": 1,
                "manual_mismatch_count": 1,
                "blocked_or_quarantined_count": 1,
                "session_family_count": 0,
                "summary_text": "1 governance inbox item; 1 immediate, 0 review soon, 0 watch list.",
            }
        )
        inbox = validate_governance_inbox(
            {
                "generated_at": "2026-04-10T12:00:00+00:00",
                "summary": summary,
                "items": [item],
                "groups": {"immediate_attention": [item], "review_soon": [], "watch_list": []},
            }
        )

        self.assertEqual(item["effective_review_origin_label"], "manual")
        self.assertIn("blocked until provenance is stronger", item["manual_review_note_summary"].lower())
        self.assertEqual(summary["manual_mismatch_count"], 1)
        self.assertEqual(inbox["items"][0]["item_id"], "belief_state:belief::target_1")

    def test_claim_record_validates_bounded_recommendation_assertion(self):
        claim = validate_claim_record(
            {
                "claim_id": "claim_1",
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "candidate_id": "cand_1",
                "candidate_reference": {"candidate_label": "cand_1 (CCO)", "smiles": "CCO", "rank": 1},
                "target_definition_snapshot": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                },
                "claim_type": "recommendation_assertion",
                "claim_text": "Under the current session evidence, cand_1 (CCO) is a plausible follow-up candidate to test for higher pIC50.",
                "bounded_scope": "This proposed claim is scoped to the current session and is not experimental confirmation or causal proof.",
                "support_level": "moderate",
                "evidence_basis_summary": "Modeling uses Observed experimental values. Ranking uses Model predictions.",
                "source_recommendation_rank": 1,
                "status": "proposed",
                "created_at": "2026-04-02T10:00:00+00:00",
                "updated_at": "2026-04-02T10:00:00+00:00",
                "created_by": "system",
            }
        )

        self.assertEqual(claim["claim_type"], "recommendation_assertion")
        self.assertEqual(claim["status"], "proposed")
        self.assertEqual(claim["support_level"], "moderate")

    def test_claim_reference_and_summary_validate_claim_level_chronology(self):
        claim_ref = validate_claim_reference(
            {
                "claim_id": "claim_1",
                "candidate_id": "cand_1",
                "candidate_label": "cand_1 (CCO)",
                "claim_type": "recommendation_assertion",
                "claim_text": "Under the current session evidence, cand_1 (CCO) is a plausible follow-up candidate to test for higher pIC50.",
                "support_level": "moderate",
                "status": "proposed",
                "source_recommendation_rank": 1,
                "claim_support_role_label": "Active governed support",
                "current_support_count": 1,
                "historical_support_count": 1,
                "rejected_support_count": 0,
                "claim_chronology_summary_text": "This claim currently has 1 active governed support change and keeps 1 superseded historical record visible for context.",
                "claim_support_basis_mix_label": "Grounded mostly in observed labels",
                "claim_support_basis_mix_summary": "This claim's current governed support is grounded mostly in observed labels (1) and remains bounded rather than final.",
                "claim_observed_label_support_count": 1,
                "claim_numeric_rule_based_support_count": 0,
                "claim_unresolved_basis_count": 0,
                "claim_weak_basis_count": 0,
                "claim_support_quality_label": "Decision-useful current active support",
                "claim_support_quality_summary": "cand_1 (CCO) currently has active support that is decision-useful enough for bounded follow-up, while still remaining bounded rather than final.",
                "claim_governed_support_posture_label": "Current support governs present posture",
                "claim_governed_support_posture_summary": "cand_1 (CCO) currently has accepted support that governs present posture for bounded follow-up.",
                "claim_support_coherence_label": "Coherent current support",
                "claim_support_coherence_summary": "cand_1 (CCO): current support is coherent enough to help govern present posture under the available evidence.",
                "claim_support_reuse_label": "Strongly reusable governed support",
                "claim_support_reuse_summary": "cand_1 (CCO): current support is the cleanest basis for future bounded governed reuse because it is coherent and posture-governing.",
                "claim_broader_reuse_label": "Broader reuse is strong under coherent current support",
                "claim_broader_reuse_summary": "This claim can contribute to stronger broader reuse because current support is coherent and related-claim continuity is posture-governing.",
                "claim_future_reuse_candidacy_label": "Stronger future governed reuse candidacy",
                "claim_future_reuse_candidacy_summary": "This claim now looks like a stronger later candidate for broader governed reuse if the bounded current posture holds.",
                "claim_continuity_cluster_posture_label": "Promotion-candidate continuity cluster",
                "claim_continuity_cluster_posture_summary": "This claim sits inside a coherent continuity cluster that is strong enough to be treated as a later broader governed promotion candidate.",
                "claim_promotion_candidate_posture_label": "Stronger broader governed reuse candidate",
                "claim_promotion_candidate_posture_summary": "This claim now looks like a stronger broader governed reuse candidate if the current continuity remains coherent.",
                "claim_promotion_stability_label": "Stable enough for governed promotion review",
                "claim_promotion_stability_summary": "This claim-family continuity is stable enough for governed promotion review.",
                "claim_promotion_gate_status_label": "Promotable under bounded governed rules",
                "claim_promotion_gate_status_summary": "This claim-family continuity is promotable under bounded governed rules.",
                "claim_promotion_block_reason_label": "No material promotion block recorded",
                "claim_promotion_block_reason_summary": "No material promotion block is currently recorded for this claim-family continuity picture.",
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
                "claim_actionability_basis_summary": "cand_1 (CCO)'s present actionability is driven by 1 active governed support change, while 1 superseded historical record remains context only.",
                "claim_active_support_actionability_label": "Current active support is decision-useful",
                "claim_historical_support_actionability_label": "Historical context remains secondary",
                "claim_historical_interest_only_flag": False,
                "claim_next_step_label": "Follow-up experiment is reasonable now",
                "claim_next_step_summary": "A bounded follow-up experiment is reasonable now, while keeping the claim explicitly separate from validated truth.",
                "created_at": "2026-04-02T10:00:00+00:00",
            }
        )
        claims_summary = validate_claims_summary(
            {
                "claim_count": 2,
                "proposed_count": 2,
                "accepted_count": 0,
                "rejected_count": 0,
                "superseded_count": 0,
                "claims_with_active_support_count": 1,
                "claims_with_historical_support_only_count": 1,
                "claims_with_rejected_support_only_count": 0,
                "claims_with_no_governed_support_count": 0,
                "continuity_aligned_claim_count": 1,
                "new_claim_context_count": 1,
                "weak_prior_alignment_count": 0,
                "no_prior_claim_context_count": 0,
                "claims_with_active_governed_continuity_count": 1,
                "claims_with_tentative_active_continuity_count": 0,
                "claims_with_historical_continuity_only_count": 0,
                "claims_with_sparse_prior_context_count": 1,
                "claims_with_no_useful_prior_context_count": 0,
                "claims_mostly_observed_label_grounded_count": 1,
                "claims_with_numeric_rule_based_support_count": 0,
                "claims_with_weak_basis_support_count": 0,
                "claims_with_mixed_support_basis_count": 1,
                "claims_with_decision_useful_active_support_count": 1,
                "claims_with_limited_active_support_quality_count": 0,
                "claims_with_context_limited_active_support_count": 0,
                "claims_with_weak_or_unresolved_active_support_count": 0,
                "claims_with_posture_governing_support_count": 1,
                "claims_with_tentative_current_support_count": 0,
                "claims_with_accepted_limited_support_count": 0,
                "claims_with_historical_non_governing_support_count": 0,
                "claims_with_contested_current_support_count": 0,
                "claims_with_degraded_current_posture_count": 0,
                "claims_with_historical_stronger_than_current_count": 0,
                "claims_with_contradiction_limited_reuse_count": 0,
                "claims_with_weakly_reusable_support_count": 0,
                "claims_action_ready_follow_up_count": 1,
                "claims_promising_but_need_stronger_evidence_count": 0,
                "claims_need_clarifying_experiment_count": 1,
                "claims_do_not_prioritize_yet_count": 0,
                "claims_with_insufficient_governed_basis_count": 0,
                "claims_action_ready_from_active_support_count": 1,
                "claims_with_active_but_limited_actionability_count": 0,
                "claims_historically_interesting_count": 0,
                "claims_with_mixed_current_historical_actionability_count": 0,
                "claims_with_no_active_governed_support_actionability_count": 0,
                "summary_text": "2 proposed claims were derived from the current shortlist. Claims remain bounded recommendation-derived assertions, not experimental confirmation.",
                "chronology_summary_text": "Claim-level support chronology remains bounded: 1 claim with active governed support, 1 historical-only.",
                "claim_support_basis_summary_text": "Claim support-basis composition remains bounded: 1 grounded mostly in observed labels, 1 mixed-basis.",
                "claim_actionability_summary_text": "Claim actionability remains bounded: 1 action-ready from current active support, 1 needing clarifying experiment.",
                "claim_actionability_basis_summary_text": "Claim actionability basis remains bounded: 1 action-ready from current active support.",
                "read_across_summary_text": "Claim read-across remains bounded: 1 continuity-aligned, 1 new-context.",
                "broader_reuse_label": "Broader reuse is strong under coherent current support",
                "broader_reuse_summary_text": "Broader claim reuse is strongest where current posture is coherent.",
                "broader_continuity_label": "Coherent broader continuity cluster",
                "broader_continuity_summary_text": "The broader claim continuity cluster is coherent.",
                "future_reuse_candidacy_label": "Stronger future governed reuse candidacy",
                "future_reuse_candidacy_summary_text": "1 claim now looks like a stronger later candidate for broader governed reuse if the bounded current posture holds.",
                "continuity_cluster_posture_label": "Promotion-candidate continuity cluster",
                "continuity_cluster_posture_summary_text": "Claim-family continuity is coherent enough to be treated as a stronger broader governed promotion candidate later.",
                "promotion_candidate_posture_label": "Stronger broader governed reuse candidate",
                "promotion_candidate_posture_summary_text": "Claim-family promotion posture is strong enough to mark a later broader governed reuse candidate without implying final truth.",
                "promotion_stability_label": "Stable enough for governed promotion review",
                "promotion_stability_summary_text": "Claim-family continuity is stable enough for governed promotion review.",
                "promotion_gate_status_label": "Promotable under bounded governed rules",
                "promotion_gate_status_summary_text": "Claim-family continuity is promotable under bounded governed rules.",
                "promotion_block_reason_label": "No material promotion block recorded",
                "promotion_block_reason_summary_text": "No material promotion block is currently recorded for the claim-family continuity picture.",
                "top_claims": [claim_ref],
            }
        )

        self.assertEqual(claim_ref["claim_support_role_label"], "Active governed support")
        self.assertEqual(claim_ref["historical_support_count"], 1)
        self.assertEqual(claim_ref["claim_support_basis_mix_label"], "Grounded mostly in observed labels")
        self.assertEqual(claim_ref["claim_support_quality_label"], "Decision-useful current active support")
        self.assertEqual(claim_ref["claim_actionability_label"], "Action-ready from current active support")
        self.assertEqual(claim_ref["claim_actionability_basis_label"], "Current active support basis")
        self.assertEqual(claim_ref["claim_active_support_actionability_label"], "Current active support is decision-useful")
        self.assertEqual(claim_ref["claim_historical_support_actionability_label"], "Historical context remains secondary")
        self.assertEqual(claim_ref["claim_next_step_label"], "Follow-up experiment is reasonable now")
        self.assertEqual(claim_ref["claim_read_across_label"], "Continuity-aligned claim")
        self.assertEqual(claim_ref["claim_prior_support_quality_label"], "Posture-governing continuity")
        self.assertEqual(claim_ref["claim_governed_support_posture_label"], "Current support governs present posture")
        self.assertEqual(claim_ref["claim_support_coherence_label"], "Coherent current support")
        self.assertEqual(claim_ref["claim_support_reuse_label"], "Strongly reusable governed support")
        self.assertEqual(claim_ref["claim_broader_reuse_label"], "Broader reuse is strong under coherent current support")
        self.assertEqual(claim_ref["claim_future_reuse_candidacy_label"], "Stronger future governed reuse candidacy")
        self.assertEqual(claim_ref["claim_continuity_cluster_posture_label"], "Promotion-candidate continuity cluster")
        self.assertEqual(claim_ref["claim_promotion_candidate_posture_label"], "Stronger broader governed reuse candidate")
        self.assertEqual(claim_ref["claim_promotion_stability_label"], "Stable enough for governed promotion review")
        self.assertEqual(claim_ref["claim_promotion_gate_status_label"], "Promotable under bounded governed rules")
        self.assertEqual(claim_ref["claim_promotion_block_reason_label"], "No material promotion block recorded")
        self.assertEqual(claims_summary["claims_with_active_support_count"], 1)
        self.assertEqual(claims_summary["continuity_aligned_claim_count"], 1)
        self.assertEqual(claims_summary["claims_with_active_governed_continuity_count"], 1)
        self.assertEqual(claims_summary["claims_with_posture_governing_support_count"], 1)
        self.assertEqual(claims_summary["claims_with_contested_current_support_count"], 0)
        self.assertEqual(claims_summary["claims_mostly_observed_label_grounded_count"], 1)
        self.assertEqual(claims_summary["claims_with_decision_useful_active_support_count"], 1)
        self.assertEqual(claims_summary["claims_action_ready_follow_up_count"], 1)
        self.assertEqual(claims_summary["claims_action_ready_from_active_support_count"], 1)
        self.assertEqual(claims_summary["claims_with_mixed_current_historical_actionability_count"], 0)
        self.assertIn("claim read-across remains bounded", claims_summary["read_across_summary_text"].lower())
        self.assertEqual(claims_summary["broader_reuse_label"], "Broader reuse is strong under coherent current support")
        self.assertEqual(claims_summary["broader_continuity_label"], "Coherent broader continuity cluster")
        self.assertEqual(claims_summary["future_reuse_candidacy_label"], "Stronger future governed reuse candidacy")
        self.assertEqual(claims_summary["continuity_cluster_posture_label"], "Promotion-candidate continuity cluster")
        self.assertEqual(claims_summary["promotion_candidate_posture_label"], "Stronger broader governed reuse candidate")
        self.assertEqual(claims_summary["promotion_stability_label"], "Stable enough for governed promotion review")
        self.assertEqual(claims_summary["promotion_gate_status_label"], "Promotable under bounded governed rules")
        self.assertEqual(claims_summary["promotion_block_reason_label"], "No material promotion block recorded")
        self.assertIn("claim-level support chronology remains bounded", claims_summary["chronology_summary_text"].lower())
        self.assertIn("claim support-basis composition remains bounded", claims_summary["claim_support_basis_summary_text"].lower())
        self.assertIn("claim actionability remains bounded", claims_summary["claim_actionability_summary_text"].lower())
        self.assertIn("claim actionability basis remains bounded", claims_summary["claim_actionability_basis_summary_text"].lower())

    def test_experiment_request_record_validates_recommended_experiment(self):
        request = validate_experiment_request_record(
            {
                "experiment_request_id": "expreq_1",
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "claim_id": "claim_1",
                "candidate_id": "cand_1",
                "candidate_reference": {"candidate_label": "cand_1 (CCO)", "smiles": "CCO", "rank": 1},
                "target_definition_snapshot": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                },
                "requested_measurement": "pIC50",
                "requested_direction": "measure for higher values",
                "rationale_summary": "This proposed experiment request is derived from the current claim. It is not scheduled lab work.",
                "priority_tier": "high",
                "status": "proposed",
                "requested_at": "2026-04-02T12:00:00+00:00",
                "requested_by": "system",
            }
        )

        self.assertEqual(request["requested_measurement"], "pIC50")
        self.assertEqual(request["priority_tier"], "high")
        self.assertEqual(request["status"], "proposed")

    def test_experiment_result_record_validates_observed_outcome(self):
        result = validate_experiment_result_record(
            {
                "experiment_result_id": "expres_1",
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "source_experiment_request_id": "expreq_1",
                "source_claim_id": "claim_1",
                "candidate_id": "cand_1",
                "candidate_reference": {"candidate_label": "cand_1 (CCO)", "smiles": "CCO", "rank": 1},
                "target_definition_snapshot": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                },
                "observed_value": 6.4,
                "observed_label": "",
                "measurement_unit": "log units",
                "assay_context": "screen_a repeat 1",
                "result_quality": "screening",
                "result_source": "manual_entry",
                "ingested_at": "2026-04-02T14:00:00+00:00",
                "ingested_by": "system",
                "notes": "Observed outcome recorded.",
            }
        )

        self.assertEqual(result["observed_value"], 6.4)
        self.assertEqual(result["result_quality"], "screening")
        self.assertEqual(result["result_source"], "manual_entry")

    def test_belief_state_and_scientific_decision_summaries_validate_multilayer_review_fields(self):
        belief_state_summary = validate_belief_state_summary(
            {
                "summary_text": "Current belief state remains bounded.",
                "support_distribution_summary": "Supported 1, weakened 0, unresolved 0.",
                "governance_scope_summary": "Current picture includes 1 proposed update.",
                "chronology_summary_text": "Current support picture relies on 1 active support change.",
                "active_claim_count": 1,
                "supported_claim_count": 1,
                "support_quality_label": "Decision-useful active support",
                "governed_support_posture_label": "Current support remains tentative",
                "support_coherence_label": "Mixed active support",
                "support_reuse_label": "Weakly reusable current support",
                "broader_target_reuse_label": "Support is locally meaningful, not broadly governing",
                "broader_target_continuity_label": "No broader continuity cluster",
                "future_reuse_candidacy_label": "Local-only future reuse context",
                "continuity_cluster_posture_label": "Local-only continuity cluster",
                "promotion_gate_status_label": "Not a governed promotion candidate",
                "promotion_block_reason_label": "Local-only meaning",
                "trust_tier_label": "Local-only evidence",
                "provenance_confidence_label": "Unknown provenance",
                "governed_review_status_label": "Not reviewed for broader influence",
                "governed_review_reason_label": "Local-only by default",
                "governed_review_record_count": 1,
                "governed_review_history_summary": "This belief-state posture has 1 governed review record; latest posture is not reviewed for broader influence under local-only evidence.",
                "derived_governed_review_status_label": "Not reviewed for broader influence",
                "derived_governed_review_status_summary": "This belief-state posture remains local-only by default until broader carryover is earned.",
                "manual_governed_review_status_label": "Reviewed and deferred",
                "manual_governed_review_status_summary": "Belief-state broader carryover remains manually deferred under bounded review.",
                "manual_governed_review_reason_label": "Stronger trust still needed",
                "manual_governed_review_reason_summary": "A reviewer deferred broader carryover pending stronger trust and continuity.",
                "manual_governed_review_record_count": 1,
                "manual_governed_review_history_summary": "This belief-state posture has 1 manual governed review record; current manual posture is reviewed and deferred by Owner.",
                "manual_governed_review_action_label": "Deferred by reviewer",
                "manual_governed_review_reviewer_label": "Owner",
                "effective_governed_review_origin_label": "manual",
                "effective_governed_review_origin_summary": "Current effective governance posture is controlled by explicit human review rather than by derived posture alone.",
                "promotion_audit_summary": "Latest promotion outcome is local only.",
                "continuity_cluster_review_status_label": "Not reviewed for broader influence",
                "continuity_cluster_review_reason_label": "Local-only by default",
                "continuity_cluster_review_record_count": 1,
                "continuity_cluster_review_history_summary": "This continuity cluster has 1 governed review record.",
                "continuity_cluster_derived_review_status_label": "Not reviewed for broader influence",
                "continuity_cluster_manual_review_status_label": "Reviewed and blocked",
                "continuity_cluster_manual_review_action_label": "Blocked by reviewer",
                "continuity_cluster_manual_review_reviewer_label": "Owner",
                "continuity_cluster_effective_review_origin_label": "manual",
                "continuity_cluster_effective_review_origin_summary": "Current effective governance posture is controlled by explicit human review rather than by derived posture alone.",
                "continuity_cluster_promotion_audit_summary": "Latest promotion outcome is local only.",
                "carryover_guardrail_summary": "Weak multiplicity does not create stronger broader carryover.",
            }
        )
        decision_summary = validate_scientific_decision_summary(
            {
                "decision_status_label": "Current active basis remains tentative",
                "decision_status_summary": "The session remains bounded and review-oriented.",
                "broader_governed_reuse_label": "Support is locally meaningful, not broadly governing",
                "broader_continuity_label": "No broader continuity cluster",
                "future_reuse_candidacy_label": "Local-only future reuse context",
                "continuity_cluster_posture_label": "Local-only continuity cluster",
                "promotion_gate_status_label": "Not a governed promotion candidate",
                "promotion_block_reason_label": "Local-only meaning",
                "trust_tier_label": "Local-only evidence",
                "provenance_confidence_label": "Unknown provenance",
                "governed_review_status_label": "Not reviewed for broader influence",
                "governed_review_reason_label": "Local-only by default",
                "session_family_review_status_label": "Not reviewed for broader influence",
                "session_family_review_reason_label": "Local-only by default",
                "session_family_review_record_count": 1,
                "session_family_review_history_summary": "This session-family carryover picture has 1 governed review record.",
                "derived_governed_review_status_label": "Not reviewed for broader influence",
                "manual_governed_review_status_label": "Reviewed and blocked",
                "manual_governed_review_status_summary": "Session-family carryover is manually blocked under bounded review.",
                "manual_governed_review_reason_label": "Contradiction-heavy current posture",
                "manual_governed_review_reason_summary": "A reviewer blocked broader carryover because contradiction-heavy history makes it unsafe to travel further.",
                "manual_governed_review_record_count": 1,
                "manual_governed_review_history_summary": "This session-family carryover picture has 1 manual governed review record; current manual posture is reviewed and blocked by Owner.",
                "manual_governed_review_action_label": "Blocked by reviewer",
                "manual_governed_review_reviewer_label": "Owner",
                "effective_governed_review_origin_label": "manual",
                "effective_governed_review_origin_summary": "Current effective governance posture is controlled by explicit human review rather than by derived posture alone.",
                "session_family_derived_review_status_label": "Not reviewed for broader influence",
                "session_family_manual_review_status_label": "Reviewed and blocked",
                "session_family_manual_review_status_summary": "Session-family carryover is manually blocked under bounded review.",
                "session_family_manual_review_reason_label": "Contradiction-heavy current posture",
                "session_family_manual_review_reason_summary": "A reviewer blocked broader carryover because contradiction-heavy history makes it unsafe to travel further.",
                "session_family_manual_review_record_count": 1,
                "session_family_manual_review_history_summary": "This session-family carryover picture has 1 manual governed review record; current manual posture is reviewed and blocked by Owner.",
                "session_family_manual_review_action_label": "Blocked by reviewer",
                "session_family_manual_review_reviewer_label": "Owner",
                "session_family_effective_review_origin_label": "manual",
                "session_family_effective_review_origin_summary": "Current effective governance posture is controlled by explicit human review rather than by derived posture alone.",
                "session_family_promotion_audit_summary": "Latest promotion outcome is local only.",
                "carryover_guardrail_summary": "Weak local multiplicity does not simulate approved session-family carryover.",
            }
        )

        self.assertEqual(belief_state_summary["governed_review_record_count"], 1)
        self.assertEqual(belief_state_summary["manual_governed_review_action_label"], "Deferred by reviewer")
        self.assertEqual(belief_state_summary["continuity_cluster_review_record_count"], 1)
        self.assertEqual(belief_state_summary["effective_governed_review_origin_label"], "manual")
        self.assertEqual(decision_summary["session_family_review_record_count"], 1)
        self.assertEqual(decision_summary["session_family_manual_review_action_label"], "Blocked by reviewer")
        self.assertIn("session-family carryover", decision_summary["session_family_review_history_summary"].lower())

    def test_belief_update_record_validates_bounded_support_change(self):
        belief_update = validate_belief_update_record(
            {
                "belief_update_id": "belief_1",
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "claim_id": "claim_1",
                "experiment_result_id": "expres_1",
                "candidate_id": "cand_1",
                "candidate_label": "cand_1 (CCO)",
                "previous_support_level": "moderate",
                "updated_support_level": "strong",
                "update_direction": "strengthened",
                "update_reason": "This proposed belief update strengthens support in a bounded way only.",
                "support_input_quality_label": "Stronger interpretation basis",
                "support_input_quality_summary": "Result quality and context support a stronger bounded interpretation under the current observed label path.",
                "assay_context_alignment_label": "No specific assay context expected",
                "result_interpretation_basis": "Observed label",
                "numeric_result_basis_label": "",
                "numeric_result_basis_summary": "",
                "numeric_result_resolution_label": "",
                "numeric_result_interpretation_label": "",
                "target_rule_alignment_label": "",
                "support_quality_label": "Decision-useful active support",
                "support_quality_summary": "Active support is grounded in a stronger-basis observed outcome and is decision-useful enough for bounded follow-up.",
                "support_decision_usefulness_label": "Can justify bounded follow-up",
                "governed_support_posture_label": "Current support remains tentative",
                "governed_support_posture_summary": "This support update is active, but it remains proposed and should stay tentative until stronger governed confirmation exists.",
                "contradiction_role_label": "Adds tentative current support",
                "contradiction_role_summary": "This active support update adds current support on paper, but it should stay tentative until the evidence picture is cleaner.",
                "governance_status": "proposed",
                "chronology_label": "Current proposed support change",
                "active_for_belief_state": True,
                "metadata": {
                    "chronology_mix_label": "Current support only",
                    "chronology_summary_text": "This session currently contributes 1 active support change and no historical support records.",
                },
                "created_at": "2026-04-02T15:00:00+00:00",
                "created_by": "scientist",
            }
        )

        self.assertEqual(belief_update["update_direction"], "strengthened")
        self.assertEqual(belief_update["governance_status"], "proposed")
        self.assertEqual(belief_update["updated_support_level"], "strong")
        self.assertEqual(belief_update["chronology_label"], "Current proposed support change")
        self.assertEqual(belief_update["support_input_quality_label"], "Stronger interpretation basis")
        self.assertEqual(belief_update["contradiction_role_label"], "Adds tentative current support")
        self.assertTrue(belief_update["active_for_belief_state"])

    def test_belief_state_record_validates_current_support_picture(self):
        belief_state = validate_belief_state_record(
            {
                "belief_state_id": "beliefstate_1",
                "workspace_id": "workspace_1",
                "target_key": "pic50|regression|maximize|pic50|measurement_dataset",
                "target_definition_snapshot": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "dataset_type": "measurement_dataset",
                    "mapping_confidence": "medium",
                },
                "summary_text": "Current belief state tracks 2 active claims. This is a bounded support summary, not final truth.",
                "active_claim_count": 2,
                "supported_claim_count": 1,
                "weakened_claim_count": 0,
                "unresolved_claim_count": 1,
                "last_updated_at": "2026-04-02T16:00:00+00:00",
                "last_update_source": "latest belief update linked to an observed result",
                "version": 1,
                "support_distribution_summary": "Supported 1, weakened 0, unresolved 1.",
                "governance_scope_summary": "Current picture includes 1 accepted and 1 proposed belief update.",
                "support_basis_mix_label": "Mixed support basis",
                "support_basis_mix_summary": "The current support picture uses a mixed basis: 1 observed-label, 0 numeric-rule-based, 1 unresolved, and 1 weak-basis active support change.",
                "observed_label_support_count": 1,
                "numeric_rule_based_support_count": 0,
                "unresolved_basis_count": 1,
                "weak_basis_count": 1,
                "support_quality_label": "Current support remains active but limited",
                "support_quality_summary": "1 active support change remain present but still limited for stronger follow-up.",
                "governed_support_posture_label": "Accepted support remains limited-weight",
                "governed_support_posture_summary": "1 accepted support change remains too limited or context-limited to govern present posture strongly.",
                "support_coherence_label": "Current posture is degraded",
                "support_coherence_summary": "Current posture is degraded: active support still exists, but weakening evidence or stronger historical context reduces present decision strength.",
                "support_reuse_label": "Reuse with contradiction caution",
                "support_reuse_summary": "Current support should be reused only with contradiction caution because mixed or weakening evidence reduces how cleanly it carries forward.",
                "broader_target_reuse_label": "Broader reuse is historical-only",
                "broader_target_reuse_summary": "Broader target-scoped reuse is mainly historical-only right now.",
                "broader_target_continuity_label": "Historical-heavy broader continuity cluster",
                "broader_target_continuity_summary": "The broader target continuity cluster is historical-heavy.",
                "future_reuse_candidacy_label": "Historical-only future reuse context",
                "future_reuse_candidacy_summary": "Future target-level reuse candidacy is mainly historical-only right now.",
                "continuity_cluster_posture_label": "Historical-heavy continuity cluster",
                "continuity_cluster_posture_summary": "Target-scoped continuity remains mainly historical, so it should stay visible as context rather than a stronger promotion candidate.",
                "promotion_candidate_posture_label": "Historical-only promotion context",
                "promotion_candidate_posture_summary": "Target-scoped continuity is mainly historical context and should not be treated as a stronger broader promotion candidate right now.",
                "promotion_stability_label": "Historical-heavy and not stably current",
                "promotion_stability_summary": "Target-scoped continuity remains historical-heavy rather than stably current.",
                "promotion_gate_status_label": "Candidate but blocked from promotion",
                "promotion_gate_status_summary": "Target-scoped continuity remains blocked from broader promotion under the current bounded rules.",
                "promotion_block_reason_label": "Historical-heavy continuity",
                "promotion_block_reason_summary": "Target-scoped continuity is mainly historical-heavy, so its value is contextual rather than broadly promotable.",
                "decision_useful_active_support_count": 0,
                "active_but_limited_support_count": 1,
                "context_limited_support_count": 0,
                "weak_or_unresolved_support_count": 1,
                "posture_governing_support_count": 0,
                "tentative_current_support_count": 0,
                "accepted_limited_support_count": 1,
                "historical_non_governing_support_count": 1,
                "contradiction_pressure_count": 1,
                "weakly_reusable_support_count": 2,
                "current_support_contested_flag": False,
                "current_posture_degraded_flag": True,
                "historical_support_stronger_than_current_flag": True,
                "belief_state_strength_summary": "The current support picture has some accepted grounding, but it is still limited and should be read cautiously.",
                "belief_state_readiness_summary": "Read-across is partial because some accepted support exists, but the picture remains update-light.",
                "governance_mix_label": "Mixed governance",
                "chronology_summary_text": "Current support picture relies on 2 active claim-linked support changes and keeps 1 superseded plus 0 rejected historical records visible for context.",
                "metadata": {
                    "accepted_update_count": 1,
                    "proposed_update_count": 1,
                    "rejected_update_count": 0,
                    "superseded_update_count": 1,
                },
            }
        )

        self.assertEqual(belief_state["active_claim_count"], 2)
        self.assertEqual(belief_state["supported_claim_count"], 1)
        self.assertEqual(belief_state["version"], 1)
        self.assertEqual(belief_state["governance_mix_label"], "Mixed governance")
        self.assertEqual(belief_state["support_basis_mix_label"], "Mixed support basis")
        self.assertEqual(belief_state["broader_target_reuse_label"], "Broader reuse is historical-only")
        self.assertEqual(belief_state["broader_target_continuity_label"], "Historical-heavy broader continuity cluster")
        self.assertEqual(belief_state["future_reuse_candidacy_label"], "Historical-only future reuse context")
        self.assertEqual(belief_state["continuity_cluster_posture_label"], "Historical-heavy continuity cluster")
        self.assertEqual(belief_state["promotion_candidate_posture_label"], "Historical-only promotion context")
        self.assertEqual(belief_state["promotion_stability_label"], "Historical-heavy and not stably current")
        self.assertEqual(belief_state["promotion_gate_status_label"], "Candidate but blocked from promotion")
        self.assertEqual(belief_state["promotion_block_reason_label"], "Historical-heavy continuity")
        self.assertEqual(belief_state["unresolved_basis_count"], 1)
        self.assertIn("active claim-linked support changes", belief_state["chronology_summary_text"].lower())
        self.assertEqual(belief_state["metadata"]["superseded_update_count"], 1)

    def test_label_builder_config_validates_threshold_rule(self):
        validated = validate_label_builder_config(
            {
                "enabled": True,
                "value_column": "pic50",
                "operator": ">=",
                "threshold": 6.0,
            }
        )

        self.assertTrue(validated["enabled"])
        self.assertEqual(validated["value_column"], "pic50")
        self.assertEqual(validated["threshold"], 6.0)

    def test_target_definition_validates_regression_contract(self):
        validated = validate_target_definition(
            {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "measurement_column": "pic50",
                "measurement_unit": "log10 molar potency scale",
                "scientific_meaning": "Higher predicted values are treated as more favorable for pIC50.",
                "dataset_type": "measurement_dataset",
                "mapping_confidence": "medium",
                "success_definition": "Success means prioritizing molecules expected to achieve higher pIC50 values.",
            }
        )

        self.assertEqual(validated["target_kind"], "regression")
        self.assertEqual(validated["measurement_column"], "pic50")
        self.assertEqual(validated["dataset_type"], "measurement_dataset")

    def test_session_identity_validates_target_aware_contract(self):
        validated = validate_session_identity(
            {
                "session_id": "session_1",
                "source_name": "upload.csv",
                "created_at": "2026-03-25T12:00:00+00:00",
                "workspace_id": "workspace_1",
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
                "session_status": "results_ready",
                "current_job_status": "succeeded",
                "scientific_purpose": "Estimate continuous values for pIC50 and prioritize molecules that look experimentally useful to test.",
                "trust_summary": "Uploaded measurements are available, so the ranking can be cross-checked against observed evidence rather than treated as model truth.",
                "latest_result_summary": "3 saved candidates are available for review.",
            }
        )

        self.assertEqual(validated["modeling_mode"], "regression")
        self.assertEqual(validated["decision_intent"], "prioritize_experiments")
        self.assertEqual(validated["target_definition"]["target_name"], "pIC50")

    def test_run_contract_validates_comparison_ready_metadata(self):
        validated = validate_run_contract(
            {
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
                "candidate_generation_requested": False,
                "candidate_generation_eligible": False,
                "used_candidate_generation": False,
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
                "predictive_task_contract": {
                    "task_label": "Bounded measurement-oriented candidate prioritization",
                    "task_summary": "The current predictive task is local candidate prioritization for what to test next, not universal truth prediction.",
                    "prioritization_target": "Prioritize molecules worth testing next for pIC50 under a continuous-target ranking workflow.",
                    "predictive_score_label": "Priority score",
                    "predictive_score_summary": "Raw predictive signal uses predicted value, normalized ranking compatibility, and prediction dispersion as bounded ordering inputs rather than as outcome truth.",
                    "final_ordering_summary": "Final user-facing ordering starts from priority score and then remains subject to heuristic shortlist policy, trust posture, and broader carryover boundaries.",
                    "governance_interaction_summary": "Trust, review, and carryover posture can still constrain how far a strong-ranked candidate should travel.",
                    "bridge_state_limitations_summary": "This predictive task is explicit enough to inspect, but current shortlist behavior still mixes model signal with bounded heuristic policy.",
                },
                "predictive_representation_summary": {
                    "feature_signature": "rdkit_descriptors_4_plus_morgan_fp_2048",
                    "represented_inputs_summary": "Feature contract currently uses rdkit descriptors 4 plus morgan fp 2048.",
                    "representation_limitations_summary": "The current representation does not explicitly encode richer assay mechanism, protocol nuance, causal structure, or stronger cross-session scientific state.",
                    "missing_structure_summary": "Missing structure still includes deeper assay context, mechanism-level representation, richer provenance-aware scientific state, and explicit independence structure between evidence sources.",
                },
                "predictive_evaluation_contract": {
                    "evaluation_ready": True,
                    "evaluation_summary": "Saved regression evaluation currently centers on holdout rmse, holdout mae, holdout r2 for rf_regression.",
                    "benchmark_summary": "No saved benchmark sweep is available yet.",
                    "ranking_metric_summary": "Saved ranking diagnostics are still limited, so future evaluation work should expand beyond current shortlist-level readouts.",
                    "closeness_band_summary": "No closeness-band diagnostics are available yet.",
                    "calibration_awareness_summary": "Regression ranking compatibility is not a calibrated probability. It is a bounded ordering signal and should be read together with dispersion and representation support.",
                    "comparison_cohort_summary": "Comparison cohort for this run is bounded by regression ranking, session trained, extra trees, and rdkit descriptors 4 plus morgan fp 2048.",
                    "cohort_diagnostic_summary": "A reusable signal-led cohort is now available for later version comparison.",
                    "session_variation_summary": "Cross-session comparison is possible, but ranking reliability across session variation remains only partly established.",
                    "cross_run_comparison_summary": "Cross-run comparison is anchored by regression ranking, session trained, extra trees, and rdkit descriptors 4 plus morgan fp 2048.",
                    "representation_evaluation_summary": "Representation-aware evaluation suggests stronger chemistry coverage improves ranking quality in this run.",
                    "engine_strength_summary": "Engine strengths are becoming more reusable: signal-led cohorts are now reusable across runs.",
                    "engine_weakness_summary": "Engine weaknesses remain visible: representation-limited cohorts still degrade ranking quality.",
                    "tracked_metrics": ["holdout_rmse", "holdout_mae", "holdout_r2"],
                },
            }
        )

        self.assertEqual(validated["modeling_mode"], "regression")
        self.assertEqual(validated["training_scope"], "session_trained")
        self.assertEqual(validated["contract_versions"]["run_contract_version"], "run_contract.v1")
        self.assertEqual(
            validated["predictive_task_contract"]["predictive_score_label"],
            "Priority score",
        )
        self.assertTrue(validated["predictive_evaluation_contract"]["evaluation_ready"])

    def test_comparison_anchors_validate_session_basis(self):
        validated = validate_comparison_anchors(
            {
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
            }
        )

        self.assertEqual(validated["target_kind"], "regression")
        self.assertTrue(validated["comparison_ready"])
        self.assertEqual(validated["scoring_policy_version"], "scoring_policy.v1")


if __name__ == "__main__":
    unittest.main()
