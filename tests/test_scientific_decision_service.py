import unittest

from system.services.scientific_decision_service import build_scientific_decision_summary


class ScientificDecisionServiceTest(unittest.TestCase):
    def test_summary_marks_historical_only_claims_as_fresh_evidence_cases(self):
        summary = build_scientific_decision_summary(
            {
                "claims_summary": {
                    "claims_historically_interesting_count": 2,
                    "claims_with_insufficient_governed_basis_count": 2,
                },
                "experiment_request_summary": {
                    "request_count": 1,
                },
            }
        )

        self.assertEqual(summary["decision_status_label"], "Historical-interest claim picture")
        self.assertEqual(summary["current_support_quality_label"], "No active support quality yet")
        self.assertEqual(summary["current_governed_support_posture_label"], "No current posture-governing support")
        self.assertEqual(summary["current_support_coherence_label"], "No coherent current support")
        self.assertEqual(summary["next_step_label"], "Gather fresh evidence before acting")
        self.assertIn("older support context", summary["decision_status_summary"].lower())

    def test_summary_marks_active_ready_claims_as_current_follow_up_basis(self):
        summary = build_scientific_decision_summary(
            {
                "claims_summary": {
                    "claims_action_ready_from_active_support_count": 1,
                    "claims_with_mixed_current_historical_actionability_count": 1,
                    "claims_historically_interesting_count": 1,
                },
                "linked_result_summary": {
                    "result_count": 2,
                    "bounded_numeric_interpretation_count": 1,
                    "unresolved_numeric_interpretation_count": 1,
                },
                "belief_update_summary": {
                    "update_count": 1,
                    "decision_useful_active_support_count": 1,
                    "posture_governing_support_count": 1,
                },
                "belief_state_summary": {
                    "support_quality_label": "Current support includes decision-useful grounding",
                    "support_quality_summary": "1 active support update currently looks decision-useful enough for bounded follow-up.",
                    "governed_support_posture_label": "Current support governs present posture",
                    "governed_support_posture_summary": "1 accepted support update currently governs present posture for bounded follow-up.",
                    "broader_target_reuse_label": "Broader reuse is strong under coherent current support",
                    "broader_target_reuse_summary": "Broader target-scoped reuse is strongest when the current target picture stays coherent.",
                    "broader_target_continuity_label": "Coherent broader continuity cluster",
                    "broader_target_continuity_summary": "The broader target continuity cluster is coherent.",
                    "future_reuse_candidacy_label": "Stronger future governed reuse candidacy",
                    "future_reuse_candidacy_summary": "This target picture now looks like a stronger later candidate for broader governed reuse.",
                    "continuity_cluster_posture_label": "Promotion-candidate continuity cluster",
                    "continuity_cluster_posture_summary": "Current continuity is coherent enough to be treated as a stronger broader governed promotion candidate later.",
                    "promotion_candidate_posture_label": "Stronger broader governed reuse candidate",
                    "promotion_candidate_posture_summary": "This session-family continuity now looks like a stronger broader governed reuse candidate if the current posture holds.",
                    "promotion_stability_label": "Stable enough for governed promotion review",
                    "promotion_stability_summary": "Current session-family continuity is stable enough for governed promotion review.",
                    "promotion_gate_status_label": "Promotable under bounded governed rules",
                    "promotion_gate_status_summary": "Current session-family continuity is promotable under bounded governed rules.",
                    "promotion_block_reason_label": "No material promotion block recorded",
                    "promotion_block_reason_summary": "No material promotion block is currently recorded for the session-family continuity picture.",
                },
            }
        )

        self.assertEqual(summary["decision_status_label"], "Active governed follow-up basis")
        self.assertEqual(summary["current_support_quality_label"], "Current support includes decision-useful grounding")
        self.assertEqual(summary["current_governed_support_posture_label"], "Current support governs present posture")
        self.assertEqual(summary["current_support_coherence_label"], "Coherent current support")
        self.assertEqual(summary["current_support_reuse_label"], "Strongly reusable governed support")
        self.assertEqual(summary["broader_governed_reuse_label"], "Broader reuse is strong under coherent current support")
        self.assertEqual(summary["broader_continuity_label"], "Coherent broader continuity cluster")
        self.assertEqual(summary["future_reuse_candidacy_label"], "Stronger future governed reuse candidacy")
        self.assertEqual(summary["continuity_cluster_posture_label"], "Promotion-candidate continuity cluster")
        self.assertEqual(summary["promotion_candidate_posture_label"], "Stronger broader governed reuse candidate")
        self.assertEqual(summary["promotion_stability_label"], "Stable enough for governed promotion review")
        self.assertEqual(summary["promotion_gate_status_label"], "Promotable under bounded governed rules")
        self.assertEqual(summary["promotion_block_reason_label"], "No material promotion block recorded")
        self.assertEqual(summary["next_step_label"], "Bounded follow-up is reasonable now")
        self.assertEqual(summary["result_state_label"], "Observed results recorded")
        self.assertIn("interpreted under the current target rule", summary["result_state_summary"].lower())
        self.assertIn("keeping observed outcomes separate from final truth", summary["result_state_summary"].lower())

    def test_summary_marks_contested_and_degraded_support_as_clarification_heavy(self):
        summary = build_scientific_decision_summary(
            {
                "claims_summary": {
                    "claims_need_clarifying_experiment_count": 1,
                    "claims_with_contested_current_support_count": 1,
                },
                "belief_update_summary": {
                    "active_count": 2,
                    "contradiction_pressure_count": 1,
                    "current_support_contested_flag": True,
                    "current_posture_degraded_flag": True,
                },
                "belief_state_summary": {
                    "support_coherence_label": "Contested and degraded current support",
                    "support_coherence_summary": "Current support is both contested and degraded: mixed or weakening updates reduce how strongly it should shape present posture.",
                    "support_reuse_label": "Reuse with contradiction caution",
                    "support_reuse_summary": "Current support should be reused only with contradiction caution because mixed or weakening evidence reduces how cleanly it carries forward.",
                    "broader_target_reuse_label": "Broader reuse is contradiction-limited",
                    "broader_target_reuse_summary": "Broader target-scoped reuse should stay contradiction-limited because degraded present posture weakens cleaner carryover.",
                    "broader_target_continuity_label": "Contested broader continuity cluster",
                    "broader_target_continuity_summary": "The broader target continuity cluster is contested.",
                    "future_reuse_candidacy_label": "Contradiction-limited future reuse candidacy",
                    "future_reuse_candidacy_summary": "Future target-level reuse candidacy is contradiction-limited.",
                    "continuity_cluster_posture_label": "Contradiction-limited continuity cluster",
                    "continuity_cluster_posture_summary": "Continuity remains visible, but contradiction pressure keeps it out of stronger promotion-candidate territory.",
                    "promotion_candidate_posture_label": "Contradiction-limited promotion candidate",
                    "promotion_candidate_posture_summary": "This session-family continuity is blocked from stronger promotion posture by contradiction-heavy current history.",
                    "promotion_stability_label": "Unstable under contradiction pressure",
                    "promotion_stability_summary": "Current session-family continuity is unstable under contradiction pressure.",
                    "promotion_gate_status_label": "Quarantined from stronger promotion",
                    "promotion_gate_status_summary": "Current session-family continuity is quarantined from stronger promotion.",
                    "promotion_block_reason_label": "Quarantined by unstable continuity",
                    "promotion_block_reason_summary": "Promotion is quarantined because current continuity is too unstable under contradiction-heavy and degraded history.",
                    "current_support_contested_flag": True,
                    "current_posture_degraded_flag": True,
                },
            }
        )

        self.assertEqual(summary["decision_status_label"], "Contested and degraded current posture")
        self.assertEqual(summary["current_support_coherence_label"], "Contested and degraded current support")
        self.assertEqual(summary["current_support_reuse_label"], "Reuse with contradiction caution")
        self.assertEqual(summary["broader_governed_reuse_label"], "Broader reuse is contradiction-limited")
        self.assertEqual(summary["broader_continuity_label"], "Contested broader continuity cluster")
        self.assertEqual(summary["future_reuse_candidacy_label"], "Contradiction-limited future reuse candidacy")
        self.assertEqual(summary["continuity_cluster_posture_label"], "Contradiction-limited continuity cluster")
        self.assertEqual(summary["promotion_candidate_posture_label"], "Contradiction-limited promotion candidate")
        self.assertEqual(summary["promotion_stability_label"], "Unstable under contradiction pressure")
        self.assertEqual(summary["promotion_gate_status_label"], "Quarantined from stronger promotion")
        self.assertEqual(summary["promotion_block_reason_label"], "Quarantined by unstable continuity")
        self.assertEqual(summary["next_step_label"], "Clarify mixed evidence before stronger follow-up")


if __name__ == "__main__":
    unittest.main()
