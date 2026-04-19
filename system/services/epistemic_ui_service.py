from __future__ import annotations

from typing import Any


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _choice_label(prefix: str, identifier: str, fallback_index: int, summary: str) -> str:
    label = _clean_text(summary)
    if label:
        return label
    clean_identifier = _clean_text(identifier)
    if clean_identifier:
        return f"{prefix} {clean_identifier}"
    return f"{prefix} {fallback_index}"


def _claim_inspection_payload(item: dict[str, Any]) -> dict[str, Any]:
    claim = item.get("claim") if isinstance(item.get("claim"), dict) else {}
    attachment = item.get("attachment_context") if isinstance(item.get("attachment_context"), dict) else {}
    experiment_detail = item.get("experiment_detail") if isinstance(item.get("experiment_detail"), dict) else {}
    belief_update = item.get("belief_update_summary") if isinstance(item.get("belief_update_summary"), dict) else {}
    belief_state = item.get("current_belief_state") if isinstance(item.get("current_belief_state"), dict) else {}
    diagnostics = item.get("diagnostics") if isinstance(item.get("diagnostics"), dict) else {}
    candidate_context = attachment.get("candidate_context") if isinstance(attachment.get("candidate_context"), dict) else {}
    run_context = attachment.get("run_context") if isinstance(attachment.get("run_context"), dict) else {}
    return {
        "claim_id": _clean_text(item.get("claim_id")),
        "claim_type": _clean_text(claim.get("claim_type"), default="unknown"),
        "claim_status": _clean_text(claim.get("claim_status"), default="unknown"),
        "claim_scope": _clean_text(claim.get("claim_scope"), default="unknown"),
        "claim_text": _clean_text(claim.get("claim_text")) or "Claim detail recorded.",
        "support_basis_summary": _clean_text(attachment.get("support_basis_summary")) or "Canonical support basis not recorded.",
        "candidate_label": _clean_text(candidate_context.get("candidate_id") or candidate_context.get("canonical_smiles")),
        "run_label": _clean_text(run_context.get("session_id")),
        "experiment_request_count": _safe_int(experiment_detail.get("request_count")),
        "experiment_result_count": _safe_int(experiment_detail.get("result_count")),
        "pending_request_count": _safe_int(experiment_detail.get("pending_request_count")),
        "belief_update_count": _safe_int(belief_update.get("update_count")),
        "belief_state": _clean_text(belief_state.get("current_state"), default="absent"),
        "belief_strength": _clean_text(belief_state.get("current_strength"), default="absent"),
        "unresolved_state": _clean_text(diagnostics.get("experiment_lifecycle_unresolved_state"), default="unknown"),
    }


def _experiment_inspection_payload(item: dict[str, Any]) -> dict[str, Any]:
    scope = item.get("scope_context") if isinstance(item.get("scope_context"), dict) else {}
    result_summary = item.get("result_summary") if isinstance(item.get("result_summary"), dict) else {}
    belief_impact = item.get("latest_belief_impact_summary") if isinstance(item.get("latest_belief_impact_summary"), dict) else {}
    return {
        "request_id": _clean_text(item.get("request_id")),
        "linked_claim_id": next((choice for choice in (item.get("linked_claim_ids") or []) if _clean_text(choice)), ""),
        "claim_scope": _clean_text(scope.get("claim_scope"), default="unknown"),
        "candidate_label": _clean_text(scope.get("candidate_id") or scope.get("canonical_smiles")),
        "run_label": _clean_text(scope.get("session_id")),
        "status": _clean_text(item.get("status"), default="unknown"),
        "objective_summary": _clean_text(item.get("objective_summary")) or "Experiment request recorded.",
        "rationale_summary": _clean_text(item.get("rationale_summary")),
        "has_result": bool(item.get("has_result")),
        "result_status": _clean_text(result_summary.get("status"), default="absent"),
        "result_summary": _clean_text(result_summary.get("summary_text")) or "No result recorded.",
        "has_belief_update": bool(item.get("has_belief_update")),
        "belief_summary": _clean_text(belief_impact.get("summary_text")) or "No belief update recorded.",
        "belief_state": _clean_text(belief_impact.get("belief_state"), default="absent"),
        "unresolved_state": _clean_text(item.get("unresolved_state"), default="unknown"),
    }


