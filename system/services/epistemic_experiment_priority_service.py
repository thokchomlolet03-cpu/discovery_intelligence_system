from __future__ import annotations

from typing import Any

from system.db import ScientificStateRepository


scientific_state_repository = ScientificStateRepository()


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _clamp(value: float, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _belief_state_signal(belief_state: dict[str, Any], unresolved_state: str) -> float:
    current_state = _clean_text(belief_state.get("current_state"), default="unresolved").lower()
    unresolved = _clean_text(unresolved_state, default="unknown").lower()
    contradiction_pressure = _clean_text(belief_state.get("contradiction_pressure"), default="none").lower()
    latest_revision_rationale = _clean_text(belief_state.get("latest_revision_rationale")).lower()
    if current_state == "challenged":
        return 1.0
    if contradiction_pressure == "high":
        return 0.98
    if contradiction_pressure == "moderate" and "unresolved" in latest_revision_rationale:
        return 0.95
    if unresolved in {"no_result_recorded", "pending_result", "no_experiment_request"}:
        return 0.95
    if unresolved == "result_recorded_no_belief_update":
        return 0.8
    if current_state == "unresolved":
        return 0.85
    if current_state == "supported":
        return 0.35
    return 0.55


def _contradiction_attention_signal(belief_state: dict[str, Any], claim_links: list[dict[str, Any]]) -> float:
    contradiction_pressure = _clean_text(belief_state.get("contradiction_pressure"), default="none").lower()
    support_balance_summary = _clean_text(belief_state.get("support_balance_summary")).lower()
    weaken_count = sum(1 for link in claim_links if _clean_text(link.get("relation_type")) == "weakens")
    if contradiction_pressure == "high":
        return 1.0
    if contradiction_pressure == "moderate":
        return 0.82 if weaken_count else 0.72
    if contradiction_pressure == "low":
        return 0.35
    if "mixed" in support_balance_summary:
        return 0.6
    return 0.1


def _unresolved_mixed_structure_signal(belief_state: dict[str, Any], unresolved_state: str) -> float:
    current_state = _clean_text(belief_state.get("current_state"), default="unresolved").lower()
    support_balance_summary = _clean_text(belief_state.get("support_balance_summary")).lower()
    latest_revision_rationale = _clean_text(belief_state.get("latest_revision_rationale")).lower()
    if current_state == "unresolved" and ("mixed" in support_balance_summary or "unresolved" in latest_revision_rationale):
        return 0.9
    if _clean_text(unresolved_state).lower() in {"pending_result", "result_recorded_no_belief_update"}:
        return 0.65
    return 0.2


def _support_weakness_signal(claim_links: list[dict[str, Any]]) -> float:
    if not claim_links:
        return 1.0
    relation_counts: dict[str, int] = {}
    for link in claim_links:
        relation = _clean_text(link.get("relation_type"), default="context_only")
        relation_counts[relation] = relation_counts.get(relation, 0) + 1
    support_count = relation_counts.get("supports", 0)
    weakens_count = relation_counts.get("weakens", 0)
    derived_count = relation_counts.get("derived_from", 0)
    context_count = relation_counts.get("context_only", 0)
    total = sum(relation_counts.values())
    if weakens_count > 0 and support_count == 0:
        return 0.95
    if support_count == 0 and derived_count > 0 and context_count <= 1:
        return 0.9
    if support_count == 0:
        return 0.8 if total <= 2 else 0.65
    if support_count == 1 and total <= 2:
        return 0.6
    return 0.3


def _context_thinness_signal(claim_links: list[dict[str, Any]], snapshot: list[dict[str, Any]]) -> float:
    total = max(len(claim_links), len(snapshot))
    if total <= 0:
        return 1.0
    if total == 1:
        return 0.85
    if total == 2:
        return 0.65
    if total == 3:
        return 0.45
    return 0.25


def _belief_change_opportunity_signal(
    *,
    unresolved_state: str,
    expected_learning_value: str,
    experiment_intent: str,
    result_count: int,
    has_belief_update: bool,
) -> float:
    unresolved = _clean_text(unresolved_state, default="unknown").lower()
    learning_text = _clean_text(expected_learning_value).lower()
    intent = _clean_text(experiment_intent).lower()
    signal = 0.5
    if unresolved in {"no_result_recorded", "pending_result", "no_experiment_request"}:
        signal = 0.9
    elif unresolved == "result_recorded_no_belief_update":
        signal = 0.7
    elif unresolved == "belief_updated":
        signal = 0.3
    if "reduce uncertainty" in learning_text or "clarif" in learning_text or "revise" in learning_text:
        signal += 0.05
    if intent == "claim_test":
        signal += 0.05
    if result_count > 0:
        signal -= 0.05
    if has_belief_update:
        signal -= 0.1
    return _clamp(signal)


def _session_relevance_multiplier(claim: dict[str, Any]) -> float:
    claim_scope = _clean_text(claim.get("claim_scope"), default="unknown").lower()
    if claim_scope == "candidate":
        return 1.0
    if claim_scope == "run":
        return 0.8
    return 0.9


def _priority_band(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _summary_rationale(
    *,
    unresolved_claim_signal: float,
    support_weakness_signal: float,
    belief_change_opportunity_signal: float,
    context_thinness_signal: float,
    contradiction_attention_signal: float,
    unresolved_mixed_structure_signal: float,
    belief_state: dict[str, Any],
    claim_links: list[dict[str, Any]],
) -> str:
    parts: list[str] = []
    if unresolved_claim_signal >= 0.8:
        parts.append("the claim remains unresolved in the current session")
    if contradiction_attention_signal >= 0.75:
        parts.append("contradiction-aware belief state still shows active pressure")
    if support_weakness_signal >= 0.8:
        parts.append("attached support is still weak or one-sided")
    if unresolved_mixed_structure_signal >= 0.8:
        parts.append("belief remains unresolved because the attached structure is mixed")
    if context_thinness_signal >= 0.8:
        parts.append("very little claim context is attached")
    if belief_change_opportunity_signal >= 0.8:
        parts.append("the next result is likely to change the session's epistemic stance")
    if not parts and _clean_text(belief_state.get("current_state")).lower() == "supported" and _clean_text(belief_state.get("contradiction_pressure")).lower() == "low":
        parts.append("the claim appears more settled and contradiction pressure is currently low")
    if not parts and claim_links:
        parts.append("the claim still deserves follow-up against its current attached context")
    if not parts:
        return "Heuristic epistemic priority is limited because little claim context is currently persisted."
    return "Prioritized because " + ", ".join(parts[:3]) + "."


def assess_epistemic_experiment_priority(
    *,
    request: dict[str, Any],
    claim: dict[str, Any] | None,
    belief_state: dict[str, Any] | None,
    claim_links: list[dict[str, Any]] | None,
    unresolved_state: str,
    result_count: int,
    has_belief_update: bool,
) -> dict[str, Any]:
    claim_payload = claim if isinstance(claim, dict) else {}
    belief_payload = belief_state if isinstance(belief_state, dict) else {}
    links = claim_links if isinstance(claim_links, list) else []
    snapshot = request.get("linked_claim_evidence_snapshot") if isinstance(request.get("linked_claim_evidence_snapshot"), list) else []

    unresolved_claim_signal = _belief_state_signal(belief_payload, unresolved_state)
    support_weakness_signal = _support_weakness_signal(links)
    context_thinness_signal = _context_thinness_signal(links, snapshot)
    contradiction_attention_signal = _contradiction_attention_signal(belief_payload, links)
    unresolved_mixed_structure_signal = _unresolved_mixed_structure_signal(belief_payload, unresolved_state)
    belief_change_opportunity_signal = _belief_change_opportunity_signal(
        unresolved_state=unresolved_state,
        expected_learning_value=_clean_text(request.get("expected_learning_value")),
        experiment_intent=_clean_text(request.get("experiment_intent")),
        result_count=result_count,
        has_belief_update=has_belief_update,
    )
    relevance_multiplier = _session_relevance_multiplier(claim_payload)
    score = _clamp(
        (
            0.26 * unresolved_claim_signal
            + 0.18 * support_weakness_signal
            + 0.22 * belief_change_opportunity_signal
            + 0.10 * context_thinness_signal
            + 0.14 * contradiction_attention_signal
            + 0.10 * unresolved_mixed_structure_signal
        )
        * relevance_multiplier
    )
    return {
        "claim_id": _clean_text(request.get("claim_id") or request.get("tested_claim_id")),
        "experiment_request_id": _clean_text(request.get("request_id")),
        "epistemic_priority_score": round(score, 4),
        "epistemic_priority_band": _priority_band(score),
        "unresolved_claim_signal": round(unresolved_claim_signal, 4),
        "support_weakness_signal": round(support_weakness_signal, 4),
        "belief_change_opportunity_signal": round(belief_change_opportunity_signal, 4),
        "context_thinness_signal": round(context_thinness_signal, 4),
        "belief_attention_signal": round(_belief_state_signal(belief_payload, unresolved_state), 4),
        "contradiction_attention_signal": round(contradiction_attention_signal, 4),
        "unresolved_mixed_structure_signal": round(unresolved_mixed_structure_signal, 4),
        "belief_informed_attention_reason": _clean_text(belief_payload.get("latest_revision_rationale")),
        "summary_rationale": _summary_rationale(
            unresolved_claim_signal=unresolved_claim_signal,
            support_weakness_signal=support_weakness_signal,
            belief_change_opportunity_signal=belief_change_opportunity_signal,
            context_thinness_signal=context_thinness_signal,
            contradiction_attention_signal=contradiction_attention_signal,
            unresolved_mixed_structure_signal=unresolved_mixed_structure_signal,
            belief_state=belief_payload,
            claim_links=links,
        ),
        "heuristic_mode": "bounded_belief_informed_epistemic_priority",
    }


def build_session_epistemic_experiment_priority_model(*, session_id: str, workspace_id: str | None = None) -> dict[str, Any]:
    claims = scientific_state_repository.list_claims(session_id=session_id, workspace_id=workspace_id)
    requests = scientific_state_repository.list_experiment_requests(session_id=session_id)
    requests = [item for item in requests if workspace_id is None or _clean_text(item.get("workspace_id")) == workspace_id]
    claim_lookup = {_clean_text(item.get("claim_id")): item for item in claims if _clean_text(item.get("claim_id"))}
    links = scientific_state_repository.list_claim_evidence_links(session_id=session_id, workspace_id=workspace_id)
    links_by_claim: dict[str, list[dict[str, Any]]] = {}
    for item in links:
        claim_id = _clean_text(item.get("claim_id"))
        if claim_id:
            links_by_claim.setdefault(claim_id, []).append(item)

    items: list[dict[str, Any]] = []
    for request in requests:
        claim_id = _clean_text(request.get("claim_id"))
        results = scientific_state_repository.list_experiment_results(request_id=_clean_text(request.get("request_id")))
        updates: list[dict[str, Any]] = []
        for result in results:
            updates.extend(scientific_state_repository.list_belief_updates(result_id=_clean_text(result.get("result_id"))))
        try:
            belief_state = scientific_state_repository.get_belief_state(claim_id=claim_id) if claim_id else {}
        except FileNotFoundError:
            belief_state = {}
        unresolved_state = "belief_updated" if updates else "result_recorded_no_belief_update" if results else "no_result_recorded"
        items.append(
            assess_epistemic_experiment_priority(
                request=request,
                claim=claim_lookup.get(claim_id),
                belief_state=belief_state,
                claim_links=links_by_claim.get(claim_id, []),
                unresolved_state=unresolved_state,
                result_count=len(results),
                has_belief_update=bool(updates),
            )
        )

    high_priority_count = sum(1 for item in items if _clean_text(item.get("epistemic_priority_band")) == "high")
    return {
        "session_summary": {
            "experiment_request_count": len(items),
            "high_priority_count": high_priority_count,
            "medium_priority_count": sum(1 for item in items if _clean_text(item.get("epistemic_priority_band")) == "medium"),
            "low_priority_count": sum(1 for item in items if _clean_text(item.get("epistemic_priority_band")) == "low"),
            "has_epistemic_priorities": bool(items),
            "absence_reason": "" if items else "no_claim_linked_experiment_opportunities",
            "provenance": "bounded_epistemic_priority" if items else "absent",
        },
        "items": items,
    }
