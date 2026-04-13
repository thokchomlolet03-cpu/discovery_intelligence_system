import unittest
from unittest.mock import patch

from system.services.governance_workflow_service import (
    build_governance_inbox,
    build_governance_workbench,
    collect_governance_inbox_items_for_session_item,
    resolve_governance_subject_context,
)


def _session_item() -> dict:
    return {
        "session_id": "session_1",
        "source_name": "upload.csv",
        "discovery_url": "/discovery?session_id=session_1",
        "dashboard_url": "/dashboard?session_id=session_1",
        "scientific_session_truth": {
            "workspace_id": "workspace_1",
            "session_id": "session_1",
            "belief_state_ref": {"target_key": "target_1"},
            "claim_refs": [
                {
                    "claim_id": "claim_1",
                    "candidate_id": "cand_1",
                    "claim_statement": "cand_1 remains locally useful but should not travel broadly yet.",
                    "claim_source_class_label": "User-uploaded uncontrolled source",
                    "claim_provenance_confidence_label": "Weak provenance",
                    "claim_trust_tier_label": "Local-only evidence",
                    "claim_promotion_gate_status_label": "Not a governed promotion candidate",
                    "claim_promotion_block_reason_label": "Weak provenance",
                    "claim_governed_review_status_label": "Reviewed and blocked",
                    "claim_governed_review_status_summary": "Claim broader carryover is blocked.",
                    "claim_governed_review_reason_label": "Weak provenance",
                    "claim_governed_review_reason_summary": "Weak provenance keeps broader carryover blocked.",
                    "claim_effective_governed_review_origin_label": "manual",
                    "claim_effective_governed_review_origin_summary": "Current effective governance posture is controlled by explicit human review rather than by derived posture alone.",
                    "claim_derived_governed_review_status_label": "Review candidate",
                    "claim_derived_governed_review_status_summary": "Claim remains a review candidate only.",
                    "claim_derived_governed_review_reason_label": "Stronger trust still needed",
                    "claim_derived_governed_review_reason_summary": "Derived posture still needs stronger trust.",
                    "claim_manual_governed_review_status_label": "Reviewed and blocked",
                    "claim_manual_governed_review_status_summary": "Owner manually blocked broader carryover.",
                    "claim_manual_governed_review_reason_label": "Weak provenance",
                    "claim_manual_governed_review_reason_summary": "Owner manually blocked due to weak provenance.",
                    "claim_manual_governed_review_action_label": "Blocked by reviewer",
                    "claim_manual_governed_review_reviewer_label": "Owner",
                    "claim_actionability_summary": "Claim remains locally useful for bounded follow-up.",
                    "claim_broader_reuse_summary": "Broader carryover remains blocked.",
                    "claim_future_reuse_candidacy_summary": "Future broader influence still needs stronger provenance.",
                    "claim_support_coherence_summary": "Contradiction-heavy active support is limiting broader carryover.",
                    "claim_promotion_audit_summary": "Latest promotion outcome is blocked.",
                }
            ],
            "belief_state_summary": {
                "governed_review_subject_id": "belief::target_1",
                "source_class_label": "User-uploaded uncontrolled source",
                "provenance_confidence_label": "Weak provenance",
                "trust_tier_label": "Review-candidate evidence",
                "promotion_gate_status_label": "Selectively promotable under bounded governed rules",
                "promotion_block_reason_label": "Contradiction-heavy current posture",
                "governed_review_status_label": "Reviewed and deferred",
                "governed_review_status_summary": "Belief-state broader review remains deferred.",
                "governed_review_reason_label": "Stronger trust still needed",
                "governed_review_reason_summary": "Belief-state broader carryover remains deferred pending stronger trust.",
                "effective_governed_review_origin_label": "derived",
                "effective_governed_review_origin_summary": "Current effective governance posture is still derived from the bridge-state rules because no active manual override is governing this layer.",
                "derived_governed_review_status_label": "Reviewed and deferred",
                "derived_governed_review_status_summary": "Belief-state broader review remains deferred.",
                "belief_state_strength_summary": "Belief-state remains locally useful.",
                "belief_state_readiness_summary": "Belief-state is not broader-ready yet.",
                "broader_target_reuse_summary": "Broader reuse remains selective only.",
                "future_reuse_candidacy_summary": "Future broader influence remains bounded.",
                "support_coherence_summary": "Contradiction-heavy current posture weakens broader carryover.",
                "carryover_guardrail_summary": "Weak multiplicity does not simulate stronger broader carryover.",
                "continuity_cluster_review_subject_id": "continuity::target_1",
                "continuity_cluster_review_status_label": "Reviewed and blocked",
                "continuity_cluster_review_status_summary": "Continuity-cluster carryover is blocked.",
                "continuity_cluster_review_reason_label": "Contradiction-heavy current posture",
                "continuity_cluster_review_reason_summary": "Continuity-cluster broader carryover is blocked by contradiction-heavy continuity.",
                "continuity_cluster_effective_review_origin_label": "manual",
                "continuity_cluster_effective_review_origin_summary": "Current effective governance posture is controlled by explicit human review rather than by derived posture alone.",
                "continuity_cluster_derived_review_status_label": "Review candidate",
                "continuity_cluster_manual_review_status_label": "Reviewed and blocked",
                "continuity_cluster_manual_review_action_label": "Blocked by reviewer",
                "continuity_cluster_manual_review_reviewer_label": "Owner",
                "continuity_cluster_posture_summary": "Continuity remains informative locally but unsafe for stronger broader carryover.",
                "continuity_cluster_promotion_audit_summary": "Latest promotion outcome is blocked.",
            },
            "scientific_decision_summary": {
                "session_family_review_subject_id": "session_family::target_1",
                "source_class_label": "User-uploaded uncontrolled source",
                "provenance_confidence_label": "Weak provenance",
                "trust_tier_label": "Review-candidate evidence",
                "promotion_gate_status_label": "Selectively promotable under bounded governed rules",
                "promotion_block_reason_label": "Weak provenance",
                "session_family_review_status_label": "Reviewed and quarantined later",
                "session_family_review_status_summary": "Session-family carryover is quarantined from stronger broader influence.",
                "session_family_review_reason_label": "Weak provenance",
                "session_family_review_reason_summary": "Manual quarantine keeps broader carryover bounded.",
                "session_family_effective_review_origin_label": "manual",
                "session_family_effective_review_origin_summary": "Current effective governance posture is controlled by explicit human review rather than by derived posture alone.",
                "session_family_derived_review_status_label": "Reviewed and approved",
                "session_family_manual_review_status_label": "Reviewed and quarantined later",
                "session_family_manual_review_action_label": "Quarantined by reviewer",
                "session_family_manual_review_reviewer_label": "Owner",
                "decision_status_summary": "Session remains locally useful.",
                "broader_governed_reuse_summary": "Broader carryover is quarantined.",
                "future_reuse_candidacy_summary": "Future broader influence is strongly limited by quarantine.",
                "current_support_coherence_summary": "Contradiction and weak provenance are limiting broader carryover.",
                "carryover_guardrail_summary": "Weak local multiplicity does not simulate approved session-family carryover.",
            },
        },
    }