def build_session_epistemic_summary(
    *,
    belief_layer_summary: dict[str, Any] | None,
    experiment_lifecycle_summary: dict[str, Any] | None,
    claim_detail_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    belief = belief_layer_summary if isinstance(belief_layer_summary, dict) else {}
    experiment = experiment_lifecycle_summary if isinstance(experiment_lifecycle_summary, dict) else {}
    claim_detail = claim_detail_summary if isinstance(claim_detail_summary, dict) else {}

    active_claim_count = _safe_int(belief.get("active_claim_count"))
    pending_experiment_count = _safe_int(experiment.get("pending_count"))
    result_recorded_count = _safe_int(experiment.get("result_recorded_count"))
    unresolved_count = _safe_int(experiment.get("claim_linked_unresolved_count"))
    belief_state_count = _safe_int(belief.get("belief_state_count"))
    belief_updated_count = _safe_int(experiment.get("belief_updated_count"))
    claim_count = _safe_int(belief.get("claim_count"))

    if claim_count == 0 and not experiment.get("has_experiments") and not belief.get("has_belief_layer"):
        status = "no_epistemic_layer"
        summary_line = "No claims, experiments, or belief state are recorded for this session."
        absence_reason = "no_claims_or_experiments_or_belief_state"
        available = False
    elif pending_experiment_count > 0:
        status = "pending_experiments"
        summary_line = f"{pending_experiment_count} pending experiment-linked state(s) require follow-up."
        absence_reason = ""
        available = True
    elif unresolved_count > 0:
        status = "unresolved_epistemic_state"
        summary_line = f"{unresolved_count} experiment-linked epistemic state(s) remain unresolved."
        absence_reason = ""
        available = True
    elif result_recorded_count > 0 or belief_updated_count > 0:
        status = "results_recorded"
        summary_line = f"{result_recorded_count} experiment result(s) recorded; {belief_updated_count} belief update(s) linked."
        absence_reason = ""
        available = True
    else:
        status = "claims_present_no_experiments"
        summary_line = "Claims are present, but no experiment lifecycle has been recorded."
        absence_reason = ""
        available = True

    return {
        "available": available,
        "status": status,
        "summary_line": summary_line,
        "active_claim_count": active_claim_count,
        "claim_count": claim_count,
        "pending_experiment_count": pending_experiment_count,
        "result_recorded_count": result_recorded_count,
        "unresolved_count": unresolved_count,
        "belief_state_count": belief_state_count,
        "belief_updated_count": belief_updated_count,
        "claim_detail_available": bool(claim_detail.get("has_claim_detail_surface")),
        "claim_detail_count": _safe_int(claim_detail.get("claim_detail_count")),
        "experiment_lifecycle_available": bool(experiment.get("has_experiments")),
        "absence_reason": absence_reason,
        "provenance": "canonical_epistemic_read_models" if available else "absent",
    }


def build_candidate_epistemic_context(
    *,
    claim_summary: dict[str, Any] | None,
    claim_detail_items: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    claim = claim_summary if isinstance(claim_summary, dict) else {}
    detail_items = claim_detail_items if isinstance(claim_detail_items, list) else []
    lifecycle = claim.get("experiment_lifecycle_summary") if isinstance(claim.get("experiment_lifecycle_summary"), dict) else {}

    claim_count = _safe_int(claim.get("claim_count"))
    has_claims = claim_count > 0
    has_pending_experiment = _safe_int(lifecycle.get("pending_request_count")) > 0 or bool(
        claim.get("has_experiment_request") and not claim.get("has_experiment_result")
    )
    has_recorded_result = bool(claim.get("has_experiment_result")) or _safe_int(lifecycle.get("result_recorded_count")) > 0
    has_belief_state = bool(claim.get("belief_states")) or bool(claim.get("latest_belief_summary"))
    has_belief_update = _safe_int(lifecycle.get("belief_updated_count")) > 0
    unresolved_count = _safe_int(lifecycle.get("unresolved_experiment_count"))
    detail_available = bool(detail_items)

    if not has_claims and not detail_available:
        status = "no_epistemic_objects"
        summary_line = "No claim, experiment, or belief context is recorded for this candidate."
        absence_reason = "candidate_has_no_epistemic_layer_objects"
        available = False
    elif has_pending_experiment:
        status = "pending_experiment"
        summary_line = "Experiment request recorded; result still pending."
        absence_reason = ""
        available = True
    elif has_recorded_result and not has_belief_update:
        status = "result_recorded_no_belief_update"
        summary_line = "Experiment result recorded; belief update not yet linked."
        absence_reason = ""
        available = True
    elif has_belief_update or has_belief_state:
        status = "belief_linked"
        summary_line = "Claim and belief context are available for this candidate."
        absence_reason = ""
        available = True
    else:
        status = "claim_present_no_experiment"
        summary_line = "Claim context is present without linked experiment lifecycle."
        absence_reason = ""
        available = True

    return {
        "available": available,
        "status": status,
        "summary_line": summary_line,
        "claim_count": claim_count,
        "has_claims": has_claims,
        "has_pending_experiment": has_pending_experiment,
        "has_recorded_result": has_recorded_result,
        "has_belief_update": has_belief_update,
        "has_belief_state": has_belief_state,
        "unresolved_count": unresolved_count,
        "detail_available": detail_available,
        "detail_count": len(detail_items),
        "absence_reason": absence_reason,
        "provenance": "canonical_epistemic_read_models" if available else "absent",
    }


def build_epistemic_entry_points(
    *,
    claim_detail_summary: dict[str, Any] | None,
    experiment_lifecycle_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    claim_detail = claim_detail_summary if isinstance(claim_detail_summary, dict) else {}
    experiment = experiment_lifecycle_summary if isinstance(experiment_lifecycle_summary, dict) else {}
    return {
        "claim_detail_available": bool(claim_detail.get("has_claim_detail_surface")),
        "claim_detail_count": _safe_int(claim_detail.get("claim_detail_count")),
        "candidate_linked_detail_count": _safe_int(claim_detail.get("candidate_linked_count")),
        "run_linked_detail_count": _safe_int(claim_detail.get("run_linked_count")),
        "experiment_lifecycle_available": bool(experiment.get("has_experiments")),
        "experiment_request_count": _safe_int(experiment.get("experiment_request_count")),
        "absence_reason": (
            "no_claim_detail_or_experiment_lifecycle"
            if not claim_detail.get("has_claim_detail_surface") and not experiment.get("has_experiments")
            else ""
        ),
        "provenance": "canonical_epistemic_read_models"
        if claim_detail.get("has_claim_detail_surface") or experiment.get("has_experiments")
        else "absent",
    }


def build_session_epistemic_detail_reveal(
    *,
    session_epistemic_summary: dict[str, Any] | None,
    epistemic_entry_points: dict[str, Any] | None,
    claim_detail_items: list[dict[str, Any]] | None,
    experiment_lifecycle_model: dict[str, Any] | None,
) -> dict[str, Any]:
    summary = session_epistemic_summary if isinstance(session_epistemic_summary, dict) else {}
    entry = epistemic_entry_points if isinstance(epistemic_entry_points, dict) else {}
    claim_items = claim_detail_items if isinstance(claim_detail_items, list) else []
    lifecycle = experiment_lifecycle_model if isinstance(experiment_lifecycle_model, dict) else {}
    lifecycle_items = lifecycle.get("experiment_items") if isinstance(lifecycle.get("experiment_items"), list) else []

    compact_claims: list[dict[str, Any]] = []
    for item in claim_items[:4]:
        if not isinstance(item, dict):
            continue
        claim = item.get("claim") if isinstance(item.get("claim"), dict) else {}
        experiment_detail = item.get("experiment_detail") if isinstance(item.get("experiment_detail"), dict) else {}
        belief_state = item.get("current_belief_state") if isinstance(item.get("current_belief_state"), dict) else {}
        diagnostics = item.get("diagnostics") if isinstance(item.get("diagnostics"), dict) else {}
        compact_claims.append(
            {
                "claim_id": _clean_text(item.get("claim_id")),
                "claim_scope": _clean_text(claim.get("claim_scope"), default="unknown"),
                "claim_type": _clean_text(claim.get("claim_type"), default="unknown"),
                "claim_text": _clean_text(claim.get("claim_text")) or "Claim detail recorded.",
                "pending_request_count": _safe_int(experiment_detail.get("pending_request_count")),
                "has_results": bool(experiment_detail.get("has_results")),
                "belief_state": _clean_text(belief_state.get("current_state"), default="absent"),
                "unresolved_state": _clean_text(diagnostics.get("experiment_lifecycle_unresolved_state"), default="unknown"),
            }
        )

    compact_experiments: list[dict[str, Any]] = []
    for item in lifecycle_items[:4]:
        if not isinstance(item, dict):
            continue
        result_summary = item.get("result_summary") if isinstance(item.get("result_summary"), dict) else {}
        belief_impact = item.get("latest_belief_impact_summary") if isinstance(item.get("latest_belief_impact_summary"), dict) else {}
        compact_experiments.append(
            {
                "request_id": _clean_text(item.get("request_id")),
                "status": _clean_text(item.get("status"), default="unknown"),
                "objective_summary": _clean_text(item.get("objective_summary")) or "Experiment request recorded.",
                "result_status": _clean_text(result_summary.get("status"), default="absent"),
                "result_summary": _clean_text(result_summary.get("summary_text")),
                "belief_summary": _clean_text(belief_impact.get("summary_text")),
                "unresolved_state": _clean_text(item.get("unresolved_state"), default="unknown"),
            }
        )

    available = bool(summary.get("available") or entry.get("claim_detail_available") or entry.get("experiment_lifecycle_available"))
    absence_reason = ""
    if not available:
        absence_reason = _clean_text(summary.get("absence_reason") or entry.get("absence_reason"), default="no_epistemic_detail_available")

    return {
        "available": available,
        "claim_items": compact_claims,
        "experiment_items": compact_experiments,
        "claim_item_count": len(compact_claims),
        "experiment_item_count": len(compact_experiments),
        "detail_available": bool(entry.get("claim_detail_available")),
        "lifecycle_available": bool(entry.get("experiment_lifecycle_available")),
        "unresolved_count": _safe_int(summary.get("unresolved_count")),
        "absence_reason": absence_reason,
        "provenance": "canonical_epistemic_read_models" if available else "absent",
    }


def build_candidate_epistemic_detail_reveal(
    *,
    candidate_epistemic_context: dict[str, Any] | None,
    claim_summary: dict[str, Any] | None,
    claim_detail_items: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    context = candidate_epistemic_context if isinstance(candidate_epistemic_context, dict) else {}
    claim = claim_summary if isinstance(claim_summary, dict) else {}
    detail_items = claim_detail_items if isinstance(claim_detail_items, list) else []
    lifecycle = claim.get("experiment_lifecycle_summary") if isinstance(claim.get("experiment_lifecycle_summary"), dict) else {}

    compact_claims: list[dict[str, Any]] = []
    for item in detail_items[:3]:
        if not isinstance(item, dict):
            continue
        claim_payload = item.get("claim") if isinstance(item.get("claim"), dict) else {}
        experiment_detail = item.get("experiment_detail") if isinstance(item.get("experiment_detail"), dict) else {}
        belief_state = item.get("current_belief_state") if isinstance(item.get("current_belief_state"), dict) else {}
        diagnostics = item.get("diagnostics") if isinstance(item.get("diagnostics"), dict) else {}
        compact_claims.append(
            {
                "claim_id": _clean_text(item.get("claim_id")),
                "claim_type": _clean_text(claim_payload.get("claim_type"), default="unknown"),
                "claim_text": _clean_text(claim_payload.get("claim_text")) or "Claim detail recorded.",
                "pending_request_count": _safe_int(experiment_detail.get("pending_request_count")),
                "has_results": bool(experiment_detail.get("has_results")),
                "belief_state": _clean_text(belief_state.get("current_state"), default="absent"),
                "unresolved_state": _clean_text(diagnostics.get("experiment_lifecycle_unresolved_state"), default="unknown"),
            }
        )

    available = bool(context.get("available") or context.get("detail_available") or compact_claims)
    absence_reason = _clean_text(context.get("absence_reason"), default="candidate_has_no_epistemic_layer_objects") if not available else ""
    return {
        "available": available,
        "status": _clean_text(context.get("status"), default="no_epistemic_objects"),
        "claim_items": compact_claims,
        "claim_count": _safe_int(context.get("claim_count")),
        "pending_experiment_count": 1 if context.get("has_pending_experiment") else 0,
        "has_recorded_result": bool(context.get("has_recorded_result")),
        "has_belief_update": bool(context.get("has_belief_update")),
        "has_belief_state": bool(context.get("has_belief_state")),
        "unresolved_count": _safe_int(context.get("unresolved_count") or lifecycle.get("unresolved_experiment_count")),
        "detail_count": len(compact_claims),
        "absence_reason": absence_reason,
        "provenance": "canonical_epistemic_read_models" if available else "absent",
    }


def build_focused_claim_inspection(
    *,
    claim_detail_items: list[dict[str, Any]] | None,
    selected_claim_id: str | None = None,
) -> dict[str, Any]:
    items = claim_detail_items if isinstance(claim_detail_items, list) else []
    clean_selected_id = _clean_text(selected_claim_id)
    choices: list[dict[str, Any]] = []
    selected = None
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        choice_payload = _claim_inspection_payload(item)
        claim_id = choice_payload["claim_id"]
        summary = choice_payload["claim_text"] or choice_payload["claim_scope"]
        choices.append(
            {
                "claim_id": claim_id,
                "label": _choice_label("Claim", claim_id, index, summary[:72]),
                "claim_type": choice_payload["claim_type"],
                "claim_status": choice_payload["claim_status"],
                "claim_scope": choice_payload["claim_scope"],
                "claim_text": choice_payload["claim_text"],
                "support_basis_summary": choice_payload["support_basis_summary"],
                "candidate_label": choice_payload["candidate_label"],
                "run_label": choice_payload["run_label"],
                "experiment_request_count": choice_payload["experiment_request_count"],
                "experiment_result_count": choice_payload["experiment_result_count"],
                "pending_request_count": choice_payload["pending_request_count"],
                "belief_update_count": choice_payload["belief_update_count"],
                "belief_state": choice_payload["belief_state"],
                "belief_strength": choice_payload["belief_strength"],
                "unresolved_state": choice_payload["unresolved_state"],
                "selected": False,
            }
        )
        if clean_selected_id and claim_id == clean_selected_id:
            selected = item

    default_first_fallback_used = False
    if selected is None:
        selected = next((item for item in items if isinstance(item, dict)), None)
        default_first_fallback_used = bool(selected and not clean_selected_id)

    if not isinstance(selected, dict):
        return {
            "available": False,
            "selected_claim_id": clean_selected_id,
            "selected_available": False,
            "choice_count": len(choices),
            "claim_choices": choices,
            "multiple_available": len(choices) > 1,
            "default_first_fallback_used": False,
            "absence_reason": "no_claim_available_for_focused_inspection",
            "provenance": "absent",
        }

    selected_payload = _claim_inspection_payload(selected)
    resolved_selected_id = _clean_text(selected.get("claim_id"))
    for choice in choices:
        if _clean_text(choice.get("claim_id")) == resolved_selected_id:
            choice["selected"] = True

    return {
        "available": True,
        "selected_claim_id": resolved_selected_id,
        "selected_available": True,
        "choice_count": len(choices),
        "claim_choices": choices,
        "multiple_available": len(choices) > 1,
        "default_first_fallback_used": default_first_fallback_used,
        **selected_payload,
        "absence_reason": "",
        "provenance": "canonical_epistemic_read_models",
    }


def build_focused_experiment_inspection(
    *,
    experiment_lifecycle_model: dict[str, Any] | None,
    selected_request_id: str | None = None,
) -> dict[str, Any]:
    lifecycle = experiment_lifecycle_model if isinstance(experiment_lifecycle_model, dict) else {}
    items = lifecycle.get("experiment_items") if isinstance(lifecycle.get("experiment_items"), list) else []
    clean_selected_id = _clean_text(selected_request_id)
    choices: list[dict[str, Any]] = []
    selected = None
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        choice_payload = _experiment_inspection_payload(item)
        request_id = choice_payload["request_id"]
        summary = choice_payload["objective_summary"]
        choices.append(
            {
                "request_id": request_id,
                "label": _choice_label("Experiment", request_id, index, summary[:72]),
                "status": choice_payload["status"],
                "has_result": choice_payload["has_result"],
                "linked_claim_id": choice_payload["linked_claim_id"],
                "claim_scope": choice_payload["claim_scope"],
                "candidate_label": choice_payload["candidate_label"],
                "run_label": choice_payload["run_label"],
                "objective_summary": choice_payload["objective_summary"],
                "rationale_summary": choice_payload["rationale_summary"],
                "result_status": choice_payload["result_status"],
                "result_summary": choice_payload["result_summary"],
                "has_belief_update": choice_payload["has_belief_update"],
                "belief_summary": choice_payload["belief_summary"],
                "belief_state": choice_payload["belief_state"],
                "unresolved_state": choice_payload["unresolved_state"],
                "selected": False,
            }
        )
        if clean_selected_id and request_id == clean_selected_id:
            selected = item

    default_first_fallback_used = False
    if selected is None:
        selected = next((item for item in items if isinstance(item, dict)), None)
        default_first_fallback_used = bool(selected and not clean_selected_id)

    if not isinstance(selected, dict):
        return {
            "available": False,
            "selected_request_id": clean_selected_id,
            "selected_available": False,
            "choice_count": len(choices),
            "experiment_choices": choices,
            "multiple_available": len(choices) > 1,
            "default_first_fallback_used": False,
            "absence_reason": "no_experiment_available_for_focused_inspection",
            "provenance": "absent",
        }

    selected_payload = _experiment_inspection_payload(selected)
    resolved_selected_id = _clean_text(selected.get("request_id"))
    for choice in choices:
        if _clean_text(choice.get("request_id")) == resolved_selected_id:
            choice["selected"] = True

    return {
        "available": True,
        "selected_request_id": resolved_selected_id,
        "selected_available": True,
        "choice_count": len(choices),
        "experiment_choices": choices,
        "multiple_available": len(choices) > 1,
        "default_first_fallback_used": default_first_fallback_used,
        **selected_payload,
        "absence_reason": "",
        "provenance": "canonical_epistemic_read_models",
    }
