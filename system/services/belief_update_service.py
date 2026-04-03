from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.contracts import (
    BeliefUpdateDirection,
    BeliefUpdateGovernanceStatus,
    ClaimStatus,
    EvidenceSupportLevel,
    validate_belief_update_record,
    validate_belief_update_reference,
    validate_belief_update_summary,
    validate_scientific_session_truth,
)
from system.db.repositories import BeliefUpdateRepository, ClaimRepository, ExperimentResultRepository
from system.services.belief_state_service import refresh_belief_state


belief_update_repository = BeliefUpdateRepository()
claim_repository = ClaimRepository()
experiment_result_repository = ExperimentResultRepository()

_SUPPORT_ORDER = (
    EvidenceSupportLevel.contextual.value,
    EvidenceSupportLevel.limited.value,
    EvidenceSupportLevel.moderate.value,
    EvidenceSupportLevel.strong.value,
)
_POSITIVE_LABELS = {"1", "true", "positive", "yes", "active", "pass", "hit", "confirmed"}
_NEGATIVE_LABELS = {"0", "false", "negative", "no", "inactive", "fail", "miss", "not_confirmed"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _candidate_label(claim_payload: dict[str, Any], experiment_result_payload: dict[str, Any]) -> str:
    result_reference = (
        experiment_result_payload.get("candidate_reference")
        if isinstance(experiment_result_payload.get("candidate_reference"), dict)
        else {}
    )
    claim_reference = claim_payload.get("candidate_reference") if isinstance(claim_payload.get("candidate_reference"), dict) else {}
    return _clean_text(
        result_reference.get("candidate_label")
        or claim_reference.get("candidate_label")
        or experiment_result_payload.get("candidate_id")
        or claim_payload.get("candidate_id")
    )


def _normalize_support_level(value: Any) -> str:
    token = _clean_text(value, default=EvidenceSupportLevel.limited.value).lower()
    if token in _SUPPORT_ORDER:
        return token
    return EvidenceSupportLevel.limited.value


def _step_support_level(level: str, direction: str) -> str:
    current = _normalize_support_level(level)
    index = _SUPPORT_ORDER.index(current)
    if direction == BeliefUpdateDirection.strengthened.value:
        return _SUPPORT_ORDER[min(index + 1, len(_SUPPORT_ORDER) - 1)]
    if direction == BeliefUpdateDirection.weakened.value:
        return _SUPPORT_ORDER[max(index - 1, 0)]
    return current


def _latest_support_level(workspace_id: str, claim_payload: dict[str, Any]) -> str:
    claim_id = _clean_text(claim_payload.get("claim_id"))
    if not claim_id:
        return EvidenceSupportLevel.limited.value
    prior_updates = belief_update_repository.list_belief_updates(
        workspace_id=workspace_id,
        claim_id=claim_id,
    )
    for update in prior_updates:
        if not isinstance(update, dict):
            continue
        governance = _clean_text(update.get("governance_status")).lower()
        if governance in {
            BeliefUpdateGovernanceStatus.rejected.value,
            BeliefUpdateGovernanceStatus.superseded.value,
        }:
            continue
        return _normalize_support_level(update.get("updated_support_level"))
    return _normalize_support_level(claim_payload.get("support_level"))


def _determine_update_direction(experiment_result_payload: dict[str, Any]) -> str:
    observed_label = _clean_text(experiment_result_payload.get("observed_label")).lower().replace(" ", "_")
    if observed_label in _POSITIVE_LABELS:
        return BeliefUpdateDirection.strengthened.value
    if observed_label in _NEGATIVE_LABELS:
        return BeliefUpdateDirection.weakened.value
    return BeliefUpdateDirection.unresolved.value


def _reason_text(
    *,
    direction: str,
    claim_payload: dict[str, Any],
    experiment_result_payload: dict[str, Any],
) -> str:
    label = _candidate_label(claim_payload, experiment_result_payload) or "This candidate"
    observed_label = _clean_text(experiment_result_payload.get("observed_label"))
    observed_value = experiment_result_payload.get("observed_value")
    if direction == BeliefUpdateDirection.strengthened.value:
        return (
            f"{label} now has an observed outcome aligned with the current claim framing, so this proposed belief update "
            "strengthens support in a bounded way. It does not prove the claim, establish causality, or change the model."
        )
    if direction == BeliefUpdateDirection.weakened.value:
        return (
            f"{label} now has an observed outcome that does not align with the current claim framing, so this proposed belief update "
            "weakens support in a bounded way. It does not disprove the broader objective or imply causality."
        )
    if observed_value is not None and observed_label:
        return (
            f"{label} now has a recorded numeric outcome and label, but this slice does not apply calibrated support thresholds to observed values. "
            "Support remains unresolved pending scientist interpretation."
        )
    if observed_value is not None:
        return (
            f"{label} now has a recorded numeric outcome, but this slice does not infer calibrated support changes from observed values alone. "
            "Support remains unresolved pending scientist interpretation."
        )
    return (
        f"{label} now has a recorded observed label '{observed_label or 'not recorded'}', but it does not map to an active support-change rule. "
        "Support remains unresolved pending scientist interpretation."
    )


def build_belief_update_record(
    *,
    session_id: str,
    workspace_id: str,
    claim_id: str = "",
    experiment_result_id: str = "",
    created_by: str = "scientist",
    created_by_user_id: str | None = None,
) -> dict[str, Any]:
    experiment_result_payload = (
        experiment_result_repository.get_experiment_result(experiment_result_id, workspace_id=workspace_id)
        if _clean_text(experiment_result_id)
        else {}
    )
    effective_claim_id = _clean_text(claim_id or experiment_result_payload.get("source_claim_id"))
    if not effective_claim_id:
        raise ValueError("BeliefUpdate requires a linked claim or an observed result already linked to a claim.")
    claim_payload = claim_repository.get_claim(effective_claim_id, workspace_id=workspace_id)
    if experiment_result_payload and _clean_text(experiment_result_payload.get("source_claim_id")):
        linked_claim_id = _clean_text(experiment_result_payload.get("source_claim_id"))
        if linked_claim_id and linked_claim_id != _clean_text(claim_payload.get("claim_id")):
            raise ValueError("BeliefUpdate claim/result linkage mismatch.")

    previous_support_level = _latest_support_level(workspace_id, claim_payload)
    update_direction = _determine_update_direction(experiment_result_payload)
    updated_support_level = _step_support_level(previous_support_level, update_direction)
    candidate_id = _clean_text(
        experiment_result_payload.get("candidate_id")
        or claim_payload.get("candidate_id")
    )
    candidate_label = _candidate_label(claim_payload, experiment_result_payload)
    created_at = _utc_now()

    return validate_belief_update_record(
        {
            "belief_update_id": "",
            "workspace_id": workspace_id,
            "session_id": session_id,
            "claim_id": effective_claim_id,
            "experiment_result_id": _clean_text(experiment_result_payload.get("experiment_result_id")),
            "candidate_id": candidate_id,
            "candidate_label": candidate_label,
            "previous_support_level": previous_support_level,
            "updated_support_level": updated_support_level,
            "update_direction": update_direction,
            "update_reason": _reason_text(
                direction=update_direction,
                claim_payload=claim_payload,
                experiment_result_payload=experiment_result_payload,
            ),
            "governance_status": BeliefUpdateGovernanceStatus.proposed.value,
            "created_at": created_at,
            "created_by": _clean_text(created_by, default="scientist"),
            "created_by_user_id": _clean_text(created_by_user_id),
            "reviewed_at": None,
            "reviewed_by": "",
            "metadata": {
                "claim_status": _clean_text(claim_payload.get("status"), default=ClaimStatus.proposed.value),
                "linked_result_quality": _clean_text(experiment_result_payload.get("result_quality")),
                "linked_result_source": _clean_text(experiment_result_payload.get("result_source")),
            },
        }
    )


def create_belief_update(
    *,
    session_id: str,
    workspace_id: str,
    claim_id: str = "",
    experiment_result_id: str = "",
    created_by: str = "scientist",
    created_by_user_id: str | None = None,
) -> dict[str, Any]:
    payload = build_belief_update_record(
        session_id=session_id,
        workspace_id=workspace_id,
        claim_id=claim_id,
        experiment_result_id=experiment_result_id,
        created_by=created_by,
        created_by_user_id=created_by_user_id,
    )
    created = belief_update_repository.upsert_belief_update(payload)
    refresh_belief_state(
        workspace_id=workspace_id,
        claim_id=_clean_text(created.get("claim_id")),
    )
    return created


def list_session_belief_updates(session_id: str, *, workspace_id: str | None = None) -> list[dict[str, Any]]:
    return belief_update_repository.list_belief_updates(session_id=session_id, workspace_id=workspace_id)


def belief_update_refs_from_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        refs.append(
            validate_belief_update_reference(
                {
                    "belief_update_id": record.get("belief_update_id"),
                    "claim_id": record.get("claim_id"),
                    "experiment_result_id": record.get("experiment_result_id"),
                    "candidate_id": record.get("candidate_id"),
                    "candidate_label": record.get("candidate_label"),
                    "previous_support_level": record.get("previous_support_level"),
                    "updated_support_level": record.get("updated_support_level"),
                    "update_direction": record.get("update_direction"),
                    "governance_status": record.get("governance_status"),
                    "created_at": record.get("created_at"),
                }
            )
        )
    return refs


def belief_update_summary_from_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    proposed = sum(
        1 for record in records if _clean_text(record.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.proposed.value
    )
    accepted = sum(
        1 for record in records if _clean_text(record.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.accepted.value
    )
    rejected = sum(
        1 for record in records if _clean_text(record.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.rejected.value
    )
    superseded = sum(
        1 for record in records if _clean_text(record.get("governance_status")).lower() == BeliefUpdateGovernanceStatus.superseded.value
    )
    strengthened = sum(
        1 for record in records if _clean_text(record.get("update_direction")).lower() == BeliefUpdateDirection.strengthened.value
    )
    weakened = sum(
        1 for record in records if _clean_text(record.get("update_direction")).lower() == BeliefUpdateDirection.weakened.value
    )
    unresolved = sum(
        1 for record in records if _clean_text(record.get("update_direction")).lower() == BeliefUpdateDirection.unresolved.value
    )
    if total:
        summary_text = (
            f"{total} belief update{'s' if total != 1 else ''} {'has' if total == 1 else 'have'} been recorded for this session. "
            "These updates track bounded support changes only; they do not prove claims, imply causality, or change the model."
        )
    else:
        summary_text = "No belief updates have been recorded."
    return validate_belief_update_summary(
        {
            "update_count": total,
            "proposed_count": proposed,
            "accepted_count": accepted,
            "rejected_count": rejected,
            "superseded_count": superseded,
            "strengthened_count": strengthened,
            "weakened_count": weakened,
            "unresolved_count": unresolved,
            "summary_text": summary_text,
            "top_updates": belief_update_refs_from_records(records[:3]),
        }
    )


def attach_belief_updates_to_scientific_session_truth(
    scientific_truth: dict[str, Any],
    updates: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(scientific_truth, dict):
        return scientific_truth
    updated = dict(scientific_truth)
    updated["belief_update_refs"] = belief_update_refs_from_records(updates)
    updated["belief_update_summary"] = belief_update_summary_from_records(updates)
    return validate_scientific_session_truth(updated)


__all__ = [
    "attach_belief_updates_to_scientific_session_truth",
    "belief_update_refs_from_records",
    "belief_update_summary_from_records",
    "build_belief_update_record",
    "create_belief_update",
    "list_session_belief_updates",
]
