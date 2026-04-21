from __future__ import annotations

from typing import Any
from uuid import uuid4

from system.db import ScientificStateRepository


scientific_state_repository = ScientificStateRepository()


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


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
        "contradiction_pressure": "none",
        "support_balance_summary": "No attached support or weakening lines are recorded yet.",
        "latest_revision_rationale": "Belief remains unresolved until evidence, contradiction, or experiment structure changes.",
        "latest_update_id": "",
        "status": "active",
        "provenance_markers": {"belief_origin": "initial_claim_materialization", "revision_mode": "bounded_contradiction_aware"},
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


def _support_counts(claim_links: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"supports": 0, "weakens": 0, "context_only": 0, "derived_from": 0}
    for item in claim_links:
        relation_type = _clean_text(item.get("relation_type"), default="context_only")
        counts[relation_type] = counts.get(relation_type, 0) + 1
    return counts


def _support_balance_summary(counts: dict[str, int]) -> str:
    support_count = counts.get("supports", 0)
    weaken_count = counts.get("weakens", 0)
    context_count = counts.get("context_only", 0)
    derived_count = counts.get("derived_from", 0)
    parts = [
        f"{support_count} supporting line(s)",
        f"{weaken_count} weakening line(s)",
        f"{context_count} context-only line(s)",
        f"{derived_count} derived line(s)",
    ]
    if support_count and not weaken_count:
        return ", ".join(parts) + "; current attached structure leans supportive."
    if weaken_count and not support_count:
        return ", ".join(parts) + "; current attached structure leans weakening."
    if support_count and weaken_count:
        return ", ".join(parts) + "; current attached structure is mixed."
    return ", ".join(parts) + "; attached structure remains thin."


def _pressure_label(active_contradictions: int, weaken_count: int, outcome: str) -> str:
    if outcome == "contradictory" and (active_contradictions > 0 or weaken_count > 0):
        return "high"
    if active_contradictions > 1 or weaken_count > 1:
        return "high"
    if active_contradictions > 0 or weaken_count > 0:
        return "moderate"
    return "low" if outcome == "supportive" else "none"


def _source_summary(*, outcome: str, counts: dict[str, int], active_contradictions: list[dict[str, Any]], prior_updates: list[dict[str, Any]]) -> str:
    contradiction_count = len(active_contradictions)
    support_count = counts.get("supports", 0)
    weaken_count = counts.get("weakens", 0)
    prior_count = len(prior_updates)
    parts = [f"Result outcome: {outcome or 'unresolved'}."]
    parts.append(f"Attached support structure: {support_count} supports / {weaken_count} weakens.")
    if contradiction_count:
        parts.append(f"Active contradiction lines before revision: {contradiction_count}.")
    if prior_count:
        parts.append(f"Prior belief updates recorded: {prior_count}.")
    return " ".join(parts)


def assess_belief_revision(
    *,
    claim: dict[str, Any],
    experiment_result: dict[str, Any],
    current_belief_state: dict[str, Any],
    contradictions: list[dict[str, Any]],
    claim_links: list[dict[str, Any]],
    prior_updates: list[dict[str, Any]],
) -> dict[str, Any]:
    outcome = _clean_text(experiment_result.get("outcome")).lower()
    counts = _support_counts(claim_links)
    active_contradictions = [
        item
        for item in contradictions
        if _clean_text(item.get("status"), default="unresolved") in {"active", "unresolved"}
    ]
    active_ids = [_clean_text(item.get("contradiction_id")) for item in active_contradictions if _clean_text(item.get("contradiction_id"))]
    support_count = counts.get("supports", 0)
    weaken_count = counts.get("weakens", 0)
    current_state = _clean_text(current_belief_state.get("current_state"), default="unresolved")
    contradiction_pressure = _pressure_label(len(active_contradictions), weaken_count, outcome)
    support_balance_summary = _support_balance_summary(counts)
    source_summary = _source_summary(
        outcome=outcome,
        counts=counts,
        active_contradictions=active_contradictions,
        prior_updates=prior_updates,
    )

    rule = "contradiction_aware_unresolved_retention"
    next_state = "unresolved"
    next_strength = "tentative"
    rationale = "Belief remains unresolved because the current result and attached claim structure do not yet settle the contradiction pressure around this claim."
    support_basis_summary = rationale

    if outcome in {"supportive", "confirmed", "positive"}:
        if contradiction_pressure in {"moderate", "high"} or weaken_count > 0:
            rule = "supportive_result_preserves_unresolved_under_contradiction_pressure"
            next_state = "unresolved"
            next_strength = "mixed"
            rationale = "A supportive result was recorded, but active contradiction or weakening structure remains attached to the claim, so belief stays unresolved."
        else:
            rule = "supportive_result_strengthens_claim_with_low_contradiction_pressure"
            next_state = "supported"
            next_strength = "strengthened" if support_count > 0 or current_state == "supported" else "tentative"
            rationale = "A supportive result increased support for this claim because contradiction pressure is currently low and no weakening line remains active."
        support_basis_summary = rationale
    elif outcome in {"contradictory", "refuted", "negative"}:
        if support_count > 0 and not active_contradictions:
            rule = "contradictory_result_keeps_claim_unresolved_under_mixed_support"
            next_state = "unresolved"
            next_strength = "mixed"
            rationale = "A contradictory result was recorded, but the claim still retains supporting structure, so belief moves into mixed unresolved state rather than collapsing immediately."
        else:
            rule = "contradictory_result_challenges_claim_under_contradiction_pressure"
            next_state = "challenged"
            next_strength = "weakened"
            rationale = "A contradictory result intensified the current contradiction pressure around this claim and moves belief toward challenged."
        support_basis_summary = rationale
    else:
        if current_state == "supported" and contradiction_pressure == "none":
            rule = "noncommittal_result_preserves_prior_supported_state"
            next_state = "supported"
            next_strength = _clean_text(current_belief_state.get("current_strength"), default="tentative")
            rationale = "The new result does not introduce new contradiction pressure and does not materially revise the prior supported state."
            support_basis_summary = rationale

    return {
        "revision_mode": "bounded_contradiction_aware",
        "deterministic_rule": rule,
        "current_state": next_state,
        "current_strength": next_strength,
        "support_basis_summary": support_basis_summary,
        "contradiction_pressure": contradiction_pressure,
        "support_balance_summary": support_balance_summary,
        "revision_rationale": rationale,
        "triggering_contradiction_ids": active_ids,
        "triggering_source_summary": source_summary,
        "provenance_markers": {
            "result_outcome": outcome,
            "active_contradiction_count": len(active_contradictions),
            "support_count": support_count,
            "weaken_count": weaken_count,
            "prior_update_count": len(prior_updates),
        },
    }


