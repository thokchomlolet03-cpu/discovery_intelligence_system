import unittest

from system.services.workspace_feedback_service import (
    annotate_candidates_with_workspace_memory,
    build_workspace_feedback_summary,
)


def review_event(
    *,
    session_id: str,
    smiles: str,
    action: str,
    status: str,
    reviewed_at: str,
    note: str = "",
    reviewer: str = "qa",
) -> dict:
    return {
        "session_id": session_id,
        "workspace_id": "workspace_1",
        "candidate_id": smiles,
        "smiles": smiles,
        "action": action,
        "previous_status": "",
        "status": status,
        "note": note,
        "timestamp": reviewed_at,
        "reviewed_at": reviewed_at,
        "actor": reviewer,
        "reviewer": reviewer,
        "actor_user_id": "",
        "metadata": {},
    }


class WorkspaceFeedbackServiceTest(unittest.TestCase):
    def test_annotate_candidates_with_workspace_memory_excludes_current_session(self):
        candidates = [
            {"candidate_id": "cand_1", "smiles": "CCO", "canonical_smiles": "CCO"},
            {"candidate_id": "cand_2", "smiles": "CCN", "canonical_smiles": "CCN"},
        ]
        reviews = [
            review_event(
                session_id="session_old",
                smiles="CCO",
                action="approve",
                status="approved",
                reviewed_at="2026-03-29T10:00:00+00:00",
                note="Carry this forward.",
            ),
            review_event(
                session_id="session_current",
                smiles="CCO",
                action="later",
                status="under review",
                reviewed_at="2026-03-30T10:00:00+00:00",
                note="Current-session review should not count as prior memory.",
            ),
        ]

        annotated = annotate_candidates_with_workspace_memory(
            candidates,
            session_id="session_current",
            workspace_id="workspace_1",
            review_events=reviews,
            session_labels={"session_old": "Baseline session"},
        )

        self.assertEqual(annotated[0]["workspace_memory_count"], 1)
        self.assertEqual(annotated[0]["workspace_memory"]["last_status"], "approved")
        self.assertEqual(annotated[0]["workspace_memory"]["last_session_label"], "Baseline session")
        self.assertEqual(annotated[1]["workspace_memory_count"], 0)

    def test_build_workspace_feedback_summary_tracks_focus_carryover_and_latest_events(self):
        focus_candidates = [
            {"candidate_id": "cand_1", "smiles": "CCO", "canonical_smiles": "CCO"},
            {"candidate_id": "cand_2", "smiles": "CCN", "canonical_smiles": "CCN"},
        ]
        reviews = [
            review_event(
                session_id="session_old",
                smiles="CCO",
                action="approve",
                status="approved",
                reviewed_at="2026-03-28T09:00:00+00:00",
                note="Approved in the baseline run.",
            ),
            review_event(
                session_id="session_other",
                smiles="CCCl",
                action="reject",
                status="rejected",
                reviewed_at="2026-03-29T12:30:00+00:00",
                note="Rejected elsewhere.",
            ),
        ]

        summary = build_workspace_feedback_summary(
            workspace_id="workspace_1",
            focus_session_id="session_current",
            focus_candidates=focus_candidates,
            review_events=reviews,
            session_labels={
                "session_old": "Baseline session",
                "session_other": "Exploration session",
            },
        )

        self.assertEqual(summary["event_count"], 2)
        self.assertEqual(summary["candidate_count"], 2)
        self.assertEqual(summary["focus_memory"]["matched_candidate_count"], 1)
        self.assertIn("earlier workspace session", summary["focus_memory"]["summary"])
        self.assertEqual(summary["focus_memory"]["matches"][0]["last_session_label"], "Baseline session")
        self.assertEqual(summary["latest_events"][0]["session_label"], "Exploration session")


if __name__ == "__main__":
    unittest.main()
