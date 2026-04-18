from __future__ import annotations

from typing import Any

from system.db import ScientificStateRepository


scientific_state_repository = ScientificStateRepository()


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _to_iso(value: Any) -> str:
    if value in (None, ""):
        return ""
    return _clean_text(value)


def _claim_key(claim: dict[str, Any]) -> str:
    return _clean_text(claim.get("claim_id"))


def _result_summary_text(result: dict[str, Any]) -> str:
    summary = _as_dict(result.get("result_summary"))
    for key in ("summary", "outcome_summary", "note", "label"):
        text = _clean_text(summary.get(key))
        if text:
            return text
    outcome = _clean_text(result.get("outcome"))
    if outcome:
        return f"Outcome recorded: {outcome}."
    return ""


def _belief_impact_summary(update: dict[str, Any], belief_state: dict[str, Any]) -> str:
    update_reason = _clean_text(update.get("update_reason"))
    if update_reason:
        return update_reason
    return _clean_text(belief_state.get("support_basis_summary"))


def _request_status(request: dict[str, Any], results: list[dict[str, Any]]) -> str:
    raw_status = _clean_text(request.get("status"), default="requested")
    if results and raw_status != "completed":
        return "result_recorded"
    return raw_status


def _scope_context(request: dict[str, Any], claim: dict[str, Any] | None) -> dict[str, Any]:
    claim_payload = claim if isinstance(claim, dict) else {}
    return {
        "session_id": _clean_text(request.get("session_id") or claim_payload.get("session_id")),
        "workspace_id": _clean_text(request.get("workspace_id") or claim_payload.get("workspace_id")),
        "claim_scope": _clean_text(claim_payload.get("claim_scope"), default="unknown"),
        "candidate_id": _clean_text(request.get("candidate_id") or claim_payload.get("candidate_id")),
        "canonical_smiles": _clean_text(request.get("canonical_smiles") or claim_payload.get("canonical_smiles")),
        "run_metadata_session_id": _clean_text(claim_payload.get("run_metadata_session_id")),
    }


def _build_experiment_item(
    request: dict[str, Any],
    *,
    claim: dict[str, Any] | None,
    results: list[dict[str, Any]],
    belief_updates: list[dict[str, Any]],
    belief_state: dict[str, Any],
) -> dict[str, Any]:
    latest_result = results[-1] if results else {}
    latest_update = belief_updates[-1] if belief_updates else {}
    has_result = bool(results)
    has_belief_update = bool(belief_updates)
    unresolved_state = (
        "no_result_recorded"
        if not has_result
        else "result_recorded_no_belief_update"
        if not has_belief_update
        else "belief_updated"
    )
    return {
        "request_id": _clean_text(request.get("request_id")),
        "linked_claim_ids": [_clean_text(request.get("claim_id"))] if _clean_text(request.get("claim_id")) else [],
        "scope_context": _scope_context(request, claim),
        "objective_summary": _clean_text(request.get("objective")),
        "rationale_summary": _clean_text(request.get("rationale")),
        "requested_measurement": _clean_text(request.get("requested_measurement")),
        "status": _request_status(request, results),
        "has_result": has_result,
        "result_count": len(results),
        "result_summary": {
            "available": has_result,
            "result_id": _clean_text(latest_result.get("result_id")),
            "outcome": _clean_text(latest_result.get("outcome")),
            "status": _clean_text(latest_result.get("status"), default="absent"),
            "summary_text": _result_summary_text(latest_result),
            "created_at": _to_iso(latest_result.get("created_at")),
            "provenance": "canonical_experiment_result" if has_result else "absent",
        },
        "has_belief_update": has_belief_update,
        "latest_belief_impact_summary": {
            "available": has_belief_update,
            "update_id": _clean_text(latest_update.get("update_id")),
            "belief_state": _clean_text(belief_state.get("current_state"), default="absent"),
            "belief_strength": _clean_text(belief_state.get("current_strength"), default="absent"),
            "summary_text": _belief_impact_summary(latest_update, belief_state),
            "created_at": _to_iso(latest_update.get("created_at")),
            "provenance": "canonical_belief_update" if has_belief_update else "absent",
        },
        "unresolved_state": unresolved_state,
        "provenance_markers": {
            "request": _as_dict(request.get("provenance_markers")),
            "result": _as_dict(latest_result.get("provenance_markers")),
            "belief_update": _as_dict(latest_update.get("provenance_markers")),
        },
        "provenance": "canonical_experiment_lifecycle",
    }


