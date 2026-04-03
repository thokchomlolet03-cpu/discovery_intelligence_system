from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.contracts import (
    ExperimentRequestStatus,
    PriorityTier,
    validate_experiment_request_record,
    validate_experiment_request_reference,
    validate_experiment_request_summary,
    validate_scientific_session_truth,
)
from system.db.repositories import ExperimentRequestRepository


experiment_request_repository = ExperimentRequestRepository()
DEFAULT_EXPERIMENT_REQUEST_LIMIT = 5


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _candidate_lookup(decision_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = decision_payload.get("top_experiments") if isinstance(decision_payload.get("top_experiments"), list) else []
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        candidate_id = _clean_text(row.get("candidate_id") or row.get("molecule_id") or row.get("polymer"))
        if candidate_id:
            lookup[candidate_id] = row
    return lookup


def _requested_measurement(target_definition: dict[str, Any]) -> str:
    measurement = _clean_text(target_definition.get("measurement_column"))
    if measurement:
        return measurement
    return _clean_text(target_definition.get("target_name"), default="target objective")


def _requested_direction(target_definition: dict[str, Any]) -> str:
    direction = _clean_text(target_definition.get("optimization_direction"), default="classify").lower()
    if direction == "maximize":
        return "measure for higher values"
    if direction == "minimize":
        return "measure for lower values"
    if direction == "hit_range":
        return "measure against the desired value range"
    return "test against the current target objective"


def _priority_tier(claim: dict[str, Any], candidate: dict[str, Any]) -> str:
    rank = _safe_int(candidate.get("rank"), _safe_int(claim.get("source_recommendation_rank"), 0))
    support_level = _clean_text(claim.get("support_level")).lower()
    if rank <= 1 or support_level == "strong":
        return PriorityTier.high.value
    if rank <= 3 or support_level == "moderate":
        return PriorityTier.medium.value
    return PriorityTier.low.value


def _rationale_summary(claim: dict[str, Any], candidate: dict[str, Any], target_definition: dict[str, Any]) -> str:
    target_name = _clean_text(target_definition.get("target_name"), default="target objective")
    requested_measurement = _requested_measurement(target_definition)
    driver = _clean_text(
        candidate.get("rationale_primary_driver")
        or ((candidate.get("rationale") or {}) if isinstance(candidate.get("rationale"), dict) else {}).get("primary_driver")
    )
    claim_text = _clean_text(claim.get("claim_text"))
    parts = [
        f"This proposed experiment request is derived from the current claim for {target_name}.",
        f"Recommended next step: measure {requested_measurement} to test whether the observed result supports the bounded session claim.",
    ]
    if driver:
        parts.append(f"Current rationale: {driver.rstrip('.')}.")
    elif claim_text:
        parts.append(f"Current claim context: {claim_text.rstrip('.')}.")
    parts.append("This is a recommended experiment request, not scheduled or completed lab work.")
    return " ".join(parts)


def build_experiment_request_record(
    *,
    session_id: str,
    workspace_id: str,
    claim: dict[str, Any],
    candidate: dict[str, Any] | None,
    requested_by_user_id: str | None = None,
    requested_by: str = "system",
) -> dict[str, Any]:
    claim = claim if isinstance(claim, dict) else {}
    candidate = candidate if isinstance(candidate, dict) else {}
    target_definition = claim.get("target_definition_snapshot") if isinstance(claim.get("target_definition_snapshot"), dict) else {}
    candidate_reference = claim.get("candidate_reference") if isinstance(claim.get("candidate_reference"), dict) else {}
    candidate_id = _clean_text(claim.get("candidate_id") or candidate.get("candidate_id") or candidate_reference.get("candidate_id"))
    timestamp = _utc_now()
    return validate_experiment_request_record(
        {
            "experiment_request_id": "",
            "workspace_id": workspace_id,
            "session_id": session_id,
            "claim_id": _clean_text(claim.get("claim_id")),
            "candidate_id": candidate_id,
            "candidate_reference": {
                **candidate_reference,
                "candidate_id": candidate_id,
                "candidate_label": _clean_text(candidate_reference.get("candidate_label"), default=candidate_id),
                "rank": _safe_int(candidate.get("rank"), _safe_int(candidate_reference.get("rank"), _safe_int(claim.get("source_recommendation_rank"), 0))),
            },
            "target_definition_snapshot": target_definition,
            "requested_measurement": _requested_measurement(target_definition),
            "requested_direction": _requested_direction(target_definition),
            "rationale_summary": _rationale_summary(claim, candidate, target_definition),
            "priority_tier": _priority_tier(claim, candidate),
            "status": ExperimentRequestStatus.proposed.value,
            "requested_at": timestamp,
            "requested_by": _clean_text(requested_by, default="system"),
            "requested_by_user_id": _clean_text(requested_by_user_id),
            "notes": "",
            "metadata": {
                "claim_support_level": _clean_text(claim.get("support_level")),
                "source_recommendation_rank": _safe_int(claim.get("source_recommendation_rank"), 0),
            },
        }
    )


def create_session_experiment_requests(
    *,
    session_id: str,
    workspace_id: str,
    claims: list[dict[str, Any]],
    decision_payload: dict[str, Any] | None,
    requested_by_user_id: str | None = None,
    requested_by: str = "system",
    limit: int = DEFAULT_EXPERIMENT_REQUEST_LIMIT,
) -> list[dict[str, Any]]:
    decision_payload = decision_payload if isinstance(decision_payload, dict) else {}
    candidate_lookup = _candidate_lookup(decision_payload)
    created: list[dict[str, Any]] = []
    for claim in claims[: max(0, int(limit))]:
        if not isinstance(claim, dict):
            continue
        claim_id = _clean_text(claim.get("claim_id"))
        candidate_id = _clean_text(claim.get("candidate_id"))
        if not claim_id or not candidate_id:
            continue
        payload = build_experiment_request_record(
            session_id=session_id,
            workspace_id=workspace_id,
            claim=claim,
            candidate=candidate_lookup.get(candidate_id) or {},
            requested_by_user_id=requested_by_user_id,
            requested_by=requested_by,
        )
        created.append(experiment_request_repository.upsert_experiment_request(payload))
    return created


def list_session_experiment_requests(
    session_id: str,
    *,
    workspace_id: str | None = None,
    claim_id: str | None = None,
) -> list[dict[str, Any]]:
    return experiment_request_repository.list_experiment_requests(
        session_id=session_id,
        workspace_id=workspace_id,
        claim_id=claim_id,
    )


def experiment_request_refs_from_records(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for request in requests:
        if not isinstance(request, dict):
            continue
        candidate_reference = request.get("candidate_reference") if isinstance(request.get("candidate_reference"), dict) else {}
        refs.append(
            validate_experiment_request_reference(
                {
                    "experiment_request_id": request.get("experiment_request_id"),
                    "claim_id": request.get("claim_id"),
                    "candidate_id": request.get("candidate_id"),
                    "candidate_label": candidate_reference.get("candidate_label") or request.get("candidate_id"),
                    "requested_measurement": request.get("requested_measurement"),
                    "requested_direction": request.get("requested_direction"),
                    "priority_tier": request.get("priority_tier"),
                    "status": request.get("status"),
                    "requested_at": request.get("requested_at"),
                }
            )
        )
    return refs


def experiment_request_summary_from_records(requests: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(requests)
    proposed = sum(1 for request in requests if _clean_text(request.get("status")).lower() == ExperimentRequestStatus.proposed.value)
    accepted = sum(1 for request in requests if _clean_text(request.get("status")).lower() == ExperimentRequestStatus.accepted.value)
    rejected = sum(1 for request in requests if _clean_text(request.get("status")).lower() == ExperimentRequestStatus.rejected.value)
    completed = sum(1 for request in requests if _clean_text(request.get("status")).lower() == ExperimentRequestStatus.completed.value)
    superseded = sum(1 for request in requests if _clean_text(request.get("status")).lower() == ExperimentRequestStatus.superseded.value)
    if total:
        summary_text = (
            f"{total} proposed experiment request{'' if total == 1 else 's'} were derived from the current claims. "
            "These requests recommend next experiments; they are not scheduled or completed lab work."
        )
    else:
        summary_text = "No experiment requests have been recorded for this session."
    return validate_experiment_request_summary(
        {
            "request_count": total,
            "proposed_count": proposed,
            "accepted_count": accepted,
            "rejected_count": rejected,
            "completed_count": completed,
            "superseded_count": superseded,
            "summary_text": summary_text,
            "top_requests": experiment_request_refs_from_records(requests[:3]),
        }
    )


def attach_experiment_requests_to_scientific_session_truth(
    scientific_truth: dict[str, Any],
    experiment_requests: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(scientific_truth, dict):
        return scientific_truth
    updated = dict(scientific_truth)
    updated["experiment_request_refs"] = experiment_request_refs_from_records(experiment_requests)
    updated["experiment_request_summary"] = experiment_request_summary_from_records(experiment_requests)
    return validate_scientific_session_truth(updated)


__all__ = [
    "attach_experiment_requests_to_scientific_session_truth",
    "build_experiment_request_record",
    "create_session_experiment_requests",
    "experiment_request_refs_from_records",
    "experiment_request_summary_from_records",
    "list_session_experiment_requests",
]