class GovernanceWorkflowServiceTest(unittest.TestCase):
    @patch("system.services.governance_workflow_service.list_subject_governed_reviews")
    def test_collect_governance_items_surfaces_multilayer_manual_and_derived_attention(self, list_reviews):
        list_reviews.side_effect = lambda **kwargs: [
            {
                "review_origin_label": "manual" if kwargs["subject_type"] != "belief_state" else "derived",
                "active": True,
                "supersedes_review_record_id": "",
                "manual_action_label": "revised_by_reviewer" if kwargs["subject_type"] == "session_family_carryover" else "",
                "review_status_label": "Reviewed and downgraded later" if kwargs["subject_type"] == "session_family_carryover" else "Reviewed and blocked",
                "metadata": {"governance_note": "Reviewer note for workflow coverage."},
            },
            {
                "review_origin_label": "derived",
                "active": kwargs["subject_type"] == "belief_state",
                "supersedes_review_record_id": "older_review" if kwargs["subject_type"] == "session_family_carryover" else "",
                "review_status_label": "Reviewed and approved",
            },
        ]
        items = collect_governance_inbox_items_for_session_item(_session_item())

        self.assertGreaterEqual(len(items), 3)
        subject_types = {item["subject_type"] for item in items}
        self.assertIn("claim", subject_types)
        self.assertIn("belief_state", subject_types)
        self.assertIn("continuity_cluster", subject_types)
        self.assertIn("session_family_carryover", subject_types)
        session_family = next(item for item in items if item["subject_type"] == "session_family_carryover")
        self.assertEqual(session_family["effective_review_origin_label"], "manual")
        self.assertIn("manual review currently governs", session_family["reviewer_attribution_summary"].lower())
        self.assertIn("reviewed", session_family["effective_review_status_label"].lower())
        self.assertIn("reviewer note", session_family["manual_review_note_summary"].lower())
        self.assertIn("reopen/revise history", session_family["manual_review_reopen_revise_summary"].lower())
        self.assertIn("carryover", session_family["carryover_effect_summary"].lower())

    @patch("system.services.governance_workflow_service.list_subject_governed_reviews")
    def test_build_governance_inbox_prioritizes_higher_layer_broader_carryover_risk(self, list_reviews):
        list_reviews.return_value = [{"review_origin_label": "derived", "active": True, "supersedes_review_record_id": ""}]
        inbox = build_governance_inbox([_session_item()])

        self.assertGreaterEqual(inbox["summary"]["item_count"], 3)
        self.assertEqual(inbox["items"][0]["subject_type"], "session_family_carryover")
        self.assertIn("immediate", inbox["items"][0]["priority_label"].lower())
        self.assertGreaterEqual(inbox["summary"]["manual_override_count"], 1)
        self.assertGreaterEqual(inbox["summary"]["blocked_or_quarantined_count"], 1)

    @patch("system.services.governance_workflow_service.list_subject_governed_reviews")
    def test_governance_workbench_selects_requested_item_and_related_items(self, list_reviews):
        list_reviews.return_value = [{"review_origin_label": "derived", "active": True, "supersedes_review_record_id": ""}]
        session_item = _session_item()
        session_item_2 = _session_item()
        session_item_2["session_id"] = "session_2"
        session_item_2["source_name"] = "second_upload.csv"
        session_item_2["scientific_session_truth"]["session_id"] = "session_2"
        workbench = build_governance_workbench(
            session_history={"items": [session_item, session_item_2]},
            selected_item_id="session_family_carryover:session_family::target_1",
            selected_session_id="session_1",
        )

        self.assertEqual(workbench["selected_item"]["subject_type"], "session_family_carryover")
        self.assertTrue(workbench["related_items"])
        self.assertIn("governance", workbench["selected_item"]["detail_url"])

    def test_resolve_governance_subject_context_keeps_claim_and_session_family_separate(self):
        session_item = _session_item()
        truth = session_item["scientific_session_truth"]

        claim_context = resolve_governance_subject_context(
            scientific_truth=truth,
            subject_type="claim",
            subject_id="claim_1",
        )
        session_family_context = resolve_governance_subject_context(
            scientific_truth=truth,
            subject_type="session_family_carryover",
            subject_id="session_family::target_1",
        )

        self.assertEqual(claim_context["subject_type"], "claim")
        self.assertEqual(session_family_context["subject_type"], "session_family_carryover")
        self.assertNotEqual(claim_context["layer_label"], session_family_context["layer_label"])
        self.assertIn("locally useful", claim_context["local_usefulness_summary"].lower())
        self.assertIn("quarantined", session_family_context["broader_carryover_summary"].lower())


if __name__ == "__main__":
    unittest.main()
