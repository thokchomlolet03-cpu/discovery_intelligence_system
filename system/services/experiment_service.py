from __future__ import annotations

from typing import Any
from uuid import uuid4

from system.db import ScientificStateRepository
from system.services.belief_state_service import apply_belief_update
from system.services.contradiction_service import build_session_contradictions


scientific_state_repository = ScientificStateRepository()


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _claim_link_snapshot(claim: dict[str, Any]) -> list[dict[str, str]]:
    claim_id = _clean_text(claim.get("claim_id"))
    if not claim_id:
        return []
    links = scientific_state_repository.list_claim_evidence_links(claim_id=claim_id)
    snapshot: list[dict[str, str]] = []
    for link in links[:6]:
        if not isinstance(link, dict):
            continue
        snapshot.append(
            {
                "linked_object_type": _clean_text(link.get("linked_object_type"), default="unknown"),
                "relation_type": _clean_text(link.get("relation_type"), default="context_only"),
                "summary": _clean_text(link.get("summary"), default="Linked context recorded."),
            }
        )
    return snapshot


def _existing_context_summary(claim: dict[str, Any], link_snapshot: list[dict[str, str]]) -> str:
    basis = _clean_text(claim.get("source_basis"))
    claim_summary = claim.get("claim_summary") if isinstance(claim.get("claim_summary"), dict) else {}
    support_text = _clean_text(claim_summary.get("support_basis_summary"))
    relation_counts: dict[str, int] = {}
    for item in link_snapshot:
        relation = _clean_text(item.get("relation_type"), default="context_only")
        relation_counts[relation] = relation_counts.get(relation, 0) + 1
    relation_summary = ", ".join(f"{count} {relation.replace('_', ' ')}" for relation, count in sorted(relation_counts.items()))
    parts = [part for part in [support_text, f"Claim basis: {basis}." if basis else "", f"Attached context lines: {relation_summary}." if relation_summary else ""] if part]
    return " ".join(parts).strip() or "Existing claim context is limited to the currently persisted claim and linked support lines."


def _strengthening_outcome_description(claim: dict[str, Any], requested_measurement: str) -> str:
    measurement = _clean_text(requested_measurement, default="the requested measurement")
    claim_text = _clean_text(claim.get("claim_text"), default="the linked claim")
    return f"Results from {measurement} that remain directionally consistent with {claim_text} would strengthen this claim within the current bridge-state logic."


def _weakening_outcome_description(claim: dict[str, Any], requested_measurement: str) -> str:
    measurement = _clean_text(requested_measurement, default="the requested measurement")
    claim_text = _clean_text(claim.get("claim_text"), default="the linked claim")
    return f"Results from {measurement} that materially conflict with {claim_text} would weaken or challenge this claim within the current bridge-state logic."


def _expected_learning_value(link_snapshot: list[dict[str, str]]) -> str:
    if not link_snapshot:
        return "This experiment primarily reduces uncertainty around a claim that currently has little attached context."
    relation_counts: dict[str, int] = {}
    for item in link_snapshot:
        relation = _clean_text(item.get("relation_type"), default="context_only")
        relation_counts[relation] = relation_counts.get(relation, 0) + 1
    if relation_counts.get("derived_from", 0) and not relation_counts.get("supports", 0):
        return "This experiment helps distinguish a recommendation-derived claim from stronger evidence-backed support."
    return "This experiment helps test whether the current attached claim context should remain trusted, weakened, or revised."


def create_experiment_request(*, claim: dict[str, Any], requested_measurement: str, rationale: str, created_by_user_id: str | None = None) -> dict[str, Any]:
    link_snapshot = _claim_link_snapshot(claim)
    claim_id = _clean_text(claim.get("claim_id"))
    measurement = requested_measurement.strip()
    return scientific_state_repository.record_experiment_request(
        {
            "request_id": _make_id("exp_req"),
            "session_id": str(claim.get("session_id") or ""),
            "workspace_id": str(claim.get("workspace_id") or ""),
            "created_by_user_id": created_by_user_id or "",
            "claim_id": claim_id,
            "tested_claim_id": claim_id,
            "candidate_id": str(claim.get("candidate_id") or ""),
            "canonical_smiles": str(claim.get("canonical_smiles") or ""),
            "objective": str(claim.get("claim_text") or "Test the linked claim").strip(),
            "rationale": rationale.strip(),
            "requested_measurement": measurement,
            "experiment_intent": "claim_test",
            "epistemic_goal_summary": "Reduce uncertainty around the linked claim by collecting a directly relevant experimental observation.",
            "existing_context_summary": _existing_context_summary(claim, link_snapshot),
            "strengthening_outcome_description": _strengthening_outcome_description(claim, measurement),
            "weakening_outcome_description": _weakening_outcome_description(claim, measurement),
            "expected_learning_value": _expected_learning_value(link_snapshot),
            "linked_claim_evidence_snapshot": link_snapshot,
            "protocol_context_summary": _clean_text(claim.get("canonical_smiles"))
            and f"Candidate scope is anchored to {str(claim.get('canonical_smiles') or '').strip()}."
            or "",
            "status": "requested",
            "provenance_markers": {
                "request_source": "claim_service",
                "claim_evidence_snapshot_used": bool(link_snapshot),
                "epistemic_request_mode": "bridge_state_claim_test",
            },
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
    session_id = str(request.get("session_id") or "")
    workspace_id = str(request.get("workspace_id") or "")
    if session_id and workspace_id:
        claims = scientific_state_repository.list_claims(session_id=session_id, workspace_id=workspace_id)
        claim_evidence_links = scientific_state_repository.list_claim_evidence_links(session_id=session_id, workspace_id=workspace_id)
        experiment_results = scientific_state_repository.list_experiment_results(claim_id=None)
        experiment_results = [
            item
            for item in experiment_results
            if str(item.get("session_id") or "").strip() == session_id
            and str(item.get("workspace_id") or "").strip() == workspace_id
        ]
        belief_updates = scientific_state_repository.list_belief_updates(claim_id=None)
        belief_updates = [
            item
            for item in belief_updates
            if str(item.get("session_id") or "").strip() == session_id
            and str(item.get("workspace_id") or "").strip() == workspace_id
        ]
        scientific_state_repository.replace_contradictions(
            session_id=session_id,
            workspace_id=workspace_id,
            payloads=build_session_contradictions(
                session_id=session_id,
                workspace_id=workspace_id,
                created_by_user_id=created_by_user_id,
                claims=claims,
                claim_evidence_links=claim_evidence_links,
                experiment_results=experiment_results,
                belief_updates=belief_updates,
            ),
        )
    return result, belief_update, belief_state
