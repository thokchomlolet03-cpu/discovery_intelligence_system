from __future__ import annotations

from typing import Any

from system.db import ScientificStateRepository
from system.services.experiment_read_service import build_session_experiment_lifecycle_read_model


scientific_state_repository = ScientificStateRepository()


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _claim_key(claim: dict[str, Any]) -> str:
    return _clean_text(claim.get("claim_id"))


def build_session_belief_read_model(*, session_id: str, workspace_id: str | None = None) -> dict[str, Any]:
    claims = scientific_state_repository.list_claims(session_id=session_id, workspace_id=workspace_id)
    candidate_states = scientific_state_repository.list_candidate_states(session_id=session_id, workspace_id=workspace_id)
    experiment_lifecycle = build_session_experiment_lifecycle_read_model(session_id=session_id, workspace_id=workspace_id)
    lifecycle_claim_lookup = {
        _clean_text(item.get("claim_id")): item
        for item in experiment_lifecycle.get("claim_items", [])
        if _clean_text(item.get("claim_id"))
    }
    lifecycle_candidate_lookup = {
        _clean_text(item.get("candidate_id")): item
        for item in experiment_lifecycle.get("candidate_items", [])
        if _clean_text(item.get("candidate_id"))
    }

    belief_states_by_claim: dict[str, dict[str, Any]] = {}
    experiment_requests_by_claim: dict[str, list[dict[str, Any]]] = {}
    experiment_results_by_claim: dict[str, list[dict[str, Any]]] = {}

    for claim in claims:
        claim_id = _claim_key(claim)
        if not claim_id:
            continue
        try:
            belief_states_by_claim[claim_id] = scientific_state_repository.get_belief_state(claim_id=claim_id)
        except FileNotFoundError:
            belief_states_by_claim[claim_id] = {}

        requests = scientific_state_repository.list_experiment_requests(claim_id=claim_id)
        experiment_requests_by_claim[claim_id] = requests
        results: list[dict[str, Any]] = []
        for request in requests:
            results.extend(scientific_state_repository.list_experiment_results(request_id=_clean_text(request.get("request_id"))))
        experiment_results_by_claim[claim_id] = results

    categories = sorted({_clean_text(item.get("claim_type")) for item in claims if _clean_text(item.get("claim_type"))})
    active_claims = [item for item in claims if _clean_text(item.get("status"), default="active") == "active"]
    supported_count = sum(1 for item in belief_states_by_claim.values() if _clean_text(item.get("current_state")) == "supported")
    challenged_count = sum(1 for item in belief_states_by_claim.values() if _clean_text(item.get("current_state")) == "challenged")
    unresolved_count = sum(1 for item in belief_states_by_claim.values() if not item or _clean_text(item.get("current_state"), default="unresolved") == "unresolved")

    candidate_items: list[dict[str, Any]] = []
    for candidate in candidate_states:
        candidate_id = _clean_text(candidate.get("candidate_id"))
        candidate_claims = [item for item in claims if _clean_text(item.get("candidate_id")) == candidate_id]
        candidate_beliefs = [belief_states_by_claim.get(_claim_key(item), {}) for item in candidate_claims]
        candidate_requests = [request for item in candidate_claims for request in experiment_requests_by_claim.get(_claim_key(item), [])]
        candidate_results = [result for item in candidate_claims for result in experiment_results_by_claim.get(_claim_key(item), [])]
        candidate_items.append(
            {
                "candidate_id": candidate_id,
                "canonical_smiles": _clean_text(candidate.get("canonical_smiles")),
                "claim_count": len(candidate_claims),
                "claim_statuses": sorted({_clean_text(item.get("status")) for item in candidate_claims if _clean_text(item.get("status"))}),
                "belief_states": sorted({_clean_text(item.get("current_state"), default="unresolved") for item in candidate_beliefs if isinstance(item, dict)}),
                "has_experiment_request": bool(candidate_requests),
                "has_experiment_result": bool(candidate_results),
                "experiment_lifecycle_summary": lifecycle_candidate_lookup.get(candidate_id, {}),
                "latest_belief_summary": next((str(item.get("support_basis_summary") or "").strip() for item in candidate_beliefs if str(item.get("support_basis_summary") or "").strip()), ""),
                "provenance": "canonical_belief_objects" if candidate_claims else "absent",
            }
        )

    run_claims = [item for item in claims if _clean_text(item.get("claim_scope")) == "run"]
    run_items = []
    for claim in run_claims:
        claim_id = _claim_key(claim)
        belief_state = belief_states_by_claim.get(claim_id, {})
        run_items.append(
            {
                "claim_id": claim_id,
                "claim_type": _clean_text(claim.get("claim_type")),
                "claim_text": _clean_text(claim.get("claim_text")),
                "belief_state": _clean_text(belief_state.get("current_state"), default="absent"),
                "belief_strength": _clean_text(belief_state.get("current_strength"), default="absent"),
                "provenance": "canonical_belief_objects",
            }
        )

    return {
        "session_summary": {
            "claim_count": len(claims),
            "active_claim_count": len(active_claims),
            "claim_categories": categories,
            "belief_state_count": sum(1 for item in belief_states_by_claim.values() if item),
            "supported_claim_count": supported_count,
            "challenged_claim_count": challenged_count,
            "unresolved_claim_count": unresolved_count,
            "experiment_request_count": sum(len(items) for items in experiment_requests_by_claim.values()),
            "experiment_result_count": sum(len(items) for items in experiment_results_by_claim.values()),
            "has_belief_layer": bool(claims),
            "absence_reason": "" if claims else "no_claims_materialized",
        },
        "candidate_items": candidate_items,
        "run_items": run_items,
        "claim_items": [
            {
                "claim_id": _claim_key(item),
                "claim_scope": _clean_text(item.get("claim_scope")),
                "claim_type": _clean_text(item.get("claim_type")),
                "claim_text": _clean_text(item.get("claim_text")),
                "status": _clean_text(item.get("status"), default="active"),
                "belief_state": _clean_text((belief_states_by_claim.get(_claim_key(item), {}) or {}).get("current_state"), default="absent"),
                "belief_strength": _clean_text((belief_states_by_claim.get(_claim_key(item), {}) or {}).get("current_strength"), default="absent"),
                "experiment_request_count": len(experiment_requests_by_claim.get(_claim_key(item), [])),
                "experiment_result_count": len(experiment_results_by_claim.get(_claim_key(item), [])),
                "experiment_lifecycle": lifecycle_claim_lookup.get(_claim_key(item), {}),
                "latest_belief_summary": _clean_text((belief_states_by_claim.get(_claim_key(item), {}) or {}).get("support_basis_summary")),
                "provenance": "canonical_belief_objects",
            }
            for item in claims
        ],
        "experiment_lifecycle_summary": experiment_lifecycle.get("session_summary", {}),
        "diagnostics": {
            "belief_read_source": "canonical_belief_objects" if claims else "absent",
            "absent_belief_state_claims": [
                _claim_key(item) for item in claims if not belief_states_by_claim.get(_claim_key(item))
            ],
            "pending_experiment_claims": [
                _claim_key(item)
                for item in claims
                if experiment_requests_by_claim.get(_claim_key(item)) and not experiment_results_by_claim.get(_claim_key(item))
            ],
            "experiment_lifecycle_source": experiment_lifecycle.get("session_summary", {}).get("provenance", "absent"),
            "claim_detail_surface_ready": bool(claims),
        },
    }
