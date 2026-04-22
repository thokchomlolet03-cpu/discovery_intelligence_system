from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.scientific_state.contracts import (
    MaterialGoalEvidenceLineRecord,
    MaterialGoalRequirementSupportTraceRecord,
    MaterialGoalSupportTraceRecord,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _query_terms(query_summary: dict[str, Any], key: str) -> list[str]:
    grouped = query_summary.get("grouped_terms") if isinstance(query_summary.get("grouped_terms"), dict) else {}
    values = grouped.get(key)
    return [str(item).strip().lower() for item in values if str(item).strip()] if isinstance(values, list) else []


def _dimension_config() -> list[tuple[str, str, bool]]:
    return [
        ("desired_properties", "Target properties / performance requirements", True),
        ("operating_environment", "Environment compatibility", True),
        ("lifecycle_window", "Lifecycle / degradation context", True),
        ("trigger_conditions", "Trigger / condition requirements", False),
        ("safety_or_regulatory_constraints", "Safety / regulatory constraints", False),
        ("target_material_function", "Target material function", True),
    ]


def _support_lines_for_terms(direction: dict[str, Any], requirement_terms: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    matched: list[dict[str, Any]] = []
    observed: list[dict[str, Any]] = []
    indirect: list[dict[str, Any]] = []
    lowered_terms = {term.lower() for term in requirement_terms if term}
    for line in _as_list(direction.get("supporting_evidence_lines")):
        if not isinstance(line, dict):
            continue
        line_terms = {str(item).strip().lower() for item in _as_list(line.get("matched_terms")) if str(item).strip()}
        if not (line_terms & lowered_terms):
            continue
        matched.append(line)
        if _clean_text(line.get("evidence_kind")) == "observed":
            observed.append(line)
        else:
            indirect.append(line)
    return matched, observed, indirect


def _dimension_contradictions(
    *,
    requirement_key: str,
    requirement_terms: list[str],
    direction: dict[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    contradictions = [
        item
        for item in _as_list(direction.get("contradiction_indicators"))
        if isinstance(item, dict) and _clean_text(item.get("status")).lower() in {"active", "unresolved"}
    ]
    if not contradictions:
        return [], False
    term_set = {term.lower() for term in requirement_terms if term}
    attributed: list[dict[str, Any]] = []
    coarse_only = False
    for item in contradictions:
        summary = _clean_text(item.get("summary")).lower()
        if term_set and any(term in summary for term in term_set):
            attributed.append(item)
            continue
        if requirement_key == "operating_environment" and any(token in summary for token in {"environment", "humid", "temperature", "water", "solvent"}):
            attributed.append(item)
            continue
        if requirement_key == "lifecycle_window" and any(token in summary for token in {"lifecycle", "degradation", "stable", "stability", "compost"}):
            attributed.append(item)
            continue
        if requirement_key == "trigger_conditions" and any(token in summary for token in {"trigger", "ph", "humidity", "temperature", "light", "uv"}):
            attributed.append(item)
            continue
        if requirement_key == "safety_or_regulatory_constraints" and any(token in summary for token in {"safety", "toxicity", "regulatory", "food contact", "medical"}):
            attributed.append(item)
            continue
        if requirement_key == "desired_properties" and any(token in summary for token in {"barrier", "strength", "flexible", "property"}):
            attributed.append(item)
            continue
        coarse_only = True
    return attributed, coarse_only and not attributed


def _gap_codes(requirement_key: str, *, uncovered_terms: list[str], observed_support_lines: list[dict[str, Any]], indirect_support_lines: list[dict[str, Any]], contradictions: list[dict[str, Any]], retrieval_sufficiency: str) -> list[str]:
    gaps: list[str] = []
    if contradictions:
        gaps.append("unresolved_contradiction_pressure")
    if uncovered_terms:
        dimension_gap_map = {
            "desired_properties": "insufficient_property_support",
            "operating_environment": "weak_environmental_match",
            "lifecycle_window": "weak_lifecycle_match",
            "trigger_conditions": "weak_trigger_match",
            "safety_or_regulatory_constraints": "safety_or_regulatory_gap",
            "target_material_function": "missing_grounded_material_direction",
        }
        gaps.append(dimension_gap_map.get(requirement_key, "incomplete_term_coverage"))
        gaps.append("incomplete_term_coverage")
    if indirect_support_lines and not observed_support_lines:
        gaps.append("only_indirect_support")
    if retrieval_sufficiency == "weak_partial_evidence" or (len(observed_support_lines) + len(indirect_support_lines)) <= 1:
        gaps.append("sparse_evidence_basis")
    return sorted(dict.fromkeys(gaps))


def _support_status(requirement_terms: list[str], uncovered_terms: list[str], observed_support_lines: list[dict[str, Any]], indirect_support_lines: list[dict[str, Any]], contradictions: list[dict[str, Any]]) -> tuple[str, str, str]:
    if not requirement_terms:
        return (
            "not_applicable",
            "requirement_not_stated",
            "This requirement dimension was not explicitly stated in the current material goal.",
        )
    if contradictions:
        return (
            "contradicted",
            "contradiction_attached_to_dimension",
            "Contradiction pressure is attached to this requirement dimension, so it cannot be treated as supported.",
        )
    if observed_support_lines and not uncovered_terms:
        return (
            "supported",
            "observed_dimension_support",
            "Observed support lines cover the stated requirement terms for this dimension.",
        )
    if observed_support_lines or indirect_support_lines:
        return (
            "partially_supported",
            "partial_or_indirect_dimension_support",
            "Some support exists for this requirement dimension, but coverage remains partial or indirect.",
        )
    return (
        "unknown",
        "no_dimension_support",
        "No matched support lines currently ground this requirement dimension.",
    )


def build_material_goal_support_trace(
    *,
    session_id: str,
    workspace_id: str,
    goal_specification: dict[str, Any] | None,
    retrieval_result: dict[str, Any] | None,
) -> dict[str, Any]:
    goal_spec = goal_specification if isinstance(goal_specification, dict) else {}
    retrieval = retrieval_result if isinstance(retrieval_result, dict) else {}
    directions = [item for item in _as_list(retrieval.get("candidate_material_directions")) if isinstance(item, dict)]
    top_direction = directions[0] if directions else {}
    query_summary = _as_dict(retrieval.get("query_summary"))
    traces: list[dict[str, Any]] = []

    for requirement_key, requirement_label, critical in _dimension_config():
        requirement_terms = _query_terms(query_summary, requirement_key)
        matched_lines, observed_lines, indirect_lines = _support_lines_for_terms(top_direction, requirement_terms)
        matched_terms = {
            str(term).strip().lower()
            for line in matched_lines
            for term in _as_list(_as_dict(line).get("matched_terms"))
            if str(term).strip()
        }
        uncovered_terms = [term for term in requirement_terms if term not in matched_terms]
        contradictions, coarse_only = _dimension_contradictions(
            requirement_key=requirement_key,
            requirement_terms=requirement_terms,
            direction=top_direction,
        )
        support_status, support_basis_classification, rationale_summary = _support_status(
            requirement_terms,
            uncovered_terms,
            observed_lines,
            indirect_lines,
            contradictions,
        )
        gap_codes = _gap_codes(
            requirement_key,
            uncovered_terms=uncovered_terms,
            observed_support_lines=observed_lines,
            indirect_support_lines=indirect_lines,
            contradictions=contradictions,
            retrieval_sufficiency=_clean_text(retrieval.get("retrieval_sufficiency")),
        )
        traces.append(
            MaterialGoalRequirementSupportTraceRecord(
                requirement_key=requirement_key,
                requirement_label=requirement_label,
                requirement_terms=requirement_terms,
                support_status=support_status,
                support_basis_classification=support_basis_classification,
                rationale_summary=rationale_summary,
                matched_support_lines=[MaterialGoalEvidenceLineRecord(**item) for item in matched_lines[:4]],
                observed_support_lines=[MaterialGoalEvidenceLineRecord(**item) for item in observed_lines[:4]],
                indirect_support_lines=[MaterialGoalEvidenceLineRecord(**item) for item in indirect_lines[:4]],
                contradiction_indicators=contradictions[:4],
                uncovered_requirement_terms=uncovered_terms,
                gap_codes=gap_codes,
                provenance={
                    "critical_dimension": critical,
                    "contradiction_attribution": "dimension_specific" if contradictions else ("coarse_direction_level_only" if coarse_only else "none"),
                },
            ).dict()
        )

    return MaterialGoalSupportTraceRecord(
        goal_id=_clean_text(goal_spec.get("goal_id")),
        session_id=session_id,
        workspace_id=workspace_id,
        top_direction_id=_clean_text(top_direction.get("direction_id")),
        top_direction_label=_clean_text(top_direction.get("direction_label")),
        top_direction_support_strength=_clean_text(top_direction.get("support_strength"), default="thin"),
        requirement_traces=[MaterialGoalRequirementSupportTraceRecord(**item) for item in traces],
        trace_provenance={
            "trace_mode": "bounded_first_battlefield_requirement_support_trace",
            "recomputed": True,
            "goal_requirement_status": _clean_text(goal_spec.get("requirement_status")),
            "retrieval_sufficiency": _clean_text(retrieval.get("retrieval_sufficiency")),
        },
        created_at=_utc_now(),
        updated_at=_utc_now(),
    ).dict()
