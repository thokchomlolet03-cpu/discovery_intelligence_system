from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.scientific_state.contracts import (
    MaterialGoalCandidateDirectionRecord,
    MaterialGoalEvidenceLineRecord,
    MaterialGoalEvidenceResultRecord,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values() if item not in (None, ""))
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value if item not in (None, ""))
    return _clean_text(value)


def _query_summary(goal_spec: dict[str, Any]) -> dict[str, Any]:
    structured = goal_spec.get("structured_requirements") if isinstance(goal_spec.get("structured_requirements"), dict) else {}
    normalized_terms: list[str] = []
    grouped_terms: dict[str, list[str]] = {}
    for key in (
        "target_material_function",
        "desired_properties",
        "operating_environment",
        "lifecycle_window",
        "trigger_conditions",
        "safety_or_regulatory_constraints",
    ):
        values = [str(item).strip().lower() for item in (structured.get(key) or []) if str(item).strip()]
        grouped_terms[key] = values
        normalized_terms.extend(values)
    deduped_terms = sorted(dict.fromkeys(normalized_terms))
    return {
        "domain_scope": _clean_text(goal_spec.get("domain_scope"), default="polymer_material"),
        "normalized_terms": deduped_terms,
        "grouped_terms": grouped_terms,
        "scientific_target_summary": _clean_text(goal_spec.get("scientific_target_summary")),
        "constraint_mode": _clean_text(structured.get("constraint_mode"), default="unspecified"),
    }


def _source_text(item: dict[str, Any]) -> str:
    parts = [
        _flatten_text(item.get("payload")),
        _flatten_text(item.get("provenance")),
        _flatten_text(item.get("rationale")),
        _flatten_text(item.get("recommendation")),
        _flatten_text(item.get("normalized_explanation")),
        _clean_text(item.get("rationale_summary")),
        _clean_text(item.get("bridge_state_summary")),
        _clean_text(item.get("evidence_type")),
        _clean_text(item.get("assay")),
        _clean_text(item.get("target_name")),
        _clean_text(item.get("bucket")),
        _clean_text(item.get("status")),
    ]
    return " ".join(part for part in parts if part).lower()


def _matched_terms(text: str, query_terms: list[str]) -> list[str]:
    return [term for term in query_terms if term and term in text]


def _evidence_kind(source_object_type: str, item: dict[str, Any]) -> str:
    if source_object_type == "evidence":
        evidence_type = _clean_text(item.get("evidence_type"))
        if evidence_type in {"observed_measurement", "observed_label"}:
            return "observed"
        return "context"
    if source_object_type == "model_output":
        return "predicted"
    if source_object_type == "recommendation":
        return "recommended"
    return "context"


def _line_summary(source_object_type: str, item: dict[str, Any], matched_terms: list[str]) -> str:
    candidate_id = _clean_text(item.get("candidate_id"), default="candidate")
    if source_object_type == "evidence":
        evidence_type = _clean_text(item.get("evidence_type"), default="evidence")
        assay = _clean_text(item.get("assay"))
        observed_value = _safe_float(item.get("observed_value"))
        if observed_value is not None:
            value_text = f" observed value {observed_value:g}"
        else:
            value_text = ""
        assay_text = f" in {assay}" if assay else ""
        return f"{candidate_id} has {evidence_type}{assay_text}{value_text}; matched goal terms: {', '.join(matched_terms)}."
    if source_object_type == "model_output":
        predicted = _safe_float(item.get("predicted_value"))
        confidence = _safe_float(item.get("confidence"))
        predicted_text = f" predicted value {predicted:g}" if predicted is not None else ""
        confidence_text = f", confidence {confidence:.2f}" if confidence is not None else ""
        return f"{candidate_id} has model-output context{predicted_text}{confidence_text}; matched goal terms: {', '.join(matched_terms)}."
    if source_object_type == "recommendation":
        rank = _safe_int(item.get("rank"))
        bucket = _clean_text(item.get("bucket"))
        rank_text = f" rank {rank}" if rank is not None else ""
        bucket_text = f" in {bucket}" if bucket else ""
        return f"{candidate_id} is present in recommendation context{rank_text}{bucket_text}; matched goal terms: {', '.join(matched_terms)}."
    return f"{candidate_id} has matched session context for goal terms: {', '.join(matched_terms)}."


