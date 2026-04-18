from __future__ import annotations

from typing import Any
from uuid import uuid4

from system.db import ScientificStateRepository


scientific_state_repository = ScientificStateRepository()


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _default_belief_state(*, claim_id: str, session_id: str, workspace_id: str, created_by_user_id: str | None = None) -> dict[str, Any]:
    return {
        "belief_state_id": _make_id("belief"),
        "session_id": session_id,
        "workspace_id": workspace_id,
        "created_by_user_id": created_by_user_id or "",
        "claim_id": claim_id,
        "current_state": "unresolved",
        "current_strength": "tentative",
        "support_basis_summary": "No experimental result has updated this claim yet.",
        "latest_update_id": "",
        "status": "active",
        "provenance_markers": {"belief_origin": "initial_claim_materialization"},
    }


def get_or_create_belief_state(*, claim: dict[str, Any], created_by_user_id: str | None = None) -> dict[str, Any]:
    try:
        return scientific_state_repository.get_belief_state(claim_id=str(claim.get("claim_id") or ""))
    except FileNotFoundError:
        return scientific_state_repository.upsert_belief_state(
            _default_belief_state(
                claim_id=str(claim.get("claim_id") or ""),
                session_id=str(claim.get("session_id") or ""),
                workspace_id=str(claim.get("workspace_id") or ""),
                created_by_user_id=created_by_user_id,
            )
        )


def apply_belief_update(*, claim: dict[str, Any], experiment_result: dict[str, Any], created_by_user_id: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = get_or_create_belief_state(claim=claim, created_by_user_id=created_by_user_id)
    outcome = str(experiment_result.get("outcome") or "").strip().lower()
    rule = "result_unresolved_keeps_claim_tentative"
    next_state = "unresolved"
    next_strength = "tentative"
    summary = "The experimental outcome remains unresolved for this claim."
    if outcome in {"supportive", "confirmed", "positive"}:
        rule = "supportive_result_strengthens_claim"
        next_state = "supported"
        next_strength = "strengthened"
        summary = "A supportive experiment result increased support for this claim."
    elif outcome in {"contradictory", "refuted", "negative"}:
        rule = "contradictory_result_weakens_claim"
        next_state = "challenged"
        next_strength = "weakened"
        summary = "A contradictory experiment result weakened support for this claim."

    updated_state = scientific_state_repository.upsert_belief_state(
        {
            "belief_state_id": str(current.get("belief_state_id") or _make_id("belief")),
            "session_id": str(claim.get("session_id") or ""),
            "workspace_id": str(claim.get("workspace_id") or ""),
            "created_by_user_id": created_by_user_id or str(current.get("created_by_user_id") or ""),
            "claim_id": str(claim.get("claim_id") or ""),
            "current_state": next_state,
            "current_strength": next_strength,
            "support_basis_summary": summary,
            "latest_update_id": "",
            "status": "active",
            "provenance_markers": {"latest_rule": rule},
        }
    )
    update = scientific_state_repository.record_belief_update(
        {
            "update_id": _make_id("belief_update"),
            "session_id": str(claim.get("session_id") or ""),
            "workspace_id": str(claim.get("workspace_id") or ""),
            "created_by_user_id": created_by_user_id or "",
            "claim_id": str(claim.get("claim_id") or ""),
            "result_id": str(experiment_result.get("result_id") or ""),
            "update_reason": summary,
            "pre_belief_state": {
                "current_state": str(current.get("current_state") or ""),
                "current_strength": str(current.get("current_strength") or ""),
            },
            "post_belief_state": {
                "current_state": next_state,
                "current_strength": next_strength,
            },
            "deterministic_rule": rule,
            "provenance_markers": {"result_outcome": outcome},
        }
    )
    updated_state = scientific_state_repository.upsert_belief_state(
        {
            **updated_state,
            "latest_update_id": str(update.get("update_id") or ""),
        }
    )
    return updated_state, update
