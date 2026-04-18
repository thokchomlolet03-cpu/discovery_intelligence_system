from __future__ import annotations

from typing import Any
from uuid import uuid4

from system.db import ScientificStateRepository
from system.services.belief_state_service import apply_belief_update


scientific_state_repository = ScientificStateRepository()


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def create_experiment_request(*, claim: dict[str, Any], requested_measurement: str, rationale: str, created_by_user_id: str | None = None) -> dict[str, Any]:
    return scientific_state_repository.record_experiment_request(
        {
            "request_id": _make_id("exp_req"),
            "session_id": str(claim.get("session_id") or ""),
            "workspace_id": str(claim.get("workspace_id") or ""),
            "created_by_user_id": created_by_user_id or "",
            "claim_id": str(claim.get("claim_id") or ""),
            "candidate_id": str(claim.get("candidate_id") or ""),
            "canonical_smiles": str(claim.get("canonical_smiles") or ""),
            "objective": str(claim.get("claim_text") or "Test the linked claim").strip(),
            "rationale": rationale.strip(),
            "requested_measurement": requested_measurement.strip(),
            "status": "requested",
            "provenance_markers": {"request_source": "claim_service"},
        }
    )


def record_experiment_result(
    *,
    request: dict[str, Any],
    outcome: str,
    observed_value: float | None = None,
    observed_label: int | None = None,
    result_summary: dict[str, Any] | None = None,
    created_by_user_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    claim = scientific_state_repository.get_claim(claim_id=str(request.get("claim_id") or ""))
    result = scientific_state_repository.record_experiment_result(
        {
            "result_id": _make_id("exp_result"),
            "session_id": str(request.get("session_id") or ""),
            "workspace_id": str(request.get("workspace_id") or ""),
            "created_by_user_id": created_by_user_id or "",
            "request_id": str(request.get("request_id") or ""),
            "claim_id": str(request.get("claim_id") or ""),
            "candidate_id": str(request.get("candidate_id") or ""),
            "canonical_smiles": str(request.get("canonical_smiles") or ""),
            "outcome": outcome.strip(),
            "observed_value": observed_value,
            "observed_label": observed_label,
            "result_summary": dict(result_summary or {}),
            "provenance_markers": {"result_source": "experiment_service"},
            "status": "recorded",
        }
    )
    belief_state, belief_update = apply_belief_update(
        claim=claim,
        experiment_result=result,
        created_by_user_id=created_by_user_id,
    )
    scientific_state_repository.update_experiment_request_status(
        request_id=str(request.get("request_id") or ""),
        status="completed",
    )
    return result, belief_update, belief_state
