from __future__ import annotations

from typing import Any


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _belief_attention_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    claim_items = candidate.get("claim_detail_items") if isinstance(candidate.get("claim_detail_items"), list) else []
    if not claim_items:
        return {
            "belief_attention_signal": 0.0,
            "contradiction_attention_signal": 0.0,
            "unresolved_mixed_structure_signal": 0.0,
            "belief_informed_attention_reason": "",
        }
    strongest = max(
        (item for item in claim_items if isinstance(item, dict)),
        key=lambda item: (
            1.0 if str((((item.get("current_belief_state") or {}) if isinstance(item.get("current_belief_state"), dict) else {}).get("contradiction_pressure") or "")).strip().lower() == "high"
            else 0.8 if str((((item.get("current_belief_state") or {}) if isinstance(item.get("current_belief_state"), dict) else {}).get("contradiction_pressure") or "")).strip().lower() == "moderate"
            else 0.3
        ),
        default={},
    )
    belief_state = strongest.get("current_belief_state") if isinstance(strongest.get("current_belief_state"), dict) else {}
    contradiction_pressure = _clean_text(belief_state.get("contradiction_pressure"), default="none").lower()
    support_balance = _clean_text(belief_state.get("support_balance_summary")).lower()
    rationale = _clean_text(belief_state.get("latest_revision_rationale"))
    contradiction_signal = 1.0 if contradiction_pressure == "high" else 0.78 if contradiction_pressure == "moderate" else 0.35 if contradiction_pressure == "low" else 0.0
    mixed_signal = 0.9 if "mixed" in support_balance or "unresolved" in rationale.lower() else 0.2
    belief_signal = max(contradiction_signal, mixed_signal if _clean_text(belief_state.get("current_state")).lower() == "unresolved" else 0.0)
    return {
        "belief_attention_signal": round(belief_signal, 4),
        "contradiction_attention_signal": round(contradiction_signal, 4),
        "unresolved_mixed_structure_signal": round(mixed_signal, 4),
        "belief_informed_attention_reason": rationale,
    }


def _candidate_attention_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    experiment_items = candidate.get("candidate_experiment_items") if isinstance(candidate.get("candidate_experiment_items"), list) else []
    top_experiment = max(
        (
            item for item in experiment_items
            if isinstance(item, dict)
        ),
        key=lambda item: _safe_float(((item.get("epistemic_priority") or {}) if isinstance(item.get("epistemic_priority"), dict) else {}).get("epistemic_priority_score")),
        default={},
    )
    top_priority = (top_experiment.get("epistemic_priority") or {}) if isinstance(top_experiment.get("epistemic_priority"), dict) else {}
    epistemic_priority_score = _safe_float(top_priority.get("epistemic_priority_score"))
    belief_feedback = _belief_attention_payload(candidate)
    belief_attention_signal = _safe_float(belief_feedback.get("belief_attention_signal"))
    experiment_value = _safe_float(candidate.get("experiment_value"))
    priority_score = _safe_float(candidate.get("priority_score"), default=experiment_value)

    active_attention = (bool(experiment_items) and epistemic_priority_score >= 0.5) or belief_attention_signal >= 0.65
    combined_attention = max(epistemic_priority_score, 0.75 * belief_attention_signal)
    boost = min(0.18, combined_attention * 0.18) if active_attention else 0.0
    surfaced_order_score = experiment_value + boost
    attention_bucket = (
        "epistemic_attention"
        if combined_attention >= 0.75
        else "epistemic_watch"
        if active_attention
        else "policy_ranked"
    )
    reason = (
        _clean_text(top_priority.get("summary_rationale"))
        if epistemic_priority_score >= belief_attention_signal and active_attention
        else _clean_text(belief_feedback.get("belief_informed_attention_reason"))
        if active_attention
        else "Surfaced primarily by the current policy ranking and experiment value."
    )
    ordering_reason = (
        "Foregrounded with a bounded epistemic-attention boost on top of policy experiment value, including contradiction-aware belief feedback."
        if active_attention
        else "Ordered by the current policy ranking without epistemic attention boost."
    )
    return {
        "surfaced_attention_active": active_attention,
        "surfaced_attention_bucket": attention_bucket,
        "surfaced_attention_score": round(epistemic_priority_score, 4),
        "surfaced_attention_boost": round(boost, 4),
        "surfaced_order_score": round(surfaced_order_score, 4),
        "surfaced_attention_reason": reason,
        "surfaced_ordering_reason": ordering_reason,
        "surfaced_attention_request_id": _clean_text(top_experiment.get("request_id")),
        "surfaced_attention_unresolved_state": _clean_text(top_experiment.get("unresolved_state")),
        "belief_attention_signal": belief_feedback.get("belief_attention_signal"),
        "contradiction_attention_signal": belief_feedback.get("contradiction_attention_signal"),
        "unresolved_mixed_structure_signal": belief_feedback.get("unresolved_mixed_structure_signal"),
        "belief_informed_attention_reason": belief_feedback.get("belief_informed_attention_reason"),
        "belief_feedback_mode": "bounded_contradiction_aware_belief_feedback" if active_attention else "inactive",
        "policy_experiment_value": round(experiment_value, 4),
        "policy_priority_score": round(priority_score, 4),
    }


def apply_surfaced_experiment_attention(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for candidate in candidates:
        payload = _candidate_attention_payload(candidate if isinstance(candidate, dict) else {})
        enriched.append({**candidate, **payload})

    enriched.sort(
        key=lambda candidate: (
            0 if candidate.get("surfaced_attention_active") else 1,
            -_safe_float(candidate.get("surfaced_order_score")),
            -_safe_float(candidate.get("priority_score")),
            _safe_float(candidate.get("rank"), default=9999.0),
        )
    )

    summary = {
        "attention_candidate_count": sum(1 for item in enriched if item.get("surfaced_attention_active")),
        "epistemic_attention_count": sum(1 for item in enriched if _clean_text(item.get("surfaced_attention_bucket")) == "epistemic_attention"),
        "epistemic_watch_count": sum(1 for item in enriched if _clean_text(item.get("surfaced_attention_bucket")) == "epistemic_watch"),
        "belief_feedback_count": sum(1 for item in enriched if _safe_float(item.get("belief_attention_signal")) >= 0.65),
        "default_sort": "surfaced_order_score",
        "ordering_mode": "bounded_belief_informed_epistemic_attention_overlay",
        "ordering_summary": "Discovery foregrounding uses a capped epistemic-attention boost on top of policy experiment value, with contradiction-aware belief state contributing when a claim remains unresolved or mixed; underlying policy scores remain visible.",
        "provenance": "bounded_belief_informed_epistemic_attention_overlay" if enriched else "absent",
    }
    return enriched, summary
