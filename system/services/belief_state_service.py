from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.contracts import (
    BeliefStateReference,
    validate_belief_state_record,
    validate_belief_state_reference,
    validate_belief_state_summary,
)
from system.db.repositories import BeliefStateRepository, BeliefUpdateRepository, ClaimRepository


belief_state_repository = BeliefStateRepository()
belief_update_repository = BeliefUpdateRepository()
claim_repository = ClaimRepository()


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


def build_target_key(target_definition: dict[str, Any] | None) -> str:
    target_definition = target_definition if isinstance(target_definition, dict) else {}
    parts = [
        _clean_text(target_definition.get("target_name"), default="target_not_recorded").lower(),
        _clean_text(target_definition.get("target_kind"), default="classification").lower(),
        _clean_text(target_definition.get("optimization_direction"), default="classify").lower(),
        _clean_text(target_definition.get("measurement_column")).lower(),
        _clean_text(target_definition.get("dataset_type")).lower(),
    ]
    return "|".join(part for part in parts if part)


def _claim_target_definition(claim_payload: dict[str, Any]) -> dict[str, Any]:
    snapshot = claim_payload.get("target_definition_snapshot")
    return snapshot if isinstance(snapshot, dict) else {}


def _active_updates_for_target(*, workspace_id: str, target_key: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    updates = belief_update_repository.list_belief_updates(workspace_id=workspace_id)
    latest_by_claim: dict[str, dict[str, Any]] = {}
    target_definition_snapshot: dict[str, Any] = {}
    for update in updates:
        if not isinstance(update, dict):
            continue
        claim_id = _clean_text(update.get("claim_id"))
        if not claim_id:
            continue
        try:
            claim_payload = claim_repository.get_claim(claim_id, workspace_id=workspace_id)
        except FileNotFoundError:
            continue
        claim_target_definition = _claim_target_definition(claim_payload)
        if build_target_key(claim_target_definition) != target_key:
            continue
        governance = _clean_text(update.get("governance_status")).lower()
        if governance in {"rejected", "superseded"}:
            continue
        if not target_definition_snapshot:
            target_definition_snapshot = claim_target_definition
        current = latest_by_claim.get(claim_id)
        if current is None or _clean_text(update.get("created_at")) > _clean_text(current.get("created_at")):
            latest_by_claim[claim_id] = update
    latest_updates = sorted(
        latest_by_claim.values(),
        key=lambda item: _clean_text(item.get("created_at")),
        reverse=True,
    )
    return latest_updates, target_definition_snapshot


def belief_state_reference_from_record(record: dict[str, Any]) -> dict[str, Any]:
    return validate_belief_state_reference(
        {
            "belief_state_id": record.get("belief_state_id"),
            "target_key": record.get("target_key"),
            "summary_text": record.get("summary_text"),
            "active_claim_count": record.get("active_claim_count"),
            "supported_claim_count": record.get("supported_claim_count"),
            "weakened_claim_count": record.get("weakened_claim_count"),
            "unresolved_claim_count": record.get("unresolved_claim_count"),
            "last_updated_at": record.get("last_updated_at"),
            "last_update_source": record.get("last_update_source"),
            "version": record.get("version"),
        }
    )


def belief_state_summary_from_record(record: dict[str, Any]) -> dict[str, Any]:
    return validate_belief_state_summary(
        {
            "summary_text": record.get("summary_text"),
            "support_distribution_summary": record.get("support_distribution_summary"),
            "governance_scope_summary": record.get("governance_scope_summary"),
            "active_claim_count": record.get("active_claim_count"),
            "supported_claim_count": record.get("supported_claim_count"),
            "weakened_claim_count": record.get("weakened_claim_count"),
            "unresolved_claim_count": record.get("unresolved_claim_count"),
            "last_updated_at": record.get("last_updated_at"),
            "last_update_source": record.get("last_update_source"),
        }
    )


def build_belief_state_record(
    *,
    workspace_id: str,
    target_definition_snapshot: dict[str, Any] | None,
    latest_updates: list[dict[str, Any]],
    previous_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target_definition_snapshot = target_definition_snapshot if isinstance(target_definition_snapshot, dict) else {}
    target_key = build_target_key(target_definition_snapshot)
    if not target_key:
        raise ValueError("BeliefState requires a target definition snapshot with a stable target key.")
    active_claim_count = len(latest_updates)
    supported_claim_count = sum(1 for update in latest_updates if _clean_text(update.get("update_direction")).lower() == "strengthened")
    weakened_claim_count = sum(1 for update in latest_updates if _clean_text(update.get("update_direction")).lower() == "weakened")
    unresolved_claim_count = sum(1 for update in latest_updates if _clean_text(update.get("update_direction")).lower() == "unresolved")
    proposed_count = sum(1 for update in latest_updates if _clean_text(update.get("governance_status")).lower() == "proposed")
    accepted_count = sum(1 for update in latest_updates if _clean_text(update.get("governance_status")).lower() == "accepted")
    last_update = latest_updates[0] if latest_updates else {}
    last_updated_at = last_update.get("created_at") or _utc_now()
    last_update_source = "latest belief update"
    if _clean_text(last_update.get("experiment_result_id")):
        last_update_source = "latest belief update linked to an observed result"
    target_name = _clean_text(target_definition_snapshot.get("target_name"), default="the current target objective")
    summary_text = (
        f"Current belief state for {target_name} tracks {active_claim_count} active claim{'s' if active_claim_count != 1 else ''}: "
        f"{supported_claim_count} strengthened, {weakened_claim_count} weakened, and {unresolved_claim_count} unresolved. "
        "This is a bounded support summary, not final scientific truth or live learning state."
    )
    support_distribution_summary = (
        f"Supported {supported_claim_count}, weakened {weakened_claim_count}, unresolved {unresolved_claim_count} across "
        f"{active_claim_count} currently tracked claim{'s' if active_claim_count != 1 else ''}."
    )
    governance_scope_summary = (
        f"Current picture includes {accepted_count} accepted and {proposed_count} proposed belief update"
        f"{'' if accepted_count + proposed_count == 1 else 's'}; rejected and superseded updates are excluded."
    )
    previous_version = _safe_int((previous_record or {}).get("version"), 0)
    return validate_belief_state_record(
        {
            "belief_state_id": _clean_text((previous_record or {}).get("belief_state_id")),
            "workspace_id": workspace_id,
            "target_key": target_key,
            "target_definition_snapshot": target_definition_snapshot,
            "summary_text": summary_text,
            "active_claim_count": active_claim_count,
            "supported_claim_count": supported_claim_count,
            "weakened_claim_count": weakened_claim_count,
            "unresolved_claim_count": unresolved_claim_count,
            "last_updated_at": last_updated_at,
            "last_update_source": last_update_source,
            "version": max(1, previous_version + 1),
            "latest_belief_update_refs": latest_updates[:3],
            "support_distribution_summary": support_distribution_summary,
            "governance_scope_summary": governance_scope_summary,
            "metadata": {
                "accepted_update_count": accepted_count,
                "proposed_update_count": proposed_count,
            },
        }
    )


def refresh_belief_state(
    *,
    workspace_id: str,
    target_definition_snapshot: dict[str, Any] | None = None,
    claim_id: str = "",
) -> dict[str, Any] | None:
    if not target_definition_snapshot and claim_id:
        claim_payload = claim_repository.get_claim(claim_id, workspace_id=workspace_id)
        target_definition_snapshot = _claim_target_definition(claim_payload)
    target_definition_snapshot = target_definition_snapshot if isinstance(target_definition_snapshot, dict) else {}
    target_key = build_target_key(target_definition_snapshot)
    if not target_key:
        return None
    latest_updates, effective_target_definition = _active_updates_for_target(
        workspace_id=workspace_id,
        target_key=target_key,
    )
    if not latest_updates:
        return None
    try:
        previous = belief_state_repository.get_belief_state(workspace_id=workspace_id, target_key=target_key)
    except FileNotFoundError:
        previous = None
    payload = build_belief_state_record(
        workspace_id=workspace_id,
        target_definition_snapshot=effective_target_definition or target_definition_snapshot,
        latest_updates=latest_updates,
        previous_record=previous,
    )
    return belief_state_repository.upsert_belief_state(payload)


def get_belief_state_for_target(
    *,
    workspace_id: str,
    target_definition_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    target_key = build_target_key(target_definition_snapshot)
    if not target_key:
        return None
    try:
        return belief_state_repository.get_belief_state(workspace_id=workspace_id, target_key=target_key)
    except FileNotFoundError:
        return None


__all__ = [
    "belief_state_reference_from_record",
    "belief_state_summary_from_record",
    "build_target_key",
    "get_belief_state_for_target",
    "refresh_belief_state",
]
