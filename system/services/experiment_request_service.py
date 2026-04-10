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


def _request_basis_and_intent_from_claim(claim: dict[str, Any]) -> dict[str, str]:
    claim = claim if isinstance(claim, dict) else {}
    actionability_label = _clean_text(claim.get("claim_actionability_label"))
    actionability_basis_label = _clean_text(claim.get("claim_actionability_basis_label"))
    support_quality_label = _clean_text(claim.get("claim_support_quality_label"))
    next_step_label = _clean_text(claim.get("claim_next_step_label"))
    historical_only = bool(claim.get("claim_historical_interest_only_flag"))

    if actionability_label == "Action-ready from current active support" or support_quality_label == "Decision-useful current active support":
        return {
            "request_basis_label": "Current active support",
            "request_intent_label": "Confirmatory follow-up",
            "request_guidance_summary": (
                "This request follows a claim with current active governed support, so it is best treated as bounded confirmatory follow-up rather than first-pass triage."
            ),
        }
    if support_quality_label == "Context-limited current support":
        return {
            "request_basis_label": "Context-limited active support",
            "request_intent_label": "Clarifying follow-up",
            "request_guidance_summary": (
                "This request is best read as clarification because active support exists, but assay or target-context limitations still need to be resolved."
            ),
        }
    if actionability_label == "Promising but needs stronger evidence":
        return {
            "request_basis_label": "Current active support still limited",
            "request_intent_label": "Strengthening follow-up",
            "request_guidance_summary": (
                "This request can strengthen a claim that already has some current active support, but the active basis remains limited and should not be treated as settled."
            ),
        }
    if actionability_label == "Mixed current/historical basis":
        return {
            "request_basis_label": "Mixed current/historical basis",
            "request_intent_label": "Clarifying follow-up",
            "request_guidance_summary": (
                "This request is best read as clarification because current support and historical context are both present, but the present action basis is not yet clean."
            ),
        }
    if historical_only or actionability_label == "Historically interesting, not currently action-ready":
        return {
            "request_basis_label": "Historical interest only",
            "request_intent_label": "Fresh-evidence follow-up",
            "request_guidance_summary": (
                "This request is a fresh-evidence check for a historically interesting claim and should not be treated as current action-readiness."
            ),
        }
    if actionability_label == "No active governed support":
        return {
            "request_basis_label": "No active governed support",
            "request_intent_label": "Exploratory follow-up",
            "request_guidance_summary": (
                "This request is exploratory because the linked claim currently lacks active governed support."
            ),
        }
    if support_quality_label == "Weak or provisional current support":
        return {
            "request_basis_label": "Weak or provisional active support",
            "request_intent_label": "Strengthening follow-up",
            "request_guidance_summary": (
                "This request is best treated as a strengthening check because active support exists, but it is still too weak or provisional for stronger follow-up."
            ),
        }
    if next_step_label == "Insufficient governed basis" or actionability_basis_label == "No governed support yet":
        return {
            "request_basis_label": "No governed support yet",
            "request_intent_label": "Exploratory follow-up",
            "request_guidance_summary": (
                "This request is best treated as context-building follow-up because governed support has not been established yet."
            ),
        }
    return {
        "request_basis_label": "Claim-derived follow-up",
        "request_intent_label": "Bounded follow-up",
        "request_guidance_summary": (
            "This request comes from the current claim set and should be treated as a bounded recommendation rather than a scheduled experiment."
        ),
    }


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
    intent_fields = _request_basis_and_intent_from_claim(claim)
    if intent_fields["request_guidance_summary"]:
        parts.append(intent_fields["request_guidance_summary"].rstrip(".") + ".")
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
    request_intent_fields = _request_basis_and_intent_from_claim(claim)
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
                "claim_support_quality_label": _clean_text(claim.get("claim_support_quality_label")),
                "claim_actionability_label": _clean_text(claim.get("claim_actionability_label")),
                "claim_actionability_basis_label": _clean_text(claim.get("claim_actionability_basis_label")),
                "claim_next_step_label": _clean_text(claim.get("claim_next_step_label")),
                "request_basis_label": request_intent_fields["request_basis_label"],
                "request_intent_label": request_intent_fields["request_intent_label"],
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


