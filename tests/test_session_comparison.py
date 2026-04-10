import unittest

from system.services.session_comparison_service import build_session_comparison_matrix, compare_session_basis


class SessionComparisonServiceTest(unittest.TestCase):
    def test_compare_session_basis_prefers_canonical_scientific_truth_over_legacy_anchor_fragments(self):
        comparison = compare_session_basis(
            focus_session={
                "comparison_anchors": {
                    "target_name": "legacy_target",
                    "target_kind": "classification",
                    "modeling_mode": "binary_classification",
                    "decision_intent": "estimate_labels",
                    "comparison_ready": False,
                },
                "scientific_session_truth": {
                    "comparison_anchors": {
                        "target_name": "pIC50",
                        "target_kind": "regression",
                        "optimization_direction": "maximize",
                        "modeling_mode": "regression",
                        "decision_intent": "prioritize_experiments",
                        "scoring_policy_version": "scoring_policy.v1",
                        "selected_model_name": "rf_regression",
                        "training_scope": "session_trained",
                        "comparison_ready": True,
                    },
                    "evidence_loop": {
                        "active_modeling_evidence": ["Observed experimental values", "Computed chemistry features"],
                        "active_ranking_evidence": ["Retrieved reference chemistry context", "Predicted continuous values"],
                    },
                },
                "status_semantics": {
                    "trustworthy_recommendations": True,
                    "viewable_artifacts": True,
                },
            },
            candidate_session={
                "scientific_session_truth": {
                    "comparison_anchors": {
                        "target_name": "pIC50",
                        "target_kind": "regression",
                        "optimization_direction": "maximize",
                        "modeling_mode": "regression",
                        "decision_intent": "prioritize_experiments",
                        "scoring_policy_version": "scoring_policy.v1",
                        "selected_model_name": "rf_regression",
                        "training_scope": "session_trained",
                        "comparison_ready": True,
                    },
                    "evidence_loop": {
                        "active_modeling_evidence": ["Observed experimental values", "Computed chemistry features"],
                        "active_ranking_evidence": ["Retrieved reference chemistry context", "Predicted continuous values"],
                    },
                },
                "status_semantics": {
                    "trustworthy_recommendations": True,
                    "viewable_artifacts": True,
                },
            },
        )

        self.assertEqual(comparison["status"], "directly_comparable")
        self.assertIn("Same target property: pIC50.", comparison["matches"])
        self.assertEqual(comparison["basis_source_summary"], "Canonical scientific session truth")

    def test_compare_session_basis_marks_direct_match_when_target_mode_and_policy_align(self):
        comparison = compare_session_basis(
            focus_session={
                "comparison_anchors": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "modeling_mode": "regression",
                    "decision_intent": "prioritize_experiments",
                    "scoring_policy_version": "scoring_policy.v1",
                    "selected_model_name": "rf_regression",
                    "training_scope": "session_trained",
                    "comparison_ready": True,
                },
                "status_semantics": {
                    "trustworthy_recommendations": True,
                    "viewable_artifacts": True,
                },
            },
            candidate_session={
                "comparison_anchors": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "modeling_mode": "regression",
                    "decision_intent": "prioritize_experiments",
                    "scoring_policy_version": "scoring_policy.v1",
                    "selected_model_name": "rf_regression",
                    "training_scope": "session_trained",
                    "comparison_ready": True,
                },
                "status_semantics": {
                    "trustworthy_recommendations": True,
                    "viewable_artifacts": True,
                },
            },
        )

        self.assertEqual(comparison["status"], "directly_comparable")
        self.assertFalse(comparison["blockers"])
        self.assertIn("Same target property: pIC50.", comparison["matches"])

    def test_compare_session_basis_blocks_mismatched_targets(self):
        comparison = compare_session_basis(
            focus_session={
                "comparison_anchors": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "modeling_mode": "regression",
                    "decision_intent": "prioritize_experiments",
                    "comparison_ready": True,
                },
                "status_semantics": {
                    "trustworthy_recommendations": True,
                    "viewable_artifacts": True,
                },
            },
            candidate_session={
                "comparison_anchors": {
                    "target_name": "solubility",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "modeling_mode": "regression",
                    "decision_intent": "prioritize_experiments",
                    "comparison_ready": True,
                },
                "status_semantics": {
                    "trustworthy_recommendations": True,
                    "viewable_artifacts": True,
                },
            },
        )

        self.assertEqual(comparison["status"], "not_comparable")
        self.assertTrue(comparison["blockers"])
        self.assertIn("Target property differs", comparison["blockers"][0])

    def test_compare_session_basis_surfaces_outcome_differences(self):
        comparison = compare_session_basis(
            focus_session={
                "comparison_anchors": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "modeling_mode": "regression",
                    "decision_intent": "prioritize_experiments",
                    "scoring_policy_version": "scoring_policy.v1",
                    "comparison_ready": True,
                },
                "status_semantics": {
                    "trustworthy_recommendations": True,
                    "viewable_artifacts": True,
                },
                "outcome_profile": {
                    "leading_bucket": "exploit",
                    "dominant_trust": "stronger_trust",
                    "out_of_domain_rate": 0.10,
                    "spearman_rank_correlation": 0.52,
                },
            },
            candidate_session={
                "comparison_anchors": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "modeling_mode": "regression",
                    "decision_intent": "prioritize_experiments",
                    "scoring_policy_version": "scoring_policy.v1",
                    "comparison_ready": True,
                },
                "status_semantics": {
                    "trustworthy_recommendations": True,
                    "viewable_artifacts": True,
                },
                "outcome_profile": {
                    "leading_bucket": "learn",
                    "dominant_trust": "high_caution",
                    "out_of_domain_rate": 0.28,
                    "spearman_rank_correlation": 0.31,
                },
            },
        )

        self.assertEqual(comparison["status"], "partially_comparable")
        self.assertTrue(comparison["outcome_differences"])
        self.assertIn("Leading shortlist bucket differs", comparison["outcome_differences"][0])

    def test_compare_session_basis_surfaces_candidate_level_changes(self):
        comparison = compare_session_basis(
            focus_session={
                "comparison_anchors": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "modeling_mode": "regression",
                    "decision_intent": "prioritize_experiments",
                    "scoring_policy_version": "scoring_policy.v1",
                    "comparison_ready": True,
                },
                "status_semantics": {
                    "trustworthy_recommendations": True,
                    "viewable_artifacts": True,
                },
                "candidate_preview": [
                    {
                        "key": "smiles::CCO",
                        "label": "cand_1 (CCO)",
                        "bucket": "exploit",
                        "trust_label": "stronger_trust",
                        "rank_position": 1,
                    },
                    {
                        "key": "smiles::CCN",
                        "label": "cand_2 (CCN)",
                        "bucket": "learn",
                        "trust_label": "mixed_trust",
                        "rank_position": 2,
                    },
                ],
            },
            candidate_session={
                "comparison_anchors": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "modeling_mode": "regression",
                    "decision_intent": "prioritize_experiments",
                    "scoring_policy_version": "scoring_policy.v1",
                    "comparison_ready": True,
                },
                "status_semantics": {
                    "trustworthy_recommendations": True,
                    "viewable_artifacts": True,
                },
                "candidate_preview": [
                    {
                        "key": "smiles::CCCl",
                        "label": "cand_9 (CCCl)",
                        "bucket": "exploit",
                        "trust_label": "stronger_trust",
                        "rank_position": 1,
                    },
                    {
                        "key": "smiles::CCN",
                        "label": "cand_2 (CCN)",
                        "bucket": "exploit",
                        "trust_label": "stronger_trust",
                        "rank_position": 2,
                    },
                ],
            },
        )

        self.assertIn("shared across the compared shortlist previews", comparison["candidate_comparison_summary"])
        self.assertTrue(comparison["candidate_differences"])
        self.assertIn("Lead candidate changed", comparison["candidate_differences"][0])
        self.assertTrue(
            any("Shared candidate bucket changed for cand_2 (CCN)" in item for item in comparison["candidate_differences"])
        )

    def test_compare_session_basis_surfaces_activation_boundary_and_bridge_state_differences(self):
        comparison = compare_session_basis(
            focus_session={
                "scientific_session_truth": {
                    "comparison_anchors": {
                        "target_name": "pIC50",
                        "target_kind": "regression",
                        "optimization_direction": "maximize",
                        "modeling_mode": "regression",
                        "decision_intent": "prioritize_experiments",
                        "scoring_policy_version": "scoring_policy.v1",
                        "comparison_ready": True,
                    },
                    "evidence_loop": {
                        "active_modeling_evidence": ["Observed experimental values"],
                        "active_ranking_evidence": ["Predicted continuous values"],
                        "future_activation_candidates": ["Human review outcomes"],
                    },
                    "evidence_activation_policy": {
                        "interpretation_summary": "Recommendation interpretation currently uses Human review outcomes.",
                        "recommendation_reuse_summary": "Conservative recommendation reuse is currently eligible for Observed experimental values and Human review outcomes.",
                        "future_learning_eligibility_summary": "Future learning consideration is currently limited to Observed experimental values.",
                    },
                    "controlled_reuse": {
                        "recommendation_reuse_active": True,
                        "ranking_context_reuse_active": False,
                        "interpretation_support_active": True,
                        "recommendation_reuse_summary": "Recommendation reuse is active from prior human review outcomes carried through workspace memory.",
                        "ranking_context_reuse_summary": "No prior evidence is currently active for ranking-context reuse in this session.",
                        "interpretation_support_summary": "Workspace feedback memory remains active as interpretation support.",
                    },
                    "belief_state_summary": {
                        "active_claim_count": 2,
                        "accepted_update_count": 1,
                        "proposed_update_count": 1,
                        "superseded_update_count": 1,
                        "support_basis_mix_label": "Grounded mostly in observed labels",
                        "belief_state_readiness_summary": "Read-across is partial because some accepted support exists, but the picture remains update-light.",
                    },
                    "belief_update_summary": {
                        "active_count": 1,
                        "historical_count": 1,
                        "support_basis_mix_label": "Grounded mostly in observed labels",
                    },
                    "claims_summary": {
                        "claims_with_active_support_count": 1,
                        "claims_with_historical_support_only_count": 1,
                        "claims_with_no_governed_support_count": 0,
                        "chronology_summary_text": "Claim-level support chronology remains bounded: 1 claim with active governed support, 1 historical-only.",
                        "claim_support_basis_summary_text": "Claim support-basis composition remains bounded: 1 grounded mostly in observed labels, 1 with no governed support yet.",
                        "continuity_aligned_claim_count": 1,
                        "new_claim_context_count": 0,
                        "weak_prior_alignment_count": 1,
                        "no_prior_claim_context_count": 0,
                        "claims_mostly_observed_label_grounded_count": 1,
                        "claims_with_numeric_rule_based_support_count": 0,
                        "claims_with_weak_basis_support_count": 0,
                        "claims_with_mixed_support_basis_count": 0,
                        "claims_action_ready_follow_up_count": 1,
                        "claims_promising_but_need_stronger_evidence_count": 0,
                        "claims_need_clarifying_experiment_count": 0,
                        "claims_do_not_prioritize_yet_count": 0,
                        "claims_with_insufficient_governed_basis_count": 1,
                        "claims_action_ready_from_active_support_count": 1,
                        "claims_historically_interesting_count": 1,
                        "claims_with_mixed_current_historical_actionability_count": 0,
                        "claim_actionability_summary_text": "Claim actionability remains bounded: 1 action-ready for bounded follow-up, 1 with insufficient governed basis.",
                        "claim_actionability_basis_summary_text": "Claim actionability basis remains bounded: 1 action-ready from current active support, 1 historically interesting and needing fresh evidence.",
                        "read_across_summary_text": "Claim read-across remains bounded: 1 continuity-aligned, 1 weak-alignment.",
                    },
                    "bridge_state_notes": ["Legacy baseline bundle still informed ranking."],
                    "belief_state_alignment_label": "Partial alignment",
                    "belief_state_alignment_summary": "This session aligns with the current support picture, but the added support remains mostly proposed or otherwise limited.",
                },
                "status_semantics": {"trustworthy_recommendations": True, "viewable_artifacts": True},
                "belief_state_alignment_label": "Partial alignment",
                "belief_state_alignment_summary": "This session aligns with the current support picture, but the added support remains mostly proposed or otherwise limited.",
            },
            candidate_session={
                "scientific_session_truth": {
                    "comparison_anchors": {
                        "target_name": "pIC50",
                        "target_kind": "regression",
                        "optimization_direction": "maximize",
                        "modeling_mode": "regression",
                        "decision_intent": "prioritize_experiments",
                        "scoring_policy_version": "scoring_policy.v1",
                        "comparison_ready": True,
                    },
                    "evidence_loop": {
                        "active_modeling_evidence": ["Observed experimental values"],
                        "active_ranking_evidence": ["Predicted continuous values"],
                        "future_activation_candidates": ["Human review outcomes", "Workspace feedback memory"],
                    },
                    "evidence_activation_policy": {
                        "interpretation_summary": "Recommendation interpretation currently uses Human review outcomes and Workspace feedback memory.",
                        "recommendation_reuse_summary": "Conservative recommendation reuse is currently eligible for Observed experimental values.",
                        "future_learning_eligibility_summary": "Future learning consideration is currently limited to Observed experimental values and Queued learning evidence.",
                    },
                    "controlled_reuse": {
                        "recommendation_reuse_active": False,
                        "ranking_context_reuse_active": True,
                        "interpretation_support_active": True,
                        "recommendation_reuse_summary": "No prior human review outcome is currently active for recommendation reuse in this session.",
                        "ranking_context_reuse_summary": "Ranking-context reuse is active for shortlist framing because prior human review outcomes provide stronger reusable continuity context.",
                        "interpretation_support_summary": "Workspace feedback memory remains active as interpretation support.",
                    },
                    "belief_state_summary": {
                        "active_claim_count": 4,
                        "accepted_update_count": 3,
                        "proposed_update_count": 1,
                        "superseded_update_count": 0,
                        "support_basis_mix_label": "Includes bounded numeric interpretation",
                        "belief_state_readiness_summary": "Read-across is stronger because multiple accepted updates contribute to the current target-scoped support picture.",
                    },
                    "belief_update_summary": {
                        "active_count": 3,
                        "historical_count": 0,
                        "support_basis_mix_label": "Includes bounded numeric interpretation",
                    },
                    "claims_summary": {
                        "claims_with_active_support_count": 3,
                        "claims_with_historical_support_only_count": 0,
                        "claims_with_no_governed_support_count": 1,
                        "chronology_summary_text": "Claim-level support chronology remains bounded: 3 claims with active governed support, 1 with no governed support yet.",
                        "claim_support_basis_summary_text": "Claim support-basis composition remains bounded: 1 grounded mostly in observed labels, 2 with bounded numeric interpretation, 1 with no governed support yet.",
                        "continuity_aligned_claim_count": 2,
                        "new_claim_context_count": 1,
                        "weak_prior_alignment_count": 0,
                        "no_prior_claim_context_count": 1,
                        "claims_mostly_observed_label_grounded_count": 1,
                        "claims_with_numeric_rule_based_support_count": 2,
                        "claims_with_weak_basis_support_count": 0,
                        "claims_with_mixed_support_basis_count": 0,
                        "claims_action_ready_follow_up_count": 1,
                        "claims_promising_but_need_stronger_evidence_count": 2,
                        "claims_need_clarifying_experiment_count": 0,
                        "claims_do_not_prioritize_yet_count": 0,
                        "claims_with_insufficient_governed_basis_count": 1,
                        "claims_action_ready_from_active_support_count": 1,
                        "claims_historically_interesting_count": 0,
                        "claims_with_mixed_current_historical_actionability_count": 1,
                        "claim_actionability_summary_text": "Claim actionability remains bounded: 1 action-ready for bounded follow-up, 2 promising but needing stronger evidence, 1 with insufficient governed basis.",
                        "claim_actionability_basis_summary_text": "Claim actionability basis remains bounded: 1 action-ready from current active support, 1 with mixed current/historical action basis, 1 with no active governed support yet.",
                        "read_across_summary_text": "This session introduces new claim context relative to prior target-scoped claims. Read-across remains bounded.",
                    },
                    "bridge_state_notes": ["No baseline fallback was recorded."],
                    "belief_state_alignment_label": "Strong alignment",
                    "belief_state_alignment_summary": "This session aligns with the current support picture and includes accepted support-change records, but that still does not make the picture final truth.",
                },
                "status_semantics": {"trustworthy_recommendations": True, "viewable_artifacts": True},
                "belief_state_alignment_label": "Strong alignment",
                "belief_state_alignment_summary": "This session aligns with the current support picture and includes accepted support-change records, but that still does not make the picture final truth.",
            },
        )

        self.assertEqual(comparison["status"], "partially_comparable")
        self.assertTrue(any("Future activation boundary differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Bridge-state behavior differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Selective interpretation use differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Recommendation-reuse eligibility differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Active recommendation reuse differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Active ranking-context reuse differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Future-learning eligibility differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Belief-state governance differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Belief-state chronology differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Belief-state support basis differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Current support-change coverage differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Historical support-change depth differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Session support basis differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Claim-level active support differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Claim-level historical support differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Claim-level unsupported context differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Claim continuity context differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Claim new-context coverage differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Claim weak-alignment context differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Claim support-basis composition differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Claim actionability differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Claim actionability basis differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Support chronology summary differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Claim read-across summary differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Claim actionability summary differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Claim actionability-basis summary differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Belief-picture read-across differs" in item for item in comparison["differences"]))

    def test_compare_session_basis_discounts_tentative_active_continuity_against_posture_governing_support(self):
        base_anchors = {
            "target_name": "pIC50",
            "target_kind": "regression",
            "optimization_direction": "maximize",
            "modeling_mode": "regression",
            "decision_intent": "prioritize_experiments",
            "scoring_policy_version": "scoring_policy.v1",
            "selected_model_name": "rf_regression",
            "training_scope": "session_trained",
            "comparison_ready": True,
        }
        focus = {
            "scientific_session_truth": {
                "comparison_anchors": base_anchors,
                "belief_update_summary": {
                    "support_quality_label": "Current active support includes decision-useful grounding",
                    "governed_support_posture_label": "Current support governs present posture",
                    "support_coherence_label": "Coherent current support",
                    "support_reuse_label": "Strongly reusable governed support",
                },
                "belief_state_summary": {
                    "support_quality_label": "Current support includes decision-useful grounding",
                    "governed_support_posture_label": "Current support governs present posture",
                    "support_coherence_label": "Coherent current support",
                    "continuity_cluster_posture_label": "Promotion-candidate continuity cluster",
                    "promotion_candidate_posture_label": "Stronger broader governed reuse candidate",
                    "promotion_stability_label": "Stable enough for governed promotion review",
                    "promotion_gate_status_label": "Promotable under bounded governed rules",
                    "promotion_block_reason_label": "No material promotion block recorded",
                },
                "claims_summary": {
                    "claims_with_active_support_count": 1,
                    "claims_with_active_governed_continuity_count": 1,
                    "claims_with_tentative_active_continuity_count": 0,
                    "claims_with_posture_governing_support_count": 1,
                    "claims_with_tentative_current_support_count": 0,
                    "claims_with_accepted_limited_support_count": 0,
                    "claims_with_contested_current_support_count": 0,
                    "claims_with_degraded_current_posture_count": 0,
                    "claims_with_historical_stronger_than_current_count": 0,
                    "claims_with_contradiction_limited_reuse_count": 0,
                    "broader_reuse_label": "Broader reuse is strong under coherent current support",
                    "broader_continuity_label": "Coherent broader continuity cluster",
                    "future_reuse_candidacy_label": "Stronger future governed reuse candidacy",
                    "continuity_cluster_posture_label": "Promotion-candidate continuity cluster",
                    "promotion_candidate_posture_label": "Stronger broader governed reuse candidate",
                    "promotion_stability_label": "Stable enough for governed promotion review",
                    "promotion_gate_status_label": "Promotable under bounded governed rules",
                    "promotion_block_reason_label": "No material promotion block recorded",
                },
                "scientific_decision_summary": {
                    "decision_status_label": "Active governed follow-up basis",
                    "current_support_quality_label": "Current support includes decision-useful grounding",
                    "current_governed_support_posture_label": "Current support governs present posture",
                    "current_support_coherence_label": "Coherent current support",
                    "current_support_reuse_label": "Strongly reusable governed support",
                    "broader_governed_reuse_label": "Broader reuse is strong under coherent current support",
                    "broader_continuity_label": "Coherent broader continuity cluster",
                    "future_reuse_candidacy_label": "Stronger future governed reuse candidacy",
                    "continuity_cluster_posture_label": "Promotion-candidate continuity cluster",
                    "promotion_candidate_posture_label": "Stronger broader governed reuse candidate",
                    "promotion_stability_label": "Stable enough for governed promotion review",
                    "promotion_gate_status_label": "Promotable under bounded governed rules",
                    "promotion_block_reason_label": "No material promotion block recorded",
                },
            },
            "status_semantics": {"trustworthy_recommendations": True, "viewable_artifacts": True},
        }
        candidate = {
            "scientific_session_truth": {
                "comparison_anchors": base_anchors,
                "belief_update_summary": {
                    "support_quality_label": "Current active support remains limited",
                    "governed_support_posture_label": "Current support remains tentative",
                    "support_coherence_label": "Current support is contested",
                    "support_reuse_label": "Reuse with contradiction caution",
                },
                "belief_state_summary": {
                    "support_quality_label": "Current support remains active but limited",
                    "governed_support_posture_label": "Current support remains tentative",
                    "support_coherence_label": "Current support is contested",
                    "broader_target_reuse_label": "Broader reuse is contradiction-limited",
                    "broader_target_continuity_label": "Contested broader continuity cluster",
                    "future_reuse_candidacy_label": "Contradiction-limited future reuse candidacy",
                    "continuity_cluster_posture_label": "Contradiction-limited continuity cluster",
                    "promotion_candidate_posture_label": "Contradiction-limited promotion candidate",
                    "promotion_stability_label": "Unstable under contradiction pressure",
                    "promotion_gate_status_label": "Quarantined from stronger promotion",
                    "promotion_block_reason_label": "Quarantined by unstable continuity",
                },
                "claims_summary": {
                    "claims_with_active_support_count": 1,
                    "claims_with_active_governed_continuity_count": 0,
                    "claims_with_tentative_active_continuity_count": 1,
                    "claims_with_posture_governing_support_count": 0,
                    "claims_with_tentative_current_support_count": 1,
                    "claims_with_accepted_limited_support_count": 0,
                    "claims_with_contested_current_support_count": 1,
                    "claims_with_degraded_current_posture_count": 0,
                    "claims_with_historical_stronger_than_current_count": 0,
                    "claims_with_contradiction_limited_reuse_count": 1,
                    "broader_reuse_label": "Broader reuse is contradiction-limited",
                    "broader_continuity_label": "Contested broader continuity cluster",
                    "future_reuse_candidacy_label": "Contradiction-limited future reuse candidacy",
                    "continuity_cluster_posture_label": "Contradiction-limited continuity cluster",
                    "promotion_candidate_posture_label": "Contradiction-limited promotion candidate",
                    "promotion_stability_label": "Unstable under contradiction pressure",
                    "promotion_gate_status_label": "Quarantined from stronger promotion",
                    "promotion_block_reason_label": "Quarantined by unstable continuity",
                },
                "scientific_decision_summary": {
                    "decision_status_label": "Current active basis remains tentative",
                    "current_support_quality_label": "Current support remains active but limited",
                    "current_governed_support_posture_label": "Current support remains tentative",
                    "current_support_coherence_label": "Current support is contested",
                    "current_support_reuse_label": "Reuse with contradiction caution",
                    "broader_governed_reuse_label": "Broader reuse is contradiction-limited",
                    "broader_continuity_label": "Contested broader continuity cluster",
                    "future_reuse_candidacy_label": "Contradiction-limited future reuse candidacy",
                    "continuity_cluster_posture_label": "Contradiction-limited continuity cluster",
                    "promotion_candidate_posture_label": "Contradiction-limited promotion candidate",
                    "promotion_stability_label": "Unstable under contradiction pressure",
                    "promotion_gate_status_label": "Quarantined from stronger promotion",
                    "promotion_block_reason_label": "Quarantined by unstable continuity",
                },
            },
            "status_semantics": {"trustworthy_recommendations": True, "viewable_artifacts": True},
        }

        comparison = compare_session_basis(focus_session=focus, candidate_session=candidate)

        self.assertTrue(any("Governed support posture differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Support coherence differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Current support reuse differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Broader claim reuse posture differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Broader target reuse differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Broader governed reuse differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Claim-family continuity-cluster posture differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Claim-family promotion posture differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Target-scoped continuity-cluster posture differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Target-scoped promotion posture differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Claim-family promotion stability differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Claim-family promotion gate differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Claim-family promotion block reason differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Target-scoped promotion stability differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Target-scoped promotion gate differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Target-scoped promotion block reason differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Session-family continuity-cluster posture differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Session-family promotion posture differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Session-family promotion stability differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Session-family promotion gate differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Session-family promotion block reason differs" in item for item in comparison["differences"]))
        self.assertTrue(any("Claim posture-governing continuity differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Claim contradiction and reuse posture differs" in item for item in comparison["cautions"]))
        self.assertTrue(any("Current governed-support posture differs" in item for item in comparison["differences"]))

    def test_build_session_comparison_matrix_includes_focus_and_deltas(self):
        focus = {
            "session_id": "focus",
            "source_name": "focus.csv",
            "rows_total": 10,
            "rows_with_values": 8,
            "candidate_count": 4,
            "top_experiment_value": 0.72,
            "results_ready": True,
            "outcome_profile": {
                "bucket_summary": "Exploit 2 / Learn 1 / Explore 1",
                "leading_bucket": "exploit",
                "trust_summary": "Stronger trust 2 / Mixed 1 / Exploratory 1 / High caution 0",
                "dominant_trust": "stronger_trust",
                "diagnostics_summary": "Rank corr 0.510 / Weak-support 10.0%",
            },
            "candidate_preview": [
                {"key": "smiles::CCO", "label": "cand_1 (CCO)", "bucket": "exploit", "rank_position": 1},
                {"key": "smiles::CCN", "label": "cand_2 (CCN)", "bucket": "learn", "rank_position": 2},
            ],
            "comparison_anchors": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "measurement_column": "pic50",
                "modeling_mode": "regression",
                "decision_intent": "prioritize_experiments",
                "scoring_policy_version": "scoring_policy.v1",
                "selected_model_name": "rf_regression",
                "training_scope": "session_trained",
                "comparison_ready": True,
            },
            "scientific_session_truth": {
                "comparison_anchors": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_column": "pic50",
                    "modeling_mode": "regression",
                    "decision_intent": "prioritize_experiments",
                    "scoring_policy_version": "scoring_policy.v1",
                    "selected_model_name": "rf_regression",
                    "training_scope": "session_trained",
                    "comparison_ready": True,
                },
                "evidence_loop": {
                    "active_modeling_evidence": ["Observed experimental values"],
                    "active_ranking_evidence": ["Retrieved reference chemistry context", "Predicted continuous values"],
                    "activation_boundary_summary": "Active modeling uses Observed experimental values. Future activation candidates: Human review outcomes.",
                    "future_activation_candidates": ["Human review outcomes"],
                },
                "controlled_reuse": {
                    "recommendation_reuse_active": True,
                    "ranking_context_reuse_active": False,
                    "interpretation_support_active": True,
                    "recommendation_reuse_summary": "Recommendation reuse is active from prior human review outcomes carried through workspace memory.",
                    "ranking_context_reuse_summary": "No prior evidence is currently active for ranking-context reuse in this session.",
                    "interpretation_support_summary": "Workspace feedback memory remains active as interpretation support.",
                },
                "belief_state_summary": {
                    "active_claim_count": 2,
                    "accepted_update_count": 1,
                    "proposed_update_count": 1,
                    "superseded_update_count": 1,
                    "belief_state_strength_summary": "The current support picture has some accepted grounding, but it is still limited and should be read cautiously.",
                    "belief_state_readiness_summary": "Read-across is partial because some accepted support exists, but the picture remains update-light.",
                    "governance_mix_label": "Mixed governance",
                    "support_basis_mix_label": "Grounded mostly in observed labels",
                    "support_basis_mix_summary": "The current support picture is grounded mostly in observed labels (2) and remains bounded rather than final.",
                    "observed_label_support_count": 2,
                    "numeric_rule_based_support_count": 0,
                    "unresolved_basis_count": 0,
                    "weak_basis_count": 0,
                    "broader_target_reuse_label": "Support is locally meaningful, not broadly governing",
                    "broader_target_reuse_summary": "Current target-scoped support is still mainly local to the present session picture.",
                    "broader_target_continuity_label": "No broader continuity cluster",
                    "broader_target_continuity_summary": "No meaningful broader target continuity cluster is established yet.",
                    "future_reuse_candidacy_label": "Local-only future reuse context",
                    "future_reuse_candidacy_summary": "Future target-level reuse candidacy remains local-only.",
                    "continuity_cluster_posture_label": "Local-only continuity cluster",
                    "continuity_cluster_posture_summary": "Continuity remains local-only right now, so it should stay within local review boundaries.",
                    "promotion_candidate_posture_label": "Context-only continuity, not a promotion candidate",
                    "promotion_candidate_posture_summary": "Current continuity is still context-only rather than a broader governed promotion candidate.",
                    "promotion_stability_label": "Insufficient continuity stability",
                    "promotion_stability_summary": "Current continuity does not yet satisfy enough governed stability for broader promotion review.",
                    "promotion_gate_status_label": "Not a governed promotion candidate",
                    "promotion_gate_status_summary": "Current continuity is not yet promotable under bounded governed rules and should remain local or contextual.",
                    "promotion_block_reason_label": "Local-only meaning",
                    "promotion_block_reason_summary": "Current support picture is still mainly local-only.",
                },
                "belief_update_summary": {
                    "active_count": 1,
                    "historical_count": 1,
                    "support_basis_mix_label": "Grounded mostly in observed labels",
                    "support_basis_mix_summary": "Session support changes are grounded mostly in observed labels (1), with 0 bounded numeric interpretation records and 0 unresolved support basis records.",
                    "observed_label_support_count": 1,
                    "numeric_rule_based_support_count": 0,
                    "unresolved_basis_count": 0,
                    "weak_basis_count": 0,
                },
                "claims_summary": {
                    "claims_with_active_support_count": 1,
                    "claims_with_historical_support_only_count": 0,
                    "claims_with_no_governed_support_count": 1,
                    "chronology_summary_text": "Claim-level support chronology remains bounded: 1 claim with active governed support, 1 with no governed support yet.",
                    "claim_support_basis_summary_text": "Claim support-basis composition remains bounded: 1 grounded mostly in observed labels, 1 with no governed support yet.",
                    "continuity_aligned_claim_count": 1,
                    "new_claim_context_count": 0,
                    "weak_prior_alignment_count": 0,
                    "no_prior_claim_context_count": 1,
                    "claims_mostly_observed_label_grounded_count": 1,
                    "claims_with_numeric_rule_based_support_count": 0,
                    "claims_with_weak_basis_support_count": 0,
                    "claims_with_mixed_support_basis_count": 0,
                    "claims_action_ready_follow_up_count": 1,
                    "claims_promising_but_need_stronger_evidence_count": 0,
                    "claims_need_clarifying_experiment_count": 0,
                    "claims_do_not_prioritize_yet_count": 0,
                    "claims_with_insufficient_governed_basis_count": 1,
                    "claims_action_ready_from_active_support_count": 1,
                    "claims_historically_interesting_count": 1,
                    "claims_with_mixed_current_historical_actionability_count": 0,
                    "claim_actionability_summary_text": "Claim actionability remains bounded: 1 action-ready for bounded follow-up, 1 with insufficient governed basis.",
                    "claim_actionability_basis_summary_text": "Claim actionability basis remains bounded: 1 action-ready from current active support, 1 historically interesting and needing fresh evidence.",
                    "read_across_summary_text": "This session mostly reinforces prior target-scoped claim context. Read-across remains bounded.",
                    "broader_reuse_label": "Support is locally meaningful, not broadly governing",
                    "broader_reuse_summary_text": "Current claim support is still mainly local to the individual claim picture.",
                    "broader_continuity_label": "No broader continuity cluster",
                    "broader_continuity_summary_text": "No meaningful broader claim continuity cluster is established yet.",
                    "future_reuse_candidacy_label": "Local-only future reuse context",
                    "future_reuse_candidacy_summary_text": "Future broader reuse candidacy remains local-only.",
                    "continuity_cluster_posture_label": "Local-only continuity cluster",
                    "continuity_cluster_posture_summary_text": "Claim-family continuity remains local-only right now, so broader promotion would be premature.",
                    "promotion_candidate_posture_label": "Context-only continuity, not a promotion candidate",
                    "promotion_candidate_posture_summary_text": "Claim-family continuity remains context-only rather than a broader governed promotion candidate.",
                    "promotion_stability_label": "Insufficient continuity stability",
                    "promotion_stability_summary_text": "Claim-family continuity does not yet satisfy enough governed stability for broader promotion review.",
                    "promotion_gate_status_label": "Not a governed promotion candidate",
                    "promotion_gate_status_summary_text": "Claim-family continuity is not yet promotable under bounded governed rules and should remain local or contextual.",
                    "promotion_block_reason_label": "Local-only meaning",
                    "promotion_block_reason_summary_text": "Claim-family continuity remains mainly local-only right now.",
                },
                "bridge_state_notes": ["Legacy baseline bundle still informed ranking."],
            },
            "belief_state_alignment_label": "Partial alignment",
            "belief_state_alignment_summary": "This session aligns with the current support picture, but the added support remains mostly proposed or otherwise limited.",
            "scientific_truth_source_label": "Canonical scientific session truth",
        }
        candidate = {
            "session_id": "candidate",
            "source_name": "candidate.csv",
            "rows_total": 14,
            "rows_with_values": 10,
            "candidate_count": 6,
            "top_experiment_value": 0.81,
            "results_ready": True,
            "outcome_profile": {
                "bucket_summary": "Exploit 3 / Learn 2 / Explore 1",
                "leading_bucket": "exploit",
                "trust_summary": "Stronger trust 3 / Mixed 1 / Exploratory 1 / High caution 1",
                "dominant_trust": "stronger_trust",
                "diagnostics_summary": "Rank corr 0.620 / Weak-support 20.0%",
            },
            "candidate_preview": [
                {"key": "smiles::CCO", "label": "cand_1 (CCO)", "bucket": "exploit", "rank_position": 1},
                {"key": "smiles::CCCl", "label": "cand_3 (CCCl)", "bucket": "explore", "rank_position": 2},
            ],
            "comparison_anchors": {
                "target_name": "pIC50",
                "target_kind": "regression",
                "optimization_direction": "maximize",
                "measurement_column": "pic50",
                "modeling_mode": "regression",
                "decision_intent": "prioritize_experiments",
                "scoring_policy_version": "scoring_policy.v1",
                "selected_model_name": "rf_regression",
                "training_scope": "session_trained",
                "comparison_ready": True,
            },
            "scientific_session_truth": {
                "comparison_anchors": {
                    "target_name": "pIC50",
                    "target_kind": "regression",
                    "optimization_direction": "maximize",
                    "measurement_column": "pic50",
                    "modeling_mode": "regression",
                    "decision_intent": "prioritize_experiments",
                    "scoring_policy_version": "scoring_policy.v1",
                    "selected_model_name": "rf_regression",
                    "training_scope": "session_trained",
                    "comparison_ready": True,
                },
                "evidence_loop": {
                    "active_modeling_evidence": ["Observed experimental values"],
                    "active_ranking_evidence": ["Retrieved reference chemistry context", "Predicted continuous values"],
                    "activation_boundary_summary": "Active modeling uses Observed experimental values. Future activation candidates: Human review outcomes and Workspace feedback memory.",
                    "future_activation_candidates": ["Human review outcomes", "Workspace feedback memory"],
                },
                "controlled_reuse": {
                    "recommendation_reuse_active": False,
                    "ranking_context_reuse_active": True,
                    "interpretation_support_active": True,
                    "recommendation_reuse_summary": "No prior human review outcome is currently active for recommendation reuse in this session.",
                    "ranking_context_reuse_summary": "Ranking-context reuse is active for shortlist framing because prior human review outcomes provide stronger reusable continuity context.",
                    "interpretation_support_summary": "Workspace feedback memory remains active as interpretation support.",
                },
                "belief_state_summary": {
                    "active_claim_count": 4,
                    "accepted_update_count": 3,
                    "proposed_update_count": 1,
                    "superseded_update_count": 0,
                    "belief_state_strength_summary": "The current support picture is more grounded because multiple accepted updates point in a similar direction, but it remains non-final.",
                    "belief_state_readiness_summary": "Read-across is stronger because multiple accepted updates contribute to the current target-scoped support picture.",
                    "governance_mix_label": "Mostly accepted",
                    "support_basis_mix_label": "Includes bounded numeric interpretation",
                    "support_basis_mix_summary": "The current support picture includes bounded numeric interpretation under current target rules (2) and should still be read cautiously.",
                    "observed_label_support_count": 1,
                    "numeric_rule_based_support_count": 2,
                    "unresolved_basis_count": 1,
                    "weak_basis_count": 0,
                    "broader_target_reuse_label": "Broader reuse is selective",
                    "broader_target_reuse_summary": "Broader target-scoped reuse is selective.",
                    "broader_target_continuity_label": "Selective broader continuity cluster",
                    "broader_target_continuity_summary": "The broader target continuity cluster is selective.",
                    "future_reuse_candidacy_label": "Selective future reuse candidacy",
                    "future_reuse_candidacy_summary": "This target picture is only a selective future reuse candidate.",
                    "continuity_cluster_posture_label": "Selective continuity cluster",
                    "continuity_cluster_posture_summary": "Continuity is usable more broadly, but it remains selective rather than strong enough for cleaner promotion posture.",
                    "promotion_candidate_posture_label": "Selective broader governed reuse candidate",
                    "promotion_candidate_posture_summary": "This target picture is only a selective broader governed reuse candidate right now.",
                    "promotion_stability_label": "Only selectively stable for promotion",
                    "promotion_stability_summary": "This target-scoped continuity is only selectively stable for promotion.",
                    "promotion_gate_status_label": "Selectively promotable under bounded governed rules",
                    "promotion_gate_status_summary": "This target-scoped continuity is only selectively promotable under bounded governed rules.",
                    "promotion_block_reason_label": "Selective continuity only",
                    "promotion_block_reason_summary": "Current continuity is selective only.",
                },
                "belief_update_summary": {
                    "active_count": 3,
                    "historical_count": 0,
                    "support_basis_mix_label": "Includes bounded numeric interpretation",
                    "support_basis_mix_summary": "Session support changes rely mainly on bounded numeric interpretation under current target rules (2), with 1 observed-label record and 1 unresolved support basis record.",
                    "observed_label_support_count": 1,
                    "numeric_rule_based_support_count": 2,
                    "unresolved_basis_count": 1,
                    "weak_basis_count": 0,
                },
                "claims_summary": {
                    "claims_with_active_support_count": 2,
                    "claims_with_historical_support_only_count": 0,
                    "claims_with_no_governed_support_count": 0,
                    "chronology_summary_text": "Claim-level support chronology remains bounded: 2 claims with active governed support.",
                    "claim_support_basis_summary_text": "Claim support-basis composition remains bounded: 1 grounded mostly in observed labels, 1 with bounded numeric interpretation.",
                    "continuity_aligned_claim_count": 1,
                    "new_claim_context_count": 1,
                    "weak_prior_alignment_count": 0,
                    "no_prior_claim_context_count": 0,
                    "claims_mostly_observed_label_grounded_count": 1,
                    "claims_with_numeric_rule_based_support_count": 1,
                    "claims_with_weak_basis_support_count": 0,
                    "claims_with_mixed_support_basis_count": 0,
                    "claims_action_ready_follow_up_count": 1,
                    "claims_promising_but_need_stronger_evidence_count": 1,
                    "claims_need_clarifying_experiment_count": 0,
                    "claims_do_not_prioritize_yet_count": 0,
                    "claims_with_insufficient_governed_basis_count": 0,
                    "claims_action_ready_from_active_support_count": 1,
                    "claims_historically_interesting_count": 0,
                    "claims_with_mixed_current_historical_actionability_count": 0,
                    "claim_actionability_summary_text": "Claim actionability remains bounded: 1 action-ready for bounded follow-up, 1 promising but needing stronger evidence.",
                    "claim_actionability_basis_summary_text": "Claim actionability basis remains bounded: 1 action-ready from current active support.",
                    "read_across_summary_text": "Claim read-across remains bounded: 1 continuity-aligned, 1 new-context.",
                    "broader_reuse_label": "Broader reuse is selective",
                    "broader_reuse_summary_text": "Broader claim reuse is selective.",
                    "broader_continuity_label": "Selective broader continuity cluster",
                    "broader_continuity_summary_text": "The broader claim continuity cluster is selective.",
                    "future_reuse_candidacy_label": "Selective future reuse candidacy",
                    "future_reuse_candidacy_summary_text": "Future broader reuse candidacy is selective.",
                    "continuity_cluster_posture_label": "Selective continuity cluster",
                    "continuity_cluster_posture_summary_text": "Claim-family continuity is usable but still selective rather than strong enough for cleaner promotion posture.",
                    "promotion_candidate_posture_label": "Selective broader governed reuse candidate",
                    "promotion_candidate_posture_summary_text": "Claim-family promotion posture is selective only right now.",
                    "promotion_stability_label": "Only selectively stable for promotion",
                    "promotion_stability_summary_text": "Claim-family continuity is only selectively stable for promotion.",
                    "promotion_gate_status_label": "Selectively promotable under bounded governed rules",
                    "promotion_gate_status_summary_text": "Claim-family continuity is only selectively promotable under bounded governed rules.",
                    "promotion_block_reason_label": "Selective continuity only",
                    "promotion_block_reason_summary_text": "Claim-family continuity remains selective only right now.",
                },
                "scientific_decision_summary": {
                    "broader_governed_reuse_label": "Broader reuse is selective",
                    "broader_governed_reuse_summary": "Broader governed reuse is selective.",
                    "broader_continuity_label": "Selective broader continuity cluster",
                    "broader_continuity_summary": "Broader continuity is selective.",
                    "future_reuse_candidacy_label": "Selective future reuse candidacy",
                    "future_reuse_candidacy_summary": "Future broader governed reuse candidacy is selective.",
                    "continuity_cluster_posture_label": "Selective continuity cluster",
                    "continuity_cluster_posture_summary": "Session-family continuity is selective only right now.",
                    "promotion_candidate_posture_label": "Selective broader governed reuse candidate",
                    "promotion_candidate_posture_summary": "Session-family promotion posture is selective only right now.",
                    "promotion_stability_label": "Only selectively stable for promotion",
                    "promotion_stability_summary": "Session-family continuity is only selectively stable for promotion.",
                    "promotion_gate_status_label": "Selectively promotable under bounded governed rules",
                    "promotion_gate_status_summary": "Session-family continuity is only selectively promotable under bounded governed rules.",
                    "promotion_block_reason_label": "Selective continuity only",
                    "promotion_block_reason_summary": "Session-family continuity remains selective only right now.",
                },
            },
            "belief_state_alignment_label": "Strong alignment",
            "belief_state_alignment_summary": "This session aligns with the current support picture and includes accepted support-change records, but that still does not make the picture final truth.",
            "scientific_truth_source_label": "Canonical scientific session truth",
            "discovery_url": "/discovery?session_id=candidate",
            "dashboard_url": "/dashboard?session_id=candidate",
            "status_semantics": {
                "trustworthy_recommendations": True,
                "viewable_artifacts": True,
            },
        }

        matrix = build_session_comparison_matrix(
            focus_session=focus,
            items=[focus, candidate],
        )

        self.assertEqual(matrix["rows"][0]["session_id"], "focus")
        self.assertEqual(matrix["rows"][0]["comparison"]["label"], "Focus session")
        self.assertEqual(matrix["rows"][1]["comparison"]["status"], "partially_comparable")
        self.assertEqual(matrix["rows"][1]["rows_total_delta"], 4)
        self.assertAlmostEqual(matrix["rows"][1]["top_experiment_value_delta"], 0.09, places=6)
        self.assertEqual(matrix["rows"][1]["leading_bucket_label"], "Exploit")
        self.assertIn("Rank corr 0.620", matrix["rows"][1]["diagnostics_summary"])
        self.assertIn("shared across the compared shortlist previews", matrix["rows"][1]["candidate_comparison_summary"])
        self.assertEqual(matrix["focus_basis_source_label"], "Canonical scientific session truth")
        self.assertIn("Active modeling uses", matrix["focus_activation_boundary_summary"])
        self.assertEqual(matrix["rows"][1]["basis_source_label"], "Canonical scientific session truth")
        self.assertIn("Modeling: Observed experimental values", matrix["rows"][1]["evidence_basis_label"])
        self.assertIn("Human review outcomes", matrix["rows"][1]["future_activation_summary"])
        self.assertTrue(matrix["rows"][1]["ranking_context_reuse_active"])
        self.assertIn("Workspace feedback memory remains active as interpretation support", matrix["rows"][1]["controlled_reuse_summary"])
        self.assertEqual(matrix["rows"][1]["belief_state_governance_label"], "Mostly accepted")
        self.assertEqual(matrix["rows"][0]["belief_state_support_basis_label"], "Grounded mostly in observed labels")
        self.assertEqual(matrix["rows"][1]["belief_state_support_basis_label"], "Includes bounded numeric interpretation")
        self.assertEqual(matrix["rows"][1]["belief_update_support_basis_label"], "Includes bounded numeric interpretation")
        self.assertEqual(matrix["rows"][0]["claims_observed_label_grounded_count"], 1)
        self.assertEqual(matrix["rows"][1]["claims_numeric_rule_based_support_count"], 1)
        self.assertIn("claim support-basis composition remains bounded", matrix["rows"][0]["claims_support_basis_summary"].lower())
        self.assertIn("claim actionability remains bounded", matrix["rows"][0]["claims_actionability_summary"].lower())
        self.assertEqual(matrix["rows"][1]["claims_need_stronger_evidence_count"], 1)
        self.assertEqual(matrix["rows"][0]["session_support_role_label"], "Contributed current support")
        self.assertEqual(matrix["rows"][1]["session_support_role_label"], "Contributed current support")
        self.assertIn("governed support", matrix["rows"][0]["session_support_role_summary"].lower())
        self.assertEqual(matrix["rows"][0]["claims_with_active_support_count"], 1)
        self.assertEqual(matrix["rows"][1]["claims_with_active_support_count"], 2)
        self.assertIn("claim-level support chronology remains bounded", matrix["rows"][1]["claims_chronology_summary"].lower())
        self.assertEqual(matrix["rows"][0]["claims_continuity_aligned_count"], 1)
        self.assertEqual(matrix["rows"][1]["claims_new_context_count"], 1)
        self.assertIn("claim read-across remains bounded", matrix["rows"][1]["claims_read_across_summary"].lower())
        self.assertEqual(matrix["rows"][0]["claims_broader_reuse_label"], "Support is locally meaningful, not broadly governing")
        self.assertEqual(matrix["rows"][1]["claims_broader_reuse_label"], "Broader reuse is selective")
        self.assertEqual(matrix["rows"][0]["claims_continuity_cluster_posture_label"], "Local-only continuity cluster")
        self.assertEqual(
            matrix["rows"][0]["claims_promotion_candidate_posture_label"],
            "Context-only continuity, not a promotion candidate",
        )
        self.assertEqual(matrix["rows"][1]["claims_continuity_cluster_posture_label"], "Selective continuity cluster")
        self.assertEqual(
            matrix["rows"][1]["claims_promotion_candidate_posture_label"],
            "Selective broader governed reuse candidate",
        )
        self.assertEqual(matrix["rows"][0]["claims_promotion_gate_status_label"], "Not a governed promotion candidate")
        self.assertEqual(
            matrix["rows"][0]["claims_promotion_block_reason_label"],
            "Local-only meaning",
        )
        self.assertEqual(
            matrix["rows"][1]["claims_promotion_gate_status_label"],
            "Selectively promotable under bounded governed rules",
        )
        self.assertEqual(matrix["rows"][1]["belief_state_broader_target_reuse_label"], "Broader reuse is selective")
        self.assertEqual(matrix["rows"][0]["belief_state_continuity_cluster_posture_label"], "Local-only continuity cluster")
        self.assertEqual(
            matrix["rows"][0]["belief_state_promotion_candidate_posture_label"],
            "Context-only continuity, not a promotion candidate",
        )
        self.assertEqual(
            matrix["rows"][0]["belief_state_promotion_gate_status_label"],
            "Not a governed promotion candidate",
        )
        self.assertEqual(matrix["rows"][1]["belief_state_continuity_cluster_posture_label"], "Selective continuity cluster")
        self.assertEqual(
            matrix["rows"][1]["belief_state_promotion_candidate_posture_label"],
            "Selective broader governed reuse candidate",
        )
        self.assertEqual(
            matrix["rows"][1]["belief_state_promotion_gate_status_label"],
            "Selectively promotable under bounded governed rules",
        )
        self.assertEqual(matrix["rows"][1]["scientific_decision_broader_governed_reuse_label"], "Broader reuse is selective")
        self.assertEqual(
            matrix["rows"][1]["scientific_decision_continuity_cluster_posture_label"],
            "Selective continuity cluster",
        )
        self.assertEqual(
            matrix["rows"][1]["scientific_decision_promotion_candidate_posture_label"],
            "Selective broader governed reuse candidate",
        )
        self.assertEqual(
            matrix["rows"][1]["scientific_decision_promotion_gate_status_label"],
            "Selectively promotable under bounded governed rules",
        )
        self.assertEqual(matrix["rows"][1]["belief_state_alignment_label"], "Strong alignment")
        self.assertEqual(matrix["rows"][1]["belief_state_superseded_updates"], 0)

    def test_build_session_comparison_matrix_surfaces_multi_layer_review_fields(self):
        session = {
            "session_id": "focus",
            "scientific_session_truth": {
                "belief_state_summary": {
                    "governed_review_status_label": "Reviewed and blocked",
                    "governed_review_status_summary": "Belief-state broader review is blocked.",
                    "governed_review_history_summary": "This belief-state posture has 2 governed review records.",
                    "promotion_audit_summary": "Latest promotion outcome is blocked.",
                    "continuity_cluster_review_status_label": "Reviewed and deferred",
                    "continuity_cluster_review_status_summary": "Continuity-cluster review remains deferred.",
                    "continuity_cluster_review_history_summary": "This continuity cluster has 2 governed review records.",
                    "continuity_cluster_promotion_audit_summary": "Latest promotion outcome is deferred.",
                    "carryover_guardrail_summary": "Weak continuity multiplicity does not simulate stronger broader carryover.",
                },
                "scientific_decision_summary": {
                    "session_family_review_status_label": "Reviewed and downgraded later",
                    "session_family_review_status_summary": "Session-family carryover was downgraded later.",
                    "session_family_review_history_summary": "This session-family carryover picture has 3 governed review records.",
                    "session_family_promotion_audit_summary": "Latest promotion outcome is downgraded.",
                    "carryover_guardrail_summary": "Weak local multiplicity does not simulate approved session-family carryover.",
                },
            },
            "discovery_url": "/discovery?session_id=focus",
            "dashboard_url": "/dashboard?session_id=focus",
        }

        matrix = build_session_comparison_matrix(
            focus_session=session,
            items=[session],
        )

        row = matrix["rows"][0]
        self.assertEqual(row["belief_state_governed_review_status_label"], "Reviewed and blocked")
        self.assertEqual(row["belief_state_continuity_cluster_review_status_label"], "Reviewed and deferred")
        self.assertIn("belief-state posture", row["belief_state_governed_review_history_summary"].lower())
        self.assertEqual(row["scientific_decision_session_family_review_status_label"], "Reviewed and downgraded later")
        self.assertIn("session-family carryover", row["scientific_decision_session_family_review_history_summary"].lower())
        self.assertIn(
            "does not simulate approved session-family carryover",
            row["scientific_decision_carryover_guardrail_summary"].lower(),
        )


if __name__ == "__main__":
    unittest.main()
