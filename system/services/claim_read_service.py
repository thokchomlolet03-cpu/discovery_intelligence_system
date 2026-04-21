from __future__ import annotations

from typing import Any

from system.db import ScientificStateRepository
from system.services.experiment_read_service import build_session_experiment_lifecycle_read_model


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


def _support_basis_summary(claim: dict[str, Any]) -> str:
    support_links = _as_dict(claim.get("support_links"))
    parts: list[str] = []
    if support_links.get("candidate_state"):
        parts.append("candidate canonical state")
    if support_links.get("run_metadata"):
        parts.append("run metadata")
    if support_links.get("recommendation_record"):
        parts.append("recommendation record")
    if support_links.get("model_output_record"):
        parts.append("model output record")
    if support_links.get("evidence_record"):
        parts.append("evidence record")
    if not parts:
        return "Canonical support links not recorded."
    return "Supported by " + ", ".join(parts) + "."


def _link_object_summary(link: dict[str, Any], evidence_lookup: dict[str, dict[str, Any]], model_output_lookup: dict[str, dict[str, Any]], recommendation_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    linked_object_type = _clean_text(link.get("linked_object_type"))
    linked_object_id = _clean_text(link.get("linked_object_id"))
    summary = {
        "linked_object_type": linked_object_type,
        "linked_object_id": linked_object_id,
        "relation_type": _clean_text(link.get("relation_type"), default="context_only"),
        "summary": _clean_text(link.get("summary")),
        "available": False,
        "label": "Linked support line",
        "context_bits": [],
    }
    if linked_object_type == "evidence":
        evidence = evidence_lookup.get(linked_object_id, {})
        summary["available"] = bool(evidence)
        summary["label"] = _clean_text(evidence.get("evidence_type"), default="evidence").replace("_", " ")
        summary["context_bits"] = [
            value
            for value in [
                f"row {evidence.get('source_row_index')}" if evidence.get("source_row_index") is not None else "",
                _clean_text(evidence.get("assay")),
                _clean_text(evidence.get("target_name")),
                f"value {evidence.get('observed_value')}" if evidence.get("observed_value") is not None else "",
                f"label {evidence.get('observed_label')}" if evidence.get("observed_label") not in (None, "") else "",
                _clean_text(evidence.get("source_column")),
            ]
            if value
        ]
    elif linked_object_type == "model_output":
        output = model_output_lookup.get(linked_object_id, {})
        summary["available"] = bool(output)
        summary["label"] = "model output"
        summary["context_bits"] = [
            value
            for value in [
                _clean_text(output.get("model_name")),
                f"confidence {output.get('confidence')}" if output.get("confidence") is not None else "",
                f"uncertainty {output.get('uncertainty')}" if output.get("uncertainty") is not None else "",
                f"predicted {output.get('predicted_value')}" if output.get("predicted_value") is not None else "",
            ]
            if value
        ]
    elif linked_object_type == "recommendation":
        recommendation = recommendation_lookup.get(linked_object_id, {})
        summary["available"] = bool(recommendation)
        summary["label"] = "recommendation"
        summary["context_bits"] = [
            value
            for value in [
                f"rank {recommendation.get('rank')}" if recommendation.get("rank") not in (None, "") else "",
                _clean_text(recommendation.get("bucket")),
                _clean_text(recommendation.get("risk")),
                _clean_text(recommendation.get("status")),
                f"priority {recommendation.get('priority_score')}" if recommendation.get("priority_score") is not None else "",
                f"experiment value {recommendation.get('experiment_value')}" if recommendation.get("experiment_value") is not None else "",
            ]
            if value
        ]
    return summary


def _contradiction_object_summary(
    contradiction: dict[str, Any],
    *,
    evidence_lookup: dict[str, dict[str, Any]],
    model_output_lookup: dict[str, dict[str, Any]],
    recommendation_lookup: dict[str, dict[str, Any]],
    result_lookup: dict[str, dict[str, Any]],
    update_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_object_type = _clean_text(contradiction.get("source_object_type"))
    source_object_id = _clean_text(contradiction.get("source_object_id"))
    summary = {
        "source_object_type": source_object_type,
        "source_object_id": source_object_id,
        "label": source_object_type.replace("_", " ") or "contradiction source",
        "context_bits": [],
    }
    if source_object_type == "evidence":
        evidence = evidence_lookup.get(source_object_id, {})
        summary["label"] = _clean_text(evidence.get("evidence_type"), default="evidence").replace("_", " ")
        summary["context_bits"] = [
            value for value in [
                f"row {evidence.get('source_row_index')}" if evidence.get("source_row_index") is not None else "",
                _clean_text(evidence.get("assay")),
                _clean_text(evidence.get("target_name")),
                f"value {evidence.get('observed_value')}" if evidence.get("observed_value") is not None else "",
            ] if value
        ]
    elif source_object_type == "model_output":
        output = model_output_lookup.get(source_object_id, {})
        summary["label"] = "model output"
        summary["context_bits"] = [
            value for value in [
                _clean_text(output.get("model_name")),
                f"predicted {output.get('predicted_value')}" if output.get("predicted_value") is not None else "",
                f"confidence {output.get('confidence')}" if output.get("confidence") is not None else "",
            ] if value
        ]
    elif source_object_type == "recommendation":
        recommendation = recommendation_lookup.get(source_object_id, {})
        summary["label"] = "recommendation"
        summary["context_bits"] = [
            value for value in [
                f"rank {recommendation.get('rank')}" if recommendation.get("rank") not in (None, "") else "",
                _clean_text(recommendation.get("bucket")),
                _clean_text(recommendation.get("status")),
            ] if value
        ]
    elif source_object_type == "experiment_result":
        result = result_lookup.get(source_object_id, {})
        summary["label"] = "experiment result"
        summary["context_bits"] = [
            value for value in [
                _clean_text(result.get("outcome")),
                f"value {result.get('observed_value')}" if result.get("observed_value") is not None else "",
                f"label {result.get('observed_label')}" if result.get("observed_label") not in (None, "") else "",
            ] if value
        ]
    elif source_object_type == "belief_update":
        update = update_lookup.get(source_object_id, {})
        summary["label"] = "belief update"
        summary["context_bits"] = [
            value for value in [
                _clean_text(update.get("deterministic_rule")),
                _clean_text(update.get("update_reason")),
            ] if value
        ]
    return summary


def _candidate_context_for_claim(claim: dict[str, Any], candidate_states: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_id = _clean_text(claim.get("candidate_id"))
    canonical_smiles = _clean_text(claim.get("canonical_smiles"))
    candidate_state = next(
        (
            item
            for item in candidate_states
            if _clean_text(item.get("candidate_id")) == candidate_id
            or (_clean_text(item.get("canonical_smiles")) and _clean_text(item.get("canonical_smiles")) == canonical_smiles)
        ),
        {},
    )
    if not candidate_state:
        return {
            "available": False,
            "candidate_id": candidate_id,
            "canonical_smiles": canonical_smiles,
            "absence_reason": "candidate_canonical_state_missing",
            "provenance": "absent",
        }

    predictive = _as_dict(candidate_state.get("predictive_summary"))
    recommendation = _as_dict(candidate_state.get("recommendation_summary"))
    governance = _as_dict(candidate_state.get("governance_summary"))
    carryover = _as_dict(candidate_state.get("carryover_summary"))
    trust = _as_dict(candidate_state.get("trust_summary"))
    return {
        "available": True,
        "candidate_id": _clean_text(candidate_state.get("candidate_id")),
        "canonical_smiles": _clean_text(candidate_state.get("canonical_smiles")),
        "rank": candidate_state.get("rank"),
        "recommendation_summary": {
            "bucket": _clean_text(recommendation.get("bucket")),
            "risk": _clean_text(recommendation.get("risk")),
            "status": _clean_text(recommendation.get("status")),
            "priority_score": recommendation.get("priority_score"),
            "experiment_value": recommendation.get("experiment_value"),
        },
        "predictive_summary": {
            "confidence": predictive.get("confidence"),
            "uncertainty": predictive.get("uncertainty"),
            "predicted_value": predictive.get("predicted_value"),
            "novelty": predictive.get("novelty"),
        },
        "governance_summary": {
            "status": _clean_text(governance.get("status")),
            "reviewed_at": _to_iso(governance.get("reviewed_at")),
        },
        "carryover_summary": {
            "record_count": carryover.get("record_count"),
            "continuity_source": _clean_text(carryover.get("continuity_source")),
        },
        "trust_summary": {
            "trust_label": _clean_text(trust.get("trust_label")),
            "trust_summary": _clean_text(trust.get("trust_summary")),
        },
        "provenance": "canonical_candidate_state",
    }


def _run_context_for_claim(claim: dict[str, Any], run_metadata: dict[str, Any]) -> dict[str, Any]:
    if not run_metadata:
        return {
            "available": False,
            "session_id": _clean_text(claim.get("session_id")),
            "absence_reason": "canonical_run_metadata_missing",
            "provenance": "absent",
        }

    trust_summary = _as_dict(run_metadata.get("trust_summary"))
    comparison_anchors = _as_dict(run_metadata.get("comparison_anchors"))
    return {
        "available": True,
        "session_id": _clean_text(run_metadata.get("session_id") or claim.get("session_id")),
        "modeling_mode": _clean_text(run_metadata.get("modeling_mode")),
        "scoring_mode": _clean_text(run_metadata.get("scoring_mode")),
        "comparison_summary": {
            "comparison_ready": bool(comparison_anchors.get("comparison_ready")),
            "target_name": _clean_text(comparison_anchors.get("target_name")),
            "target_kind": _clean_text(comparison_anchors.get("target_kind")),
        },
        "trust_summary": {
            "bridge_state_summary": _clean_text(trust_summary.get("bridge_state_summary")),
            "baseline_fallback_visible": bool(trust_summary.get("baseline_fallback_visible")),
        },
        "provenance": "canonical_persisted_run_metadata",
    }


def build_claim_detail_read_model(*, claim_id: str) -> dict[str, Any]:
    try:
        claim = scientific_state_repository.get_claim(claim_id=claim_id)
    except FileNotFoundError:
        return {
            "available": False,
            "claim_id": claim_id,
            "absence_reason": "claim_not_found",
            "diagnostics": {"detail_source": "absent"},
        }

    session_id = _clean_text(claim.get("session_id"))
    workspace_id = _clean_text(claim.get("workspace_id")) or None
    candidate_states = scientific_state_repository.list_candidate_states(session_id=session_id, workspace_id=workspace_id)
    try:
        run_metadata = scientific_state_repository.get_run_metadata(session_id=session_id, workspace_id=workspace_id)
    except FileNotFoundError:
        run_metadata = {}

    requests = scientific_state_repository.list_experiment_requests(claim_id=claim_id)
    results = scientific_state_repository.list_experiment_results(claim_id=claim_id)
    updates = scientific_state_repository.list_belief_updates(claim_id=claim_id)
    claim_links = scientific_state_repository.list_claim_evidence_links(claim_id=claim_id)
    contradictions = scientific_state_repository.list_contradictions(claim_id=claim_id)
    try:
        belief_state = scientific_state_repository.get_belief_state(claim_id=claim_id)
    except FileNotFoundError:
        belief_state = {}
    experiment_lifecycle = build_session_experiment_lifecycle_read_model(session_id=session_id, workspace_id=workspace_id)
    lifecycle_claim = next(
        (
            item
            for item in experiment_lifecycle.get("claim_items", [])
            if _clean_text(item.get("claim_id")) == claim_id
        ),
        {},
    )
    lifecycle_item_by_request = {
        _clean_text(item.get("request_id")): item
        for item in experiment_lifecycle.get("experiment_items", [])
        if _clean_text(item.get("request_id"))
    }
    evidence_lookup = {
        _clean_text(item.get("record_id")): item
        for item in scientific_state_repository.list_evidence_records(session_id=session_id, workspace_id=workspace_id)
        if _clean_text(item.get("record_id"))
    }
    model_output_lookup = {
        _clean_text(item.get("record_id")): item
        for item in scientific_state_repository.list_model_outputs(session_id=session_id, workspace_id=workspace_id)
        if _clean_text(item.get("record_id"))
    }
    recommendation_lookup = {
        _clean_text(item.get("record_id")): item
        for item in scientific_state_repository.list_recommendations(session_id=session_id, workspace_id=workspace_id)
        if _clean_text(item.get("record_id"))
    }

    claim_scope = _clean_text(claim.get("claim_scope"))
    candidate_context = _candidate_context_for_claim(claim, candidate_states) if claim_scope == "candidate" else {
        "available": False,
        "absence_reason": "not_candidate_linked",
        "provenance": "not_applicable",
    }
    run_context = _run_context_for_claim(claim, run_metadata) if claim_scope == "run" else {
        "available": False,
        "absence_reason": "not_run_linked",
        "provenance": "not_applicable",
    }

    request_items = [
        {
            "request_id": _clean_text(item.get("request_id")),
            "status": _clean_text(item.get("status"), default="requested"),
            "objective": _clean_text(item.get("objective")),
            "rationale": _clean_text(item.get("rationale")),
            "requested_measurement": _clean_text(item.get("requested_measurement")),
            "created_at": _to_iso(item.get("created_at")),
            "updated_at": _to_iso(item.get("updated_at")),
            "provenance": "canonical_experiment_request",
        }
        for item in requests
    ]
    result_items = [
        {
            "result_id": _clean_text(item.get("result_id")),
            "request_id": _clean_text(item.get("request_id")),
            "status": _clean_text(item.get("status"), default="recorded"),
            "outcome": _clean_text(item.get("outcome")),
            "observed_value": item.get("observed_value"),
            "observed_label": _clean_text(item.get("observed_label")),
            "result_summary": _as_dict(item.get("result_summary")),
            "created_at": _to_iso(item.get("created_at")),
            "updated_at": _to_iso(item.get("updated_at")),
            "provenance": "canonical_experiment_result",
        }
        for item in results
    ]
    update_items = [
        {
            "update_id": _clean_text(item.get("update_id")),
            "result_id": _clean_text(item.get("result_id")),
            "update_reason": _clean_text(item.get("update_reason")),
            "deterministic_rule": _clean_text(item.get("deterministic_rule")),
            "revision_mode": _clean_text(item.get("revision_mode"), default="bounded_contradiction_aware"),
            "contradiction_pressure": _clean_text(item.get("contradiction_pressure"), default="none"),
            "support_balance_summary": _clean_text(item.get("support_balance_summary")),
            "revision_rationale": _clean_text(item.get("revision_rationale")),
            "triggering_contradiction_ids": item.get("triggering_contradiction_ids") if isinstance(item.get("triggering_contradiction_ids"), list) else [],
            "triggering_source_summary": _clean_text(item.get("triggering_source_summary")),
            "pre_belief_state": _as_dict(item.get("pre_belief_state")),
            "post_belief_state": _as_dict(item.get("post_belief_state")),
            "created_at": _to_iso(item.get("created_at")),
            "updated_at": _to_iso(item.get("updated_at")),
            "provenance": "canonical_belief_update",
        }
        for item in updates
    ]
    result_lookup = {_clean_text(item.get("result_id")): item for item in results if _clean_text(item.get("result_id"))}
    update_lookup = {_clean_text(item.get("update_id")): item for item in updates if _clean_text(item.get("update_id"))}
    link_items = [
        {
            "link_id": _clean_text(item.get("link_id")),
            "linked_object_type": _clean_text(item.get("linked_object_type")),
            "linked_object_id": _clean_text(item.get("linked_object_id")),
            "relation_type": _clean_text(item.get("relation_type"), default="context_only"),
            "summary": _clean_text(item.get("summary")),
            "created_at": _to_iso(item.get("created_at")),
            "updated_at": _to_iso(item.get("updated_at")),
            "object_summary": _link_object_summary(item, evidence_lookup, model_output_lookup, recommendation_lookup),
            "provenance": "canonical_claim_evidence_link",
        }
        for item in claim_links
    ]
    contradiction_items = [
        {
            "contradiction_id": _clean_text(item.get("contradiction_id")),
            "contradiction_scope": _clean_text(item.get("contradiction_scope"), default="claim"),
            "contradiction_type": _clean_text(item.get("contradiction_type"), default="unknown"),
            "source_object_type": _clean_text(item.get("source_object_type"), default="unknown"),
            "source_object_id": _clean_text(item.get("source_object_id")),
            "status": _clean_text(item.get("status"), default="unresolved"),
            "summary": _clean_text(item.get("summary")),
            "created_at": _to_iso(item.get("created_at")),
            "updated_at": _to_iso(item.get("updated_at")),
            "object_summary": _contradiction_object_summary(
                item,
                evidence_lookup=evidence_lookup,
                model_output_lookup=model_output_lookup,
                recommendation_lookup=recommendation_lookup,
                result_lookup=result_lookup,
                update_lookup=update_lookup,
            ),
            "provenance": "canonical_contradiction",
        }
        for item in contradictions
    ]
    grouped_link_counts: dict[str, int] = {}
    for item in link_items:
        relation_type = item["relation_type"]
        grouped_link_counts[relation_type] = grouped_link_counts.get(relation_type, 0) + 1

    return {
        "available": True,
        "claim_id": claim_id,
        "claim": {
            "claim_id": claim_id,
            "claim_type": _clean_text(claim.get("claim_type")),
            "claim_status": _clean_text(claim.get("status"), default="active"),
            "claim_scope": claim_scope,
            "claim_text": _clean_text(claim.get("claim_text")),
            "claim_summary": _as_dict(claim.get("claim_summary")),
            "source_basis": _clean_text(claim.get("source_basis")),
            "provenance_markers": _as_dict(claim.get("provenance_markers")),
            "created_at": _to_iso(claim.get("created_at")),
            "updated_at": _to_iso(claim.get("updated_at")),
        },
        "attachment_context": {
            "session_id": session_id,
            "workspace_id": _clean_text(claim.get("workspace_id")),
            "candidate_context": candidate_context,
            "run_context": run_context,
            "support_links": _as_dict(claim.get("support_links")),
            "support_basis_summary": _support_basis_summary(claim),
            "claim_evidence_link_count": len(link_items),
            "claim_evidence_relation_counts": grouped_link_counts,
            "claim_evidence_links": link_items,
            "contradiction_count": len(contradiction_items),
            "active_contradiction_count": sum(1 for item in contradiction_items if item["status"] in {"active", "unresolved"}),
            "contradictions": contradiction_items,
            "provenance": "canonical_epistemic_objects",
        },
        "experiment_detail": {
            "request_count": len(request_items),
            "result_count": len(result_items),
            "pending_request_count": sum(1 for item in request_items if item["status"] != "completed"),
            "has_requests": bool(request_items),
            "has_results": bool(result_items),
            "absence_reason": "" if request_items or result_items else "no_linked_experiments",
            "requests": request_items,
            "results": result_items,
            "lifecycle_summary": lifecycle_claim,
            "lifecycle_items": [
                lifecycle_item_by_request[_clean_text(item.get("request_id"))]
                for item in request_items
                if _clean_text(item.get("request_id")) in lifecycle_item_by_request
            ],
        },
        "belief_update_summary": {
            "update_count": len(update_items),
            "has_updates": bool(update_items),
            "absence_reason": "" if update_items else "no_belief_updates",
            "latest_update_id": _clean_text(update_items[-1].get("update_id")) if update_items else "",
            "items": update_items,
        },
        "current_belief_state": {
            "available": bool(belief_state),
            "current_state": _clean_text(belief_state.get("current_state"), default="absent"),
            "current_strength": _clean_text(belief_state.get("current_strength"), default="absent"),
            "support_basis_summary": _clean_text(belief_state.get("support_basis_summary")),
            "contradiction_pressure": _clean_text(belief_state.get("contradiction_pressure"), default="none"),
            "support_balance_summary": _clean_text(belief_state.get("support_balance_summary")),
            "latest_revision_rationale": _clean_text(belief_state.get("latest_revision_rationale")),
            "latest_update_id": _clean_text(belief_state.get("latest_update_id")),
            "status": _clean_text(belief_state.get("status"), default="absent"),
            "updated_at": _to_iso(belief_state.get("updated_at")),
            "absence_reason": "" if belief_state else "belief_state_absent",
            "provenance": "canonical_belief_state" if belief_state else "absent",
        },
        "diagnostics": {
            "detail_source": "canonical_epistemic_objects",
            "has_claim_evidence_links": bool(link_items),
            "has_experiment_requests": bool(request_items),
            "has_experiment_results": bool(result_items),
            "has_belief_updates": bool(update_items),
            "has_belief_state": bool(belief_state),
            "has_contradictions": bool(contradiction_items),
            "experiment_lifecycle_unresolved_state": _clean_text(lifecycle_claim.get("unresolved_state"), default="no_experiment_request"),
        },
    }


def build_session_claim_detail_items(*, session_id: str, workspace_id: str | None = None) -> list[dict[str, Any]]:
    claims = scientific_state_repository.list_claims(session_id=session_id, workspace_id=workspace_id)
    return [
        build_claim_detail_read_model(claim_id=_clean_text(item.get("claim_id")))
        for item in claims
        if _clean_text(item.get("claim_id"))
    ]
