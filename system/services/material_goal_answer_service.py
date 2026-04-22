from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.scientific_state.contracts import (
    MaterialGoalAnswerDecisionRecord,
    MaterialGoalAnswerRequestRecord,
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


def _is_active_contradiction(item: dict[str, Any]) -> bool:
    return _clean_text(item.get("status")).lower() in {"active", "unresolved"}


def _support_lines(direction: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _as_list(direction.get("supporting_evidence_lines")) if isinstance(item, dict)]


def _request(summary: str, *, kind: str, linked_unknowns: list[str], priority: str = "medium") -> dict[str, Any]:
    return MaterialGoalAnswerRequestRecord(
        request_kind=kind,
        priority=priority,
        summary=summary,
        linked_unknowns=linked_unknowns,
        provenance={"request_mode": "bounded_first_battlefield_answer_gap_closure"},
    ).dict()


def _coverage_items(coverage_result: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _as_list(coverage_result.get("requirement_coverages")) if isinstance(item, dict)]


def _trace_items(support_trace_result: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _as_list(support_trace_result.get("requirement_traces")) if isinstance(item, dict)]


def _collect_unknowns_from_trace(coverage_result: dict[str, Any], support_trace_result: dict[str, Any]) -> tuple[list[str], list[str]]:
    unknowns = list(_as_list(coverage_result.get("critical_unknowns")))
    reasons: list[str] = []
    for item in _trace_items(support_trace_result):
        status = _clean_text(item.get("support_status"))
        if status not in {"unknown", "partially_supported", "contradicted"}:
            continue
        rationale = _clean_text(item.get("rationale_summary"))
        if rationale:
            reasons.append(f"{_clean_text(item.get('requirement_label'))}: {rationale}")
        for gap in _as_list(item.get("gap_codes")):
            text = str(gap).strip()
            if text:
                unknowns.append(text)
    return sorted(dict.fromkeys(unknowns)), reasons[:6]


def _build_requests(unknowns: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    additional_data: list[dict[str, Any]] = []
    experiments: list[dict[str, Any]] = []

    if "missing_grounded_material_direction" in unknowns:
        additional_data.append(
            _request(
                "Add grounded material records that map directly to the stated target material function.",
                kind="grounded_material_direction_data",
                linked_unknowns=["missing_grounded_material_direction"],
                priority="high",
            )
        )
    if "insufficient_property_support" in unknowns or "partial_requirement_coverage" in unknowns:
        additional_data.append(
            _request(
                "Add comparative property measurements covering the stated performance requirements for the leading direction.",
                kind="property_support_data",
                linked_unknowns=["insufficient_property_support", "partial_requirement_coverage"],
                priority="high",
            )
        )
    if "weak_environmental_match" in unknowns:
        experiments.append(
            _request(
                "Run environment-matched testing for the leading direction under the stated operating conditions.",
                kind="environment_match_experiment",
                linked_unknowns=["weak_environmental_match"],
                priority="high",
            )
        )
    if "weak_lifecycle_match" in unknowns:
        experiments.append(
            _request(
                "Run lifecycle or degradation/stability testing across the stated lifetime window.",
                kind="lifecycle_match_experiment",
                linked_unknowns=["weak_lifecycle_match"],
                priority="high",
            )
        )
    if "weak_trigger_match" in unknowns:
        experiments.append(
            _request(
                "Run trigger-response testing aligned to the stated activation or transition condition.",
                kind="trigger_response_experiment",
                linked_unknowns=["weak_trigger_match"],
                priority="medium",
            )
        )
    if "safety_or_regulatory_gap" in unknowns:
        additional_data.append(
            _request(
                "Add safety, toxicity, food-contact, medical, or regulatory evidence tied to the stated use case.",
                kind="safety_regulatory_data",
                linked_unknowns=["safety_or_regulatory_gap"],
                priority="high",
            )
        )
    if "unresolved_contradiction_pressure" in unknowns:
        experiments.append(
            _request(
                "Run one contradiction-resolving comparative experiment targeted at the leading direction and conflicting evidence.",
                kind="contradiction_resolving_experiment",
                linked_unknowns=["unresolved_contradiction_pressure"],
                priority="high",
            )
        )
    if "sparse_evidence_basis" in unknowns and not additional_data:
        additional_data.append(
            _request(
                "Add additional grounded evidence lines before promoting any candidate direction into a supported answer.",
                kind="sparse_evidence_basis_data",
                linked_unknowns=["sparse_evidence_basis"],
                priority="medium",
            )
        )

    return additional_data[:4], experiments[:4]


def _coverage_summary(coverage_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "top_direction_label": _clean_text(coverage_result.get("top_direction_label")),
        "top_direction_support_strength": _clean_text(coverage_result.get("top_direction_support_strength")),
        "supported_requirement_count": int(coverage_result.get("supported_requirement_count") or 0),
        "partially_supported_requirement_count": int(coverage_result.get("partially_supported_requirement_count") or 0),
        "unknown_requirement_count": int(coverage_result.get("unknown_requirement_count") or 0),
        "contradicted_requirement_count": int(coverage_result.get("contradicted_requirement_count") or 0),
        "critical_unknowns": _as_list(coverage_result.get("critical_unknowns")),
        "blocking_gaps": _as_list(coverage_result.get("blocking_gaps")),
    }


def build_material_goal_answer_decision(
    *,
    session_id: str,
    workspace_id: str,
    goal_specification: dict[str, Any] | None,
    retrieval_result: dict[str, Any] | None,
    coverage_result: dict[str, Any] | None = None,
    support_trace_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    goal_spec = goal_specification if isinstance(goal_specification, dict) else {}
    retrieval = retrieval_result if isinstance(retrieval_result, dict) else {}
    coverage = coverage_result if isinstance(coverage_result, dict) else {}
    support_trace = support_trace_result if isinstance(support_trace_result, dict) else {}
    directions = [item for item in _as_list(retrieval.get("candidate_material_directions")) if isinstance(item, dict)]
    top_direction = directions[0] if directions else {}
    top_lines = _support_lines(top_direction)
    observed_count = sum(1 for item in top_lines if _clean_text(item.get("evidence_kind")) == "observed")
    active_contradiction_count = sum(
        1 for item in _as_list(top_direction.get("contradiction_indicators")) if isinstance(item, dict) and _is_active_contradiction(item)
    )

    requirement_items = _coverage_items(coverage)
    critical_items = [item for item in requirement_items if bool(_as_dict(item.get("provenance")).get("critical_dimension")) and _clean_text(item.get("status")) != "not_applicable"]
    supported_critical = [item for item in critical_items if _clean_text(item.get("status")) == "supported"]
    blocked_critical = [item for item in critical_items if _clean_text(item.get("status")) in {"unknown", "contradicted"}]
    partial_critical = [item for item in critical_items if _clean_text(item.get("status")) == "partially_supported"]

    can_answer = (
        _clean_text(goal_spec.get("requirement_status")) == "sufficiently_specified"
        and _clean_text(retrieval.get("retrieval_sufficiency")) == "candidate_directions_available"
        and _clean_text(top_direction.get("support_strength")) == "grounded"
        and len(critical_items) > 0
        and len(blocked_critical) == 0
        and len(partial_critical) == 0
        and len(supported_critical) == len(critical_items)
        and observed_count >= 1
        and len(top_lines) >= 2
        and active_contradiction_count == 0
    )

    if can_answer:
        direction_label = _clean_text(top_direction.get("direction_label"), default="leading candidate direction")
        rationale = [
            f"The leading direction is {direction_label}.",
            f"Critical requirement coverage is currently complete across {len(supported_critical)} dimension(s).",
            f"{observed_count} observed support line(s) and {len(top_lines)} total matched support line(s) back this direction.",
        ]
        return MaterialGoalAnswerDecisionRecord(
            goal_id=_clean_text(goal_spec.get("goal_id")),
            session_id=session_id,
            workspace_id=workspace_id,
            answer_status="best_supported_answer_available",
            answer_sufficiency="answer_supported",
            coverage_summary=_coverage_summary(coverage),
            best_supported_material_answer=f"Current best-supported material direction: {direction_label}.",
            best_supported_direction=top_direction,
            supporting_rationale=rationale[:5],
            answer_limitations=[_clean_text(item) for item in _as_list(top_direction.get("limitation_lines")) if _clean_text(item)][:4],
            explicit_unknowns=[],
            insufficiency_reasons=[],
            required_additional_data=[],
            required_experiments=[],
            decision_provenance={
                "decision_mode": "bounded_first_battlefield_answer_decision",
                "primary_gate": "requirement_coverage",
                "recomputed": True,
                "goal_requirement_status": _clean_text(goal_spec.get("requirement_status")),
                "retrieval_sufficiency": _clean_text(retrieval.get("retrieval_sufficiency")),
                "selected_direction_id": _clean_text(top_direction.get("direction_id")),
                "selected_direction_support_strength": _clean_text(top_direction.get("support_strength")),
                "supported_critical_requirement_count": len(supported_critical),
                "blocked_critical_requirement_count": len(blocked_critical),
                "partial_critical_requirement_count": len(partial_critical),
                "observed_support_line_count": observed_count,
                "active_contradiction_count": active_contradiction_count,
            },
            created_at=_utc_now(),
            updated_at=_utc_now(),
        ).dict()

    unknowns, reasons = _collect_unknowns_from_trace(coverage, support_trace)
    if _clean_text(goal_spec.get("requirement_status")) != "sufficiently_specified":
        unknowns.append("goal_requirements_incomplete")
        reasons.insert(0, "Critical material constraints are still missing, so answer evaluation cannot proceed honestly.")
    additional_data, experiments = _build_requests(sorted(dict.fromkeys(unknowns)))

    return MaterialGoalAnswerDecisionRecord(
        goal_id=_clean_text(goal_spec.get("goal_id")),
        session_id=session_id,
        workspace_id=workspace_id,
        answer_status="insufficient_evidence_requires_followup",
        answer_sufficiency="insufficient_evidence",
        coverage_summary=_coverage_summary(coverage),
        best_supported_material_answer="",
        best_supported_direction=top_direction if isinstance(top_direction, dict) else {},
        supporting_rationale=[],
        answer_limitations=[_clean_text(item) for item in _as_list(retrieval.get("limitation_lines")) if _clean_text(item)][:5],
        explicit_unknowns=sorted(dict.fromkeys(unknowns)),
        insufficiency_reasons=reasons[:6],
        required_additional_data=additional_data,
        required_experiments=experiments,
        decision_provenance={
            "decision_mode": "bounded_first_battlefield_answer_decision",
            "primary_gate": "requirement_coverage",
            "recomputed": True,
            "goal_requirement_status": _clean_text(goal_spec.get("requirement_status")),
            "retrieval_sufficiency": _clean_text(retrieval.get("retrieval_sufficiency")),
            "selected_direction_id": _clean_text(top_direction.get("direction_id")),
            "selected_direction_support_strength": _clean_text(top_direction.get("support_strength")),
            "supported_critical_requirement_count": len(supported_critical),
            "blocked_critical_requirement_count": len(blocked_critical),
            "partial_critical_requirement_count": len(partial_critical),
            "observed_support_line_count": observed_count,
            "active_contradiction_count": active_contradiction_count,
        },
        created_at=_utc_now(),
        updated_at=_utc_now(),
    ).dict()