def experiment_request_refs_from_records(
    requests: list[dict[str, Any]],
    *,
    claim_refs_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    claim_refs_by_id = claim_refs_by_id if isinstance(claim_refs_by_id, dict) else {}
    refs: list[dict[str, Any]] = []
    for request in requests:
        if not isinstance(request, dict):
            continue
        candidate_reference = request.get("candidate_reference") if isinstance(request.get("candidate_reference"), dict) else {}
        metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
        claim_ref = claim_refs_by_id.get(_clean_text(request.get("claim_id"))) or {}
        request_intent_fields = _request_basis_and_intent_from_claim({**metadata, **claim_ref})
        refs.append(
            validate_experiment_request_reference(
                {
                    "experiment_request_id": request.get("experiment_request_id"),
                    "claim_id": request.get("claim_id"),
                    "candidate_id": request.get("candidate_id"),
                    "candidate_label": candidate_reference.get("candidate_label") or request.get("candidate_id"),
                    "requested_measurement": request.get("requested_measurement"),
                    "requested_direction": request.get("requested_direction"),
                    "request_basis_label": request_intent_fields["request_basis_label"],
                    "request_intent_label": request_intent_fields["request_intent_label"],
                    "request_guidance_summary": request_intent_fields["request_guidance_summary"],
                    "priority_tier": request.get("priority_tier"),
                    "status": request.get("status"),
                    "requested_at": request.get("requested_at"),
                }
            )
        )
    return refs


def experiment_request_summary_from_records(
    requests: list[dict[str, Any]],
    *,
    claim_refs_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    total = len(requests)
    proposed = sum(1 for request in requests if _clean_text(request.get("status")).lower() == ExperimentRequestStatus.proposed.value)
    accepted = sum(1 for request in requests if _clean_text(request.get("status")).lower() == ExperimentRequestStatus.accepted.value)
    rejected = sum(1 for request in requests if _clean_text(request.get("status")).lower() == ExperimentRequestStatus.rejected.value)
    completed = sum(1 for request in requests if _clean_text(request.get("status")).lower() == ExperimentRequestStatus.completed.value)
    superseded = sum(1 for request in requests if _clean_text(request.get("status")).lower() == ExperimentRequestStatus.superseded.value)
    refs = experiment_request_refs_from_records(requests, claim_refs_by_id=claim_refs_by_id)
    confirmatory = sum(1 for ref in refs if _clean_text(ref.get("request_intent_label")) == "Confirmatory follow-up")
    clarifying = sum(1 for ref in refs if _clean_text(ref.get("request_intent_label")) == "Clarifying follow-up")
    fresh_evidence = sum(1 for ref in refs if _clean_text(ref.get("request_intent_label")) == "Fresh-evidence follow-up")
    exploratory = sum(
        1
        for ref in refs
        if _clean_text(ref.get("request_intent_label")) in {"Exploratory follow-up", "Bounded follow-up", "Strengthening follow-up"}
    )
    if total:
        parts = [
            f"{total} proposed experiment request{'' if total == 1 else 's'} were derived from the current claims.",
            "These requests recommend next experiments; they are not scheduled or completed lab work.",
        ]
        intent_bits = []
        if confirmatory:
            intent_bits.append(f"{confirmatory} confirmatory")
        if clarifying:
            intent_bits.append(f"{clarifying} clarifying")
        if fresh_evidence:
            intent_bits.append(f"{fresh_evidence} fresh-evidence")
        if exploratory:
            intent_bits.append(f"{exploratory} exploratory or strengthening")
        if intent_bits:
            parts.append("Current request intent is bounded as " + ", ".join(intent_bits) + " follow-up.")
        summary_text = " ".join(parts)
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
            "confirmatory_request_count": confirmatory,
            "clarifying_request_count": clarifying,
            "fresh_evidence_request_count": fresh_evidence,
            "exploratory_request_count": exploratory,
            "summary_text": summary_text,
            "top_requests": refs[:3],
        }
    )


def attach_experiment_requests_to_scientific_session_truth(
    scientific_truth: dict[str, Any],
    experiment_requests: list[dict[str, Any]],
    *,
    claim_refs_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(scientific_truth, dict):
        return scientific_truth
    updated = dict(scientific_truth)
    updated["experiment_request_refs"] = experiment_request_refs_from_records(
        experiment_requests,
        claim_refs_by_id=claim_refs_by_id,
    )
    updated["experiment_request_summary"] = experiment_request_summary_from_records(
        experiment_requests,
        claim_refs_by_id=claim_refs_by_id,
    )
    return validate_scientific_session_truth(updated)


__all__ = [
    "attach_experiment_requests_to_scientific_session_truth",
    "build_experiment_request_record",
    "create_session_experiment_requests",
    "experiment_request_refs_from_records",
    "experiment_request_summary_from_records",
    "list_session_experiment_requests",
]