def _candidate_direction_label(item: dict[str, Any]) -> str:
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    family = _clean_text(payload.get("material_family") or payload.get("polymer_class") or payload.get("formulation_type"))
    application = _clean_text(payload.get("application") or payload.get("intended_use"))
    candidate_id = _clean_text(item.get("candidate_id"))
    canonical_smiles = _clean_text(item.get("canonical_smiles") or item.get("smiles"))
    if family and application:
        return f"{family} for {application}"
    if family:
        return family
    if application:
        return application
    if candidate_id and canonical_smiles and candidate_id != canonical_smiles:
        return f"Candidate-linked direction {candidate_id}"
    return candidate_id or canonical_smiles or "Candidate-linked direction"


def _direction_type(item: dict[str, Any]) -> str:
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    if _clean_text(payload.get("material_family") or payload.get("polymer_class")):
        return "material_family_direction"
    if _clean_text(payload.get("formulation_type")):
        return "formulation_direction"
    if _clean_text(payload.get("application") or payload.get("intended_use")):
        return "application_direction"
    return "candidate_linked_direction"


def _collect_candidate_contradictions(
    *,
    candidate_id: str,
    canonical_smiles: str,
    claims: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    claim_ids = {
        _clean_text(item.get("claim_id"))
        for item in claims
        if _clean_text(item.get("candidate_id")) == candidate_id
        or (_clean_text(item.get("canonical_smiles")) and _clean_text(item.get("canonical_smiles")) == canonical_smiles)
    }
    return [
        {
            "contradiction_id": _clean_text(item.get("contradiction_id")),
            "status": _clean_text(item.get("status"), default="unresolved"),
            "contradiction_type": _clean_text(item.get("contradiction_type")),
            "summary": _clean_text(item.get("summary")),
        }
        for item in contradictions
        if _clean_text(item.get("claim_id")) in claim_ids
    ]


def _limitation_lines(
    *,
    direction_lines: list[dict[str, Any]],
    grouped_terms: dict[str, list[str]],
    contradictions: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    observed_count = sum(1 for item in direction_lines if item.get("evidence_kind") == "observed")
    predicted_count = sum(1 for item in direction_lines if item.get("evidence_kind") == "predicted")
    recommended_count = sum(1 for item in direction_lines if item.get("evidence_kind") == "recommended")
    matched_terms = {term for item in direction_lines for term in item.get("matched_terms", [])}
    if observed_count == 0 and (predicted_count > 0 or recommended_count > 0):
        lines.append("Current retrieval is driven by model or recommendation context without direct observed evidence aligned to this goal.")
    if len(direction_lines) == 1:
        lines.append("Only a single matched support line is currently available for this direction.")
    if grouped_terms.get("operating_environment") and not any(term in matched_terms for term in grouped_terms.get("operating_environment") or []):
        lines.append("Matched evidence does not yet clearly ground the requested operating environment.")
    if grouped_terms.get("lifecycle_window") and not any(term in matched_terms for term in grouped_terms.get("lifecycle_window") or []):
        lines.append("Matched evidence does not yet clearly ground the requested lifecycle or stability window.")
    if any(_clean_text(item.get("status")) in {"active", "unresolved"} for item in contradictions):
        lines.append("Active or unresolved contradiction pressure is still attached to this direction.")
    return lines


def _support_strength(direction_lines: list[dict[str, Any]], limitation_lines: list[str]) -> str:
    observed_count = sum(1 for item in direction_lines if item.get("evidence_kind") == "observed")
    if observed_count >= 1 and len(direction_lines) >= 2 and len(limitation_lines) <= 1:
        return "grounded"
    if len(direction_lines) >= 2:
        return "partial"
    return "thin"


def build_material_goal_evidence_result(
    *,
    session_id: str,
    workspace_id: str,
    goal_specification: dict[str, Any] | None,
    evidence_records: list[dict[str, Any]] | None = None,
    model_outputs: list[dict[str, Any]] | None = None,
    recommendations: list[dict[str, Any]] | None = None,
    claims: list[dict[str, Any]] | None = None,
    contradictions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    goal_spec = goal_specification if isinstance(goal_specification, dict) else {}
    if not goal_spec:
        return MaterialGoalEvidenceResultRecord(
            session_id=session_id,
            workspace_id=workspace_id,
            retrieval_status="no_goal_specification",
            retrieval_sufficiency="no_grounded_evidence",
            limitation_lines=["No persisted material goal specification is available for retrieval yet."],
            retrieval_provenance={"retrieval_mode": "bounded_first_battlefield_material_goal_retrieval", "recomputed": True},
        ).dict()

    if _clean_text(goal_spec.get("requirement_status")) != "sufficiently_specified":
        return MaterialGoalEvidenceResultRecord(
            goal_id=_clean_text(goal_spec.get("goal_id")),
            session_id=session_id,
            workspace_id=workspace_id,
            retrieval_status="blocked_goal_insufficient",
            retrieval_sufficiency="no_grounded_evidence",
            query_summary=_query_summary(goal_spec),
            limitation_lines=["Retrieval is blocked until critical material requirements are clarified."],
            retrieval_provenance={"retrieval_mode": "bounded_first_battlefield_material_goal_retrieval", "recomputed": True},
        ).dict()

    evidence_records = evidence_records if isinstance(evidence_records, list) else []
    model_outputs = model_outputs if isinstance(model_outputs, list) else []
    recommendations = recommendations if isinstance(recommendations, list) else []
    claims = claims if isinstance(claims, list) else []
    contradictions = contradictions if isinstance(contradictions, list) else []

    query_summary = _query_summary(goal_spec)
    query_terms = query_summary.get("normalized_terms") if isinstance(query_summary.get("normalized_terms"), list) else []
    grouped_terms = query_summary.get("grouped_terms") if isinstance(query_summary.get("grouped_terms"), dict) else {}
    matched_lines: list[dict[str, Any]] = []

    def collect(source_object_type: str, item: dict[str, Any]) -> None:
        text = _source_text(item)
        matched = _matched_terms(text, query_terms)
        if not matched:
            return
        line = MaterialGoalEvidenceLineRecord(
            source_object_type=source_object_type,
            source_object_id=str(
                item.get("record_id")
                or item.get("request_id")
                or item.get("candidate_id")
                or item.get("canonical_smiles")
                or ""
            ).strip(),
            candidate_id=_clean_text(item.get("candidate_id")),
            canonical_smiles=_clean_text(item.get("canonical_smiles") or item.get("smiles")),
            relation_to_goal="matched_structured_requirement_terms",
            evidence_kind=_evidence_kind(source_object_type, item),
            summary=_line_summary(source_object_type, item, matched),
            matched_terms=matched,
            observed_value=_safe_float(item.get("observed_value")),
            observed_label=_safe_int(item.get("observed_label")),
            predicted_value=_safe_float(item.get("predicted_value")),
            confidence=_safe_float(item.get("confidence")),
            uncertainty=_safe_float(item.get("uncertainty")),
            rank=_safe_int(item.get("rank")),
            provenance={"retrieval_match_count": len(matched)},
        ).dict()
        matched_lines.append(line)

    for item in evidence_records:
        if isinstance(item, dict):
            collect("evidence", item)
    for item in model_outputs:
        if isinstance(item, dict):
            collect("model_output", item)
    for item in recommendations:
        if isinstance(item, dict):
            collect("recommendation", item)

    if not matched_lines:
        return MaterialGoalEvidenceResultRecord(
            goal_id=_clean_text(goal_spec.get("goal_id")),
            session_id=session_id,
            workspace_id=workspace_id,
            retrieval_status="retrieval_complete",
            retrieval_sufficiency="no_grounded_evidence",
            query_summary=query_summary,
            limitation_lines=[
                "The current session does not contain grounded evidence lines that match the structured material goal closely enough for retrieval.",
            ],
            retrieval_provenance={"retrieval_mode": "bounded_first_battlefield_material_goal_retrieval", "recomputed": True},
        ).dict()

    grouped: dict[str, list[dict[str, Any]]] = {}
    line_context: dict[str, dict[str, Any]] = {}
    for item in matched_lines:
        candidate_id = _clean_text(item.get("candidate_id"))
        canonical_smiles = _clean_text(item.get("canonical_smiles"))
        key = candidate_id or canonical_smiles or f"ungrouped::{_clean_text(item.get('source_object_type'))}:{_clean_text(item.get('source_object_id'))}"
        grouped.setdefault(key, []).append(item)
        if key not in line_context:
            source_object_type = _clean_text(item.get("source_object_type"))
            source_object_id = _clean_text(item.get("source_object_id"))
            source_rows = {
                "evidence": evidence_records,
                "model_output": model_outputs,
                "recommendation": recommendations,
            }.get(source_object_type, [])
            context_item = next(
                (
                    row for row in source_rows
                    if _clean_text(row.get("record_id") or row.get("candidate_id") or row.get("canonical_smiles")) == source_object_id
                ),
                {},
            )
            line_context[key] = context_item if isinstance(context_item, dict) else {}

    candidate_directions: list[dict[str, Any]] = []
    all_contradictions: list[dict[str, Any]] = []
    all_limitations: list[str] = []
    for key, direction_lines in grouped.items():
        context_item = line_context.get(key, {})
        candidate_id = _clean_text(direction_lines[0].get("candidate_id"))
        canonical_smiles = _clean_text(direction_lines[0].get("canonical_smiles"))
        contradictions_for_direction = _collect_candidate_contradictions(
            candidate_id=candidate_id,
            canonical_smiles=canonical_smiles,
            claims=claims,
            contradictions=contradictions,
        )
        limitation_lines = _limitation_lines(
            direction_lines=direction_lines,
            grouped_terms=grouped_terms,
            contradictions=contradictions_for_direction,
        )
        support_strength = _support_strength(direction_lines, limitation_lines)
        direction = MaterialGoalCandidateDirectionRecord(
            direction_id=f"direction::{key}",
            direction_label=_candidate_direction_label(context_item or {"candidate_id": candidate_id, "canonical_smiles": canonical_smiles}),
            direction_type=_direction_type(context_item or {}),
            candidate_id=candidate_id,
            canonical_smiles=canonical_smiles,
            matched_terms=sorted(dict.fromkeys(term for item in direction_lines for term in item.get("matched_terms", []))),
            support_strength=support_strength,
            supporting_evidence_lines=[MaterialGoalEvidenceLineRecord(**item) for item in direction_lines],
            limitation_lines=limitation_lines,
            contradiction_indicators=contradictions_for_direction,
            retrieval_match_summary=(
                f"{len(direction_lines)} matched line(s) retrieved for this direction; "
                f"support is currently {support_strength}."
            ),
        ).dict()
        candidate_directions.append(direction)
        all_contradictions.extend(contradictions_for_direction)
        all_limitations.extend(limitation_lines)

    candidate_directions.sort(
        key=lambda item: (
            {"grounded": 0, "partial": 1, "thin": 2}.get(_clean_text(item.get("support_strength")), 3),
            -len(item.get("supporting_evidence_lines") or []),
            _clean_text(item.get("direction_label")),
        )
    )
    sufficiency = "weak_partial_evidence"
    if any(_clean_text(item.get("support_strength")) == "grounded" for item in candidate_directions):
        sufficiency = "candidate_directions_available"
    elif not candidate_directions:
        sufficiency = "no_grounded_evidence"

    top_level_limitations = sorted(dict.fromkeys(all_limitations))
    if sufficiency != "candidate_directions_available":
        top_level_limitations.append(
            "Current retrieval does not yet justify a best-supported material answer; it only exposes partial candidate directions."
        )

    return MaterialGoalEvidenceResultRecord(
        goal_id=_clean_text(goal_spec.get("goal_id")),
        session_id=session_id,
        workspace_id=workspace_id,
        retrieval_status="retrieval_complete",
        retrieval_sufficiency=sufficiency,
        query_summary=query_summary,
        candidate_material_directions=[MaterialGoalCandidateDirectionRecord(**item) for item in candidate_directions],
        supporting_evidence_lines=[MaterialGoalEvidenceLineRecord(**item) for item in matched_lines[:12]],
        limitation_lines=top_level_limitations,
        contradiction_indicators=all_contradictions[:12],
        retrieval_provenance={
            "retrieval_mode": "bounded_first_battlefield_material_goal_retrieval",
            "recomputed": True,
            "goal_requirement_status": _clean_text(goal_spec.get("requirement_status")),
            "matched_line_count": len(matched_lines),
            "candidate_direction_count": len(candidate_directions),
        },
        created_at=_utc_now(),
        updated_at=_utc_now(),
    ).dict()
