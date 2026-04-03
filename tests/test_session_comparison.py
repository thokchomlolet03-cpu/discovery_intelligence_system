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
                    "bridge_state_notes": ["Legacy baseline bundle still informed ranking."],
                },
                "status_semantics": {"trustworthy_recommendations": True, "viewable_artifacts": True},
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
                    "bridge_state_notes": ["No baseline fallback was recorded."],
                },
                "status_semantics": {"trustworthy_recommendations": True, "viewable_artifacts": True},
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
                "bridge_state_notes": ["Legacy baseline bundle still informed ranking."],
            },
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
            },
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


if __name__ == "__main__":
    unittest.main()
