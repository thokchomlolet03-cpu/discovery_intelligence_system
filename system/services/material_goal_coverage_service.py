from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.scientific_state.contracts import (
    MaterialGoalCoverageRecord,
    MaterialGoalRequirementCoverageRecord,
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


def _coverage_from_trace_item(trace_item: dict[str, Any]) -> dict[str, Any]:
    status = _clean_text(trace_item.get("support_status"), default="unknown")
    rationale_basis = _clean_text(trace_item.get("support_basis_classification"))
    rationale_summary = _clean_text(trace_item.get("rationale_summary"))
    if status == "partially_supported" and _clean_text(trace_item.get("support_basis_classification")) == "partial_or_indirect_dimension_support":
        if _as_list(trace_item.get("observed_support_lines")) and _as_list(trace_item.get("uncovered_requirement_terms")):
            rationale_basis = "observed_but_incomplete_dimension_support"
            rationale_summary = "Observed support exists, but some stated requirement terms remain uncovered."
        elif _as_list(trace_item.get("indirect_support_lines")) and not _as_list(trace_item.get("observed_support_lines")):
            rationale_basis = "indirect_only_dimension_support"
            rationale_summary = "Only indirect support exists for this requirement dimension."

    return MaterialGoalRequirementCoverageRecord(
        requirement_key=_clean_text(trace_item.get("requirement_key")),
        requirement_label=_clean_text(trace_item.get("requirement_label")),
        requirement_terms=[str(item).strip() for item in _as_list(trace_item.get("requirement_terms")) if str(item).strip()],
        status=status,
        rationale_basis=rationale_basis,
        rationale_summary=rationale_summary,
        matched_terms=sorted(
            dict.fromkeys(
                str(term).strip()
                for line in _as_list(trace_item.get("matched_support_lines"))
                if isinstance(line, dict)
                for term in _as_list(line.get("matched_terms"))
                if str(term).strip()
            )
        ),
        supporting_evidence_lines=[item for item in _as_list(trace_item.get("matched_support_lines")) if isinstance(item, dict)][:4],
        contradiction_indicators=[item for item in _as_list(trace_item.get("contradiction_indicators")) if isinstance(item, dict)][:4],
        gap_codes=[str(item).strip() for item in _as_list(trace_item.get("gap_codes")) if str(item).strip()],
        support_trace=trace_item,
        provenance=_as_dict(trace_item.get("provenance")),
    ).dict()


def build_material_goal_coverage(
    *,
    session_id: str,
    workspace_id: str,
    goal_specification: dict[str, Any] | None,
    retrieval_result: dict[str, Any] | None,
    support_trace_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    goal_spec = goal_specification if isinstance(goal_specification, dict) else {}
    retrieval = retrieval_result if isinstance(retrieval_result, dict) else {}
    trace = support_trace_result if isinstance(support_trace_result, dict) else {}
    trace_items = [item for item in _as_list(trace.get("requirement_traces")) if isinstance(item, dict)]
    coverages = [_coverage_from_trace_item(item) for item in trace_items]

    critical_unknowns = sorted(
        dict.fromkeys(
            gap
            for item in coverages
            if bool(_as_dict(item.get("provenance")).get("critical_dimension"))
            and _clean_text(item.get("status")) in {"unknown", "contradicted", "partially_supported"}
            for gap in _as_list(item.get("gap_codes"))
        )
    )
    blocking_gaps = sorted(
        dict.fromkeys(
            gap
            for item in coverages
            if _clean_text(item.get("status")) in {"unknown", "contradicted"}
            for gap in _as_list(item.get("gap_codes"))
        )
    )

    return MaterialGoalCoverageRecord(
        goal_id=_clean_text(goal_spec.get("goal_id")),
        session_id=session_id,
        workspace_id=workspace_id,
        retrieval_status=_clean_text(retrieval.get("retrieval_status"), default="not_attempted"),
        top_direction_id=_clean_text(trace.get("top_direction_id")),
        top_direction_label=_clean_text(trace.get("top_direction_label")),
        top_direction_support_strength=_clean_text(trace.get("top_direction_support_strength"), default="thin"),
        requirement_coverages=[MaterialGoalRequirementCoverageRecord(**item) for item in coverages],
        supported_requirement_count=sum(1 for item in coverages if _clean_text(item.get("status")) == "supported"),
        partially_supported_requirement_count=sum(1 for item in coverages if _clean_text(item.get("status")) == "partially_supported"),
        unknown_requirement_count=sum(1 for item in coverages if _clean_text(item.get("status")) == "unknown"),
        contradicted_requirement_count=sum(1 for item in coverages if _clean_text(item.get("status")) == "contradicted"),
        critical_unknowns=critical_unknowns,
        blocking_gaps=blocking_gaps,
        coverage_provenance={
            "coverage_mode": "bounded_first_battlefield_requirement_coverage",
            "primary_substrate": "material_goal_support_trace",
            "recomputed": True,
            "goal_requirement_status": _clean_text(goal_spec.get("requirement_status")),
            "retrieval_sufficiency": _clean_text(retrieval.get("retrieval_sufficiency")),
        },
        created_at=_utc_now(),
        updated_at=_utc_now(),
    ).dict()