def build_session_experiment_lifecycle_read_model(*, session_id: str, workspace_id: str | None = None) -> dict[str, Any]:
    claims = scientific_state_repository.list_claims(session_id=session_id, workspace_id=workspace_id)
    requests = scientific_state_repository.list_experiment_requests(session_id=session_id)
    requests = [item for item in requests if workspace_id is None or _clean_text(item.get("workspace_id")) == workspace_id]
    claim_lookup = {_claim_key(item): item for item in claims if _claim_key(item)}

    results_by_request: dict[str, list[dict[str, Any]]] = {}
    updates_by_result: dict[str, list[dict[str, Any]]] = {}
    belief_state_by_claim: dict[str, dict[str, Any]] = {}
    experiment_items: list[dict[str, Any]] = []

    for request in requests:
        request_id = _clean_text(request.get("request_id"))
        claim_id = _clean_text(request.get("claim_id"))
        request_results = scientific_state_repository.list_experiment_results(request_id=request_id)
        results_by_request[request_id] = request_results
        belief_updates: list[dict[str, Any]] = []
        for result in request_results:
            result_id = _clean_text(result.get("result_id"))
            result_updates = scientific_state_repository.list_belief_updates(result_id=result_id)
            updates_by_result[result_id] = result_updates
            belief_updates.extend(result_updates)
        if claim_id and claim_id not in belief_state_by_claim:
            try:
                belief_state_by_claim[claim_id] = scientific_state_repository.get_belief_state(claim_id=claim_id)
            except FileNotFoundError:
                belief_state_by_claim[claim_id] = {}
        experiment_items.append(
            _build_experiment_item(
                request,
                claim=claim_lookup.get(claim_id),
                results=request_results,
                belief_updates=belief_updates,
                belief_state=belief_state_by_claim.get(claim_id, {}),
            )
        )

    claim_items: list[dict[str, Any]] = []
    for claim in claims:
        claim_id = _claim_key(claim)
        claim_requests = [item for item in requests if _clean_text(item.get("claim_id")) == claim_id]
        claim_results = [
            result
            for request in claim_requests
            for result in results_by_request.get(_clean_text(request.get("request_id")), [])
        ]
        claim_updates = [
            update
            for result in claim_results
            for update in updates_by_result.get(_clean_text(result.get("result_id")), [])
        ]
        unresolved_state = (
            "no_experiment_request"
            if not claim_requests
            else "pending_result"
            if not claim_results
            else "result_recorded_no_belief_update"
            if not claim_updates
            else "belief_updated"
        )
        claim_items.append(
            {
                "claim_id": claim_id,
                "claim_scope": _clean_text(claim.get("claim_scope")),
                "claim_type": _clean_text(claim.get("claim_type")),
                "has_experiment_request": bool(claim_requests),
                "pending_result": bool(claim_requests) and not bool(claim_results),
                "has_result_recorded": bool(claim_results),
                "has_belief_update": bool(claim_updates),
                "unresolved_state": unresolved_state,
                "request_ids": [_clean_text(item.get("request_id")) for item in claim_requests if _clean_text(item.get("request_id"))],
                "result_ids": [_clean_text(item.get("result_id")) for item in claim_results if _clean_text(item.get("result_id"))],
                "belief_update_ids": [_clean_text(item.get("update_id")) for item in claim_updates if _clean_text(item.get("update_id"))],
                "provenance": "canonical_experiment_lifecycle" if claim_requests or claim_results or claim_updates else "absent",
            }
        )

    candidate_ids = sorted(
        {
            _clean_text(item.get("candidate_id"))
            for item in claims + requests
            if _clean_text(item.get("candidate_id"))
        }
    )
    candidate_items: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        candidate_claims = [
            item for item in claim_items if _clean_text(claim_lookup.get(_clean_text(item.get("claim_id")), {}).get("candidate_id")) == candidate_id
        ]
        candidate_experiments = [
            item for item in experiment_items if _clean_text((item.get("scope_context") or {}).get("candidate_id")) == candidate_id
        ]
        candidate_items.append(
            {
                "candidate_id": candidate_id,
                "canonical_smiles": next(
                    (
                        _clean_text((item.get("scope_context") or {}).get("canonical_smiles"))
                        for item in candidate_experiments
                        if _clean_text((item.get("scope_context") or {}).get("canonical_smiles"))
                    ),
                    next(
                        (
                            _clean_text(claim_lookup.get(_clean_text(item.get("claim_id")), {}).get("canonical_smiles"))
                            for item in candidate_claims
                            if _clean_text(claim_lookup.get(_clean_text(item.get("claim_id")), {}).get("canonical_smiles"))
                        ),
                        "",
                    ),
                ),
                "pending_request_count": sum(1 for item in candidate_experiments if not item.get("has_result")),
                "completed_request_count": sum(1 for item in candidate_experiments if item.get("has_result")),
                "result_recorded_count": sum(1 for item in candidate_experiments if item.get("has_result")),
                "belief_updated_count": sum(1 for item in candidate_experiments if item.get("has_belief_update")),
                "claim_without_experiment_count": sum(1 for item in candidate_claims if not item.get("has_experiment_request")),
                "unresolved_experiment_count": sum(1 for item in candidate_experiments if item.get("unresolved_state") != "belief_updated"),
                "has_experiment_context": bool(candidate_experiments),
                "absence_reason": "" if candidate_experiments or candidate_claims else "candidate_not_linked",
                "experiment_items": candidate_experiments,
                "provenance": "canonical_experiment_lifecycle" if candidate_experiments or candidate_claims else "absent",
            }
        )

    run_claim_items = [item for item in claim_items if item.get("claim_scope") == "run"]
    run_items = [
        {
            "session_id": session_id,
            "request_count": sum(1 for item in run_claim_items if item.get("has_experiment_request")),
            "pending_result_count": sum(1 for item in run_claim_items if item.get("pending_result")),
            "result_recorded_count": sum(1 for item in run_claim_items if item.get("has_result_recorded")),
            "belief_updated_count": sum(1 for item in run_claim_items if item.get("has_belief_update")),
            "unresolved_claim_count": sum(1 for item in run_claim_items if item.get("unresolved_state") != "belief_updated"),
            "absence_reason": "" if run_claim_items else "run_linked_experiment_context_absent",
            "provenance": "canonical_experiment_lifecycle" if run_claim_items else "absent",
        }
    ]

    return {
        "session_summary": {
            "experiment_request_count": len(requests),
            "pending_count": sum(1 for item in experiment_items if not item.get("has_result")),
            "completed_count": sum(1 for item in requests if _clean_text(item.get("status")) == "completed"),
            "result_recorded_count": sum(1 for item in experiment_items if item.get("has_result")),
            "claim_linked_unresolved_count": sum(1 for item in claim_items if item.get("unresolved_state") != "belief_updated"),
            "belief_updated_count": sum(1 for item in experiment_items if item.get("has_belief_update")),
            "has_experiments": bool(requests),
            "absence_reason": "" if requests else "no_experiments_in_session",
            "provenance": "canonical_experiment_lifecycle" if requests else "absent",
        },
        "claim_items": claim_items,
        "candidate_items": candidate_items,
        "run_items": run_items,
        "experiment_items": experiment_items,
        "diagnostics": {
            "experiment_summary_present": bool(requests),
            "experiment_summary_absent": not bool(requests),
            "requests_without_results": [
                item.get("request_id") for item in experiment_items if item.get("unresolved_state") == "no_result_recorded"
            ],
            "results_without_belief_updates": [
                _clean_text((item.get("result_summary") or {}).get("result_id"))
                for item in experiment_items
                if item.get("unresolved_state") == "result_recorded_no_belief_update"
            ],
            "experiment_linked_unresolved_claims": [
                item.get("claim_id") for item in claim_items if item.get("unresolved_state") != "belief_updated"
            ],
            "field_provenance": {
                "request_fields": "canonical_experiment_request",
                "result_fields": "canonical_experiment_result",
                "belief_fields": "canonical_belief_update_and_belief_state",
            },
            "fallback_state": "no_experiments_in_session" if not requests else "",
        },
    }