def apply_belief_update(*, claim: dict[str, Any], experiment_result: dict[str, Any], created_by_user_id: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    current = get_or_create_belief_state(claim=claim, created_by_user_id=created_by_user_id)
    claim_id = str(claim.get("claim_id") or "")
    contradictions = scientific_state_repository.list_contradictions(claim_id=claim_id)
    claim_links = scientific_state_repository.list_claim_evidence_links(claim_id=claim_id)
    prior_updates = scientific_state_repository.list_belief_updates(claim_id=claim_id)
    revision = assess_belief_revision(
        claim=claim,
        experiment_result=experiment_result,
        current_belief_state=current,
        contradictions=contradictions,
        claim_links=claim_links,
        prior_updates=prior_updates,
    )

    updated_state = scientific_state_repository.upsert_belief_state(
        {
            "belief_state_id": str(current.get("belief_state_id") or _make_id("belief")),
            "session_id": str(claim.get("session_id") or ""),
            "workspace_id": str(claim.get("workspace_id") or ""),
            "created_by_user_id": created_by_user_id or str(current.get("created_by_user_id") or ""),
            "claim_id": claim_id,
            "current_state": revision["current_state"],
            "current_strength": revision["current_strength"],
            "support_basis_summary": revision["support_basis_summary"],
            "contradiction_pressure": revision["contradiction_pressure"],
            "support_balance_summary": revision["support_balance_summary"],
            "latest_revision_rationale": revision["revision_rationale"],
            "latest_update_id": "",
            "status": "active",
            "provenance_markers": {
                "latest_rule": revision["deterministic_rule"],
                "revision_mode": revision["revision_mode"],
                **revision["provenance_markers"],
            },
        }
    )
    update = scientific_state_repository.record_belief_update(
        {
            "update_id": _make_id("belief_update"),
            "session_id": str(claim.get("session_id") or ""),
            "workspace_id": str(claim.get("workspace_id") or ""),
            "created_by_user_id": created_by_user_id or "",
            "claim_id": claim_id,
            "result_id": str(experiment_result.get("result_id") or ""),
            "update_reason": revision["support_basis_summary"],
            "pre_belief_state": {
                "current_state": _clean_text(current.get("current_state")),
                "current_strength": _clean_text(current.get("current_strength")),
                "contradiction_pressure": _clean_text(current.get("contradiction_pressure"), default="none"),
            },
            "post_belief_state": {
                "current_state": revision["current_state"],
                "current_strength": revision["current_strength"],
                "contradiction_pressure": revision["contradiction_pressure"],
            },
            "deterministic_rule": revision["deterministic_rule"],
            "revision_mode": revision["revision_mode"],
            "contradiction_pressure": revision["contradiction_pressure"],
            "support_balance_summary": revision["support_balance_summary"],
            "revision_rationale": revision["revision_rationale"],
            "triggering_contradiction_ids": revision["triggering_contradiction_ids"],
            "triggering_source_summary": revision["triggering_source_summary"],
            "provenance_markers": revision["provenance_markers"],
        }
    )
    updated_state = scientific_state_repository.upsert_belief_state(
        {
            **updated_state,
            "latest_update_id": str(update.get("update_id") or ""),
        }
    )
    return updated_state, update
