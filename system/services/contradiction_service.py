from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _belief_transition_conflict_type(update: dict[str, Any]) -> str:
    deterministic_rule = _clean_text(update.get("deterministic_rule")).lower()
    if "contradict" in deterministic_rule:
        return "belief_transition_conflict"
    return "belief_transition_conflict"


def build_session_contradictions(
    *,
    session_id: str,
    workspace_id: str,
    created_by_user_id: str | None,
    claims: list[dict[str, Any]],
    claim_evidence_links: list[dict[str, Any]],
    experiment_results: list[dict[str, Any]],
    belief_updates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    claim_ids = {_clean_text(item.get("claim_id")) for item in claims if _clean_text(item.get("claim_id"))}
    contradictions: list[dict[str, Any]] = []

    for link in claim_evidence_links:
        claim_id = _clean_text(link.get("claim_id"))
        relation_type = _clean_text(link.get("relation_type"))
        if claim_id not in claim_ids or relation_type != "weakens":
            continue
        linked_object_type = _clean_text(link.get("linked_object_type"))
        contradiction_type = "evidence_vs_claim" if linked_object_type == "evidence" else "support_structure_conflict"
        contradictions.append(
            {
                "contradiction_id": _make_id("contradiction"),
                "session_id": session_id,
                "workspace_id": workspace_id,
                "created_by_user_id": created_by_user_id or "",
                "claim_id": claim_id,
                "contradiction_scope": "claim",
                "contradiction_type": contradiction_type,
                "source_object_type": linked_object_type or "evidence",
                "source_object_id": _clean_text(link.get("linked_object_id")),
                "status": "active",
                "summary": _clean_text(link.get("summary"), default="A weakening support line is attached to this claim."),
                "provenance_markers": {"materialization_source": "claim_evidence_link", "relation_type": relation_type},
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            }
        )

    for result in experiment_results:
        claim_id = _clean_text(result.get("claim_id"))
        outcome = _clean_text(result.get("outcome")).lower()
        if claim_id not in claim_ids or outcome != "contradictory":
            continue
        contradictions.append(
            {
                "contradiction_id": _make_id("contradiction"),
                "session_id": session_id,
                "workspace_id": workspace_id,
                "created_by_user_id": created_by_user_id or "",
                "claim_id": claim_id,
                "contradiction_scope": "claim",
                "contradiction_type": "result_vs_claim",
                "source_object_type": "experiment_result",
                "source_object_id": _clean_text(result.get("result_id")),
                "status": "active",
                "summary": _clean_text(((result.get("result_summary") or {}) if isinstance(result.get("result_summary"), dict) else {}).get("summary"))
                or _clean_text(((result.get("result_summary") or {}) if isinstance(result.get("result_summary"), dict) else {}).get("note"))
                or "A recorded experiment result contradicts the linked claim.",
                "provenance_markers": {"materialization_source": "experiment_result", "outcome": outcome},
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            }
        )

    for update in belief_updates:
        claim_id = _clean_text(update.get("claim_id"))
        post_state = (update.get("post_belief_state") or {}) if isinstance(update.get("post_belief_state"), dict) else {}
        current_state = _clean_text(post_state.get("current_state")).lower()
        deterministic_rule = _clean_text(update.get("deterministic_rule")).lower()
        if claim_id not in claim_ids:
            continue
        if current_state != "challenged" and "contradict" not in deterministic_rule:
            continue
        contradictions.append(
            {
                "contradiction_id": _make_id("contradiction"),
                "session_id": session_id,
                "workspace_id": workspace_id,
                "created_by_user_id": created_by_user_id or "",
                "claim_id": claim_id,
                "contradiction_scope": "claim",
                "contradiction_type": _belief_transition_conflict_type(update),
                "source_object_type": "belief_update",
                "source_object_id": _clean_text(update.get("update_id")),
                "status": "unresolved",
                "summary": _clean_text(update.get("update_reason"), default="A belief transition challenges the linked claim."),
                "provenance_markers": {"materialization_source": "belief_update", "deterministic_rule": deterministic_rule},
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            }
        )

    return contradictions
