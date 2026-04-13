import os
import tempfile
import unittest
from pathlib import Path

from system.db import ensure_database_ready, reset_database_state
from system.services.governed_review_service import (
    REVIEW_ORIGIN_DERIVED,
    REVIEW_ORIGIN_MANUAL,
    SUBJECT_TYPE_BELIEF_STATE,
    build_governed_review_overlay,
    list_subject_governed_reviews,
    record_manual_subject_governed_review_action,
    sync_subject_governed_review_snapshot,
)


class GovernedReviewServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        reset_database_state(f"sqlite:///{Path(self.tmpdir.name) / 'governed_review.db'}")
        ensure_database_ready()

    def tearDown(self):
        reset_database_state()
        os.environ.pop("DISCOVERY_ALLOWED_ARTIFACT_ROOTS", None)
        self.tmpdir.cleanup()

    def _derived_snapshot(self) -> dict[str, str]:
        return {
            "workspace_id": "workspace_1",
            "session_id": "session_1",
            "subject_type": SUBJECT_TYPE_BELIEF_STATE,
            "subject_id": "belief::target_1",
            "target_key": "target_1",
            "source_class_label": "Internal governed experimental source",
            "provenance_confidence_label": "Strong provenance",
            "trust_tier_label": "Governed-trusted evidence",
            "review_status_label": "Reviewed and approved",
            "review_reason_label": "Approved for bounded broader consideration",
            "review_reason_summary": "Derived posture says this belief-state is strong enough for bounded broader carryover consideration.",
            "promotion_gate_status_label": "Promotable under bounded governed rules",
            "promotion_block_reason_label": "No material promotion block recorded",
            "decision_summary": "Belief-state broader carryover is approved under derived bridge-state governance.",
            "recorded_by": "scientific_session_truth",
        }

    def test_manual_override_becomes_effective_while_derived_snapshot_stays_visible(self):
        sync_subject_governed_review_snapshot(self._derived_snapshot())
        record_manual_subject_governed_review_action(
            {
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "subject_type": SUBJECT_TYPE_BELIEF_STATE,
                "subject_id": "belief::target_1",
                "target_key": "target_1",
                "source_class_label": "Internal governed experimental source",
                "provenance_confidence_label": "Strong provenance",
                "trust_tier_label": "Governed-trusted evidence",
                "review_status_label": "Reviewed and blocked",
                "review_reason_label": "Contradiction-heavy current posture",
                "review_reason_summary": "Owner manually blocked broader carryover after reviewing contradiction-heavy current posture.",
                "promotion_gate_status_label": "Promotable under bounded governed rules",
                "promotion_block_reason_label": "No material promotion block recorded",
                "decision_summary": "Belief-state broader carryover is manually blocked under bounded human review.",
                "reviewer_label": "Owner",
                "recorded_by": "Owner",
            }
        )

        records = list_subject_governed_reviews(
            workspace_id="workspace_1",
            subject_type=SUBJECT_TYPE_BELIEF_STATE,
            subject_id="belief::target_1",
        )
        overlay = build_governed_review_overlay(records, subject_label="This belief-state posture")
        active_records = [record for record in records if record.get("active")]

        self.assertEqual(len(records), 2)
        self.assertEqual(len(active_records), 2)
        self.assertEqual(overlay["effective_governed_review_origin_label"], REVIEW_ORIGIN_MANUAL)
        self.assertEqual(overlay["governed_review_status_label"], "Reviewed and blocked")
        self.assertEqual(overlay["derived_governed_review_status_label"], "Reviewed and approved")
        self.assertEqual(overlay["manual_governed_review_status_label"], "Reviewed and blocked")
        self.assertEqual(overlay["manual_governed_review_action_label"], "Blocked by reviewer")
        self.assertEqual(overlay["manual_governed_review_reviewer_label"], "Owner")
        self.assertEqual(overlay["trust_tier_label"], "Governed-trusted evidence")
        self.assertEqual(overlay["provenance_confidence_label"], "Strong provenance")

    def test_later_manual_review_supersedes_earlier_manual_review_without_erasing_derived_history(self):
        sync_subject_governed_review_snapshot(self._derived_snapshot())
        first_manual = record_manual_subject_governed_review_action(
            {
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "subject_type": SUBJECT_TYPE_BELIEF_STATE,
                "subject_id": "belief::target_1",
                "target_key": "target_1",
                "source_class_label": "Internal governed experimental source",
                "provenance_confidence_label": "Strong provenance",
                "trust_tier_label": "Governed-trusted evidence",
                "review_status_label": "Reviewed and deferred",
                "review_reason_label": "Stronger trust still needed",
                "review_reason_summary": "Owner manually deferred broader carryover pending stronger trust.",
                "promotion_gate_status_label": "Promotable under bounded governed rules",
                "promotion_block_reason_label": "No material promotion block recorded",
                "decision_summary": "Belief-state broader carryover is manually deferred under bounded human review.",
                "reviewer_label": "Owner",
                "recorded_by": "Owner",
            }
        )
        second_manual = record_manual_subject_governed_review_action(
            {
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "subject_type": SUBJECT_TYPE_BELIEF_STATE,
                "subject_id": "belief::target_1",
                "target_key": "target_1",
                "source_class_label": "Internal governed experimental source",
                "provenance_confidence_label": "Strong provenance",
                "trust_tier_label": "Governed-trusted evidence",
                "review_status_label": "Reviewed and approved",
                "review_reason_label": "Approved for bounded broader consideration",
                "review_reason_summary": "Owner manually approved bounded broader carryover after review.",
                "promotion_gate_status_label": "Promotable under bounded governed rules",
                "promotion_block_reason_label": "No material promotion block recorded",
                "decision_summary": "Belief-state broader carryover is manually approved under bounded human review.",
                "reviewer_label": "Owner",
                "recorded_by": "Owner",
            }
        )

        records = list_subject_governed_reviews(
            workspace_id="workspace_1",
            subject_type=SUBJECT_TYPE_BELIEF_STATE,
            subject_id="belief::target_1",
        )
        overlay = build_governed_review_overlay(records, subject_label="This belief-state posture")
        active_manual = [
            record
            for record in records
            if record.get("active") and record.get("review_origin_label") == REVIEW_ORIGIN_MANUAL
        ]

        self.assertNotEqual(first_manual["review_record_id"], second_manual["review_record_id"])
        self.assertEqual(len(records), 3)
        self.assertEqual(len(active_manual), 1)
        self.assertEqual(active_manual[0]["review_record_id"], second_manual["review_record_id"])
        self.assertEqual(overlay["effective_governed_review_origin_label"], REVIEW_ORIGIN_MANUAL)
        self.assertEqual(overlay["governed_review_status_label"], "Reviewed and approved")
        self.assertEqual(overlay["manual_governed_review_status_label"], "Reviewed and approved")
        self.assertEqual(overlay["derived_governed_review_status_label"], "Reviewed and approved")
        self.assertIn("superseded", overlay["manual_governed_review_history_summary"].lower())
        self.assertIn("manually reviewed", overlay["governed_review_history_summary"].lower())

    def test_manual_note_and_reopen_revise_history_are_visible_without_erasing_effective_posture(self):
        sync_subject_governed_review_snapshot(self._derived_snapshot())
        record_manual_subject_governed_review_action(
            {
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "subject_type": SUBJECT_TYPE_BELIEF_STATE,
                "subject_id": "belief::target_1",
                "target_key": "target_1",
                "source_class_label": "Internal governed experimental source",
                "provenance_confidence_label": "Strong provenance",
                "trust_tier_label": "Governed-trusted evidence",
                "review_status_label": "Reviewed and deferred",
                "review_reason_label": "Stronger trust still needed",
                "review_reason_summary": "Owner reopened broader carryover for reconsideration.",
                "promotion_gate_status_label": "Promotable under bounded governed rules",
                "promotion_block_reason_label": "No material promotion block recorded",
                "decision_summary": "Belief-state broader carryover is reopened for reconsideration.",
                "reviewer_label": "Owner",
                "recorded_by": "Owner",
                "manual_action_label": "reopened_for_review",
                "metadata": {"governance_note": "Fresh supporting assay reopened this layer for review."},
            }
        )
        record_manual_subject_governed_review_action(
            {
                "workspace_id": "workspace_1",
                "session_id": "session_1",
                "subject_type": SUBJECT_TYPE_BELIEF_STATE,
                "subject_id": "belief::target_1",
                "target_key": "target_1",
                "source_class_label": "Internal governed experimental source",
                "provenance_confidence_label": "Strong provenance",
                "trust_tier_label": "Governed-trusted evidence",
                "review_status_label": "Reviewed and approved",
                "review_reason_label": "Approved for bounded broader consideration",
                "review_reason_summary": "Owner revised the posture into bounded approval.",
                "promotion_gate_status_label": "Promotable under bounded governed rules",
                "promotion_block_reason_label": "No material promotion block recorded",
                "decision_summary": "Belief-state broader carryover is manually revised into approval.",
                "reviewer_label": "Owner",
                "recorded_by": "Owner",
                "manual_action_label": "revised_by_reviewer",
                "metadata": {"governance_note": "Earlier block no longer fits the stronger support picture."},
            }
        )

        records = list_subject_governed_reviews(
            workspace_id="workspace_1",
            subject_type=SUBJECT_TYPE_BELIEF_STATE,
            subject_id="belief::target_1",
        )
        overlay = build_governed_review_overlay(records, subject_label="This belief-state posture")

        self.assertEqual(overlay["manual_governed_review_action_label"], "Revised by reviewer")
        self.assertIn("stronger support picture", overlay["manual_governed_review_note_summary"].lower())
        self.assertIn("reopen/revise history", overlay["manual_governed_review_reopen_revise_summary"].lower())
        self.assertIn("consistent manual override", overlay["governed_review_consistency_label"].lower())
        self.assertIn("broader carryover", overlay["effective_carryover_effect_summary"].lower())


if __name__ == "__main__":
    unittest.main()
