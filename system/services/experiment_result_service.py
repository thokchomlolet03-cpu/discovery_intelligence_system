from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.contracts import (
    ExperimentResultQuality,
    ExperimentResultSource,
    validate_experiment_result_record,
    validate_experiment_result_reference,
    validate_experiment_result_summary,
    validate_scientific_session_truth,
)
from system.db.repositories import ClaimRepository, ExperimentRequestRepository, ExperimentResultRepository
from system.services.support_quality_service import (
    assess_governed_evidence_posture,
    assess_provenance_confidence,
    classify_evidence_source_class,
    classify_result_context_limitation,
    classify_result_support_quality,
    rollup_quality_labels,
)


experiment_result_repository = ExperimentResultRepository()
experiment_request_repository = ExperimentRequestRepository()
claim_repository = ClaimRepository()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_float(value: Any) -> float | None:
    if value in (None, "", "nan"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _candidate_label(reference: dict[str, Any], candidate_id: str) -> str:
    return _clean_text(reference.get("candidate_label"), default=candidate_id or "candidate")


def _result_quality(value: Any) -> str:
    token = _clean_text(value, default=ExperimentResultQuality.provisional.value).lower()
    if token in {item.value for item in ExperimentResultQuality}:
        return token
    return ExperimentResultQuality.provisional.value


def _result_source(value: Any) -> str:
    token = _clean_text(value, default=ExperimentResultSource.manual_entry.value).lower()
    if token in {item.value for item in ExperimentResultSource}:
        return token
    return ExperimentResultSource.manual_entry.value


def _normalized_unit(value: Any) -> str:
    return _clean_text(value).lower().replace("μ", "u").replace("µ", "u").replace(" ", "")


def _numeric_interpretation_context(result: dict[str, Any]) -> dict[str, Any]:
    result = result if isinstance(result, dict) else {}
    target_definition = (
        result.get("target_definition_snapshot") if isinstance(result.get("target_definition_snapshot"), dict) else {}
    )
    observed_value = _safe_float(result.get("observed_value"))
    if observed_value is None:
        return {
            "bounded_numeric_interpretation": False,
            "unresolved_numeric_interpretation": False,
            "reason": "",
        }

    target_kind = _clean_text(target_definition.get("target_kind")).lower()
    rule = target_definition.get("derived_label_rule") if isinstance(target_definition.get("derived_label_rule"), dict) else {}
    operator = _clean_text(rule.get("operator"))
    threshold = _safe_float(rule.get("threshold"))
    if target_kind != "regression" or not operator or threshold is None:
        return {
            "bounded_numeric_interpretation": False,
            "unresolved_numeric_interpretation": True,
            "reason": "the current target definition does not provide a clean numeric interpretation rule",
        }

    target_unit = _normalized_unit(target_definition.get("measurement_unit"))
    observed_unit = _normalized_unit(result.get("measurement_unit"))
    if target_unit and observed_unit and target_unit != observed_unit and target_unit not in observed_unit and observed_unit not in target_unit:
        return {
            "bounded_numeric_interpretation": False,
            "unresolved_numeric_interpretation": True,
            "reason": "the recorded unit does not align cleanly with the current target definition",
        }
    if target_unit and not observed_unit:
        return {
            "bounded_numeric_interpretation": False,
            "unresolved_numeric_interpretation": True,
            "reason": "the recorded numeric value does not include a matching measurement unit",
        }
    return {
        "bounded_numeric_interpretation": True,
        "unresolved_numeric_interpretation": False,
        "reason": f"the current target definition provides a bounded numeric rule ({operator} {threshold:g})",
    }


def _result_interpretation_fields(result: dict[str, Any]) -> dict[str, str | bool]:
    result = result if isinstance(result, dict) else {}
    quality = _result_quality(result.get("result_quality"))
    assay_context = _clean_text(result.get("assay_context"))
    observed_label = _clean_text(result.get("observed_label"))
    numeric_context = _numeric_interpretation_context(result)
    context_limitation = classify_result_context_limitation(
        result,
        bounded_numeric_interpretation=bool(numeric_context["bounded_numeric_interpretation"]),
    )

    quality_caution = quality in {
        ExperimentResultQuality.provisional.value,
        ExperimentResultQuality.screening.value,
    }
    if numeric_context["bounded_numeric_interpretation"]:
        label = "Bounded numeric interpretation available"
        summary = "A numeric result is recorded and can be interpreted under the current target rule."
    elif numeric_context["unresolved_numeric_interpretation"]:
        label = "Numeric result recorded, unresolved under current basis"
        summary = (
            "A numeric result is recorded, but bounded interpretation remains unresolved because "
            f"{numeric_context['reason']}."
        )
    elif observed_label:
        label = "Observed label can inform support revision"
        summary = "A direct observed label is recorded for this result and can contribute to bounded support revision."
    else:
        label = "Observed result recorded"
        summary = "An observed result is recorded for this session."

    if quality_caution:
        summary += f" Result quality is {quality.replace('_', ' ')}, so interpretation should remain cautious."
    elif quality == ExperimentResultQuality.confirmatory.value:
        summary += " Result quality is confirmatory, which makes the observed outcome more useful for bounded follow-up interpretation."
    if assay_context:
        summary += " Assay context is recorded for review against the current target context."

    support_quality = classify_result_support_quality(
        result_quality=quality,
        has_observed_label=bool(observed_label),
        bounded_numeric_interpretation=bool(numeric_context["bounded_numeric_interpretation"]),
        unresolved_numeric_interpretation=bool(numeric_context["unresolved_numeric_interpretation"]),
        context_limitation_label=context_limitation["result_context_limitation_label"],
        context_limitation_summary=context_limitation["result_context_limitation_summary"],
    )

    return {
        "result_interpretation_label": label,
        "result_interpretation_summary": summary,
        "result_support_quality_label": support_quality["result_support_quality_label"],
        "result_support_quality_summary": support_quality["result_support_quality_summary"],
        "result_decision_usefulness_label": support_quality["result_decision_usefulness_label"],
        "result_context_limitation_label": context_limitation["result_context_limitation_label"],
        "bounded_numeric_interpretation": bool(numeric_context["bounded_numeric_interpretation"]),
        "unresolved_numeric_interpretation": bool(numeric_context["unresolved_numeric_interpretation"]),
        "quality_caution": quality_caution,
        "assay_context_recorded": bool(assay_context),
    }


def _load_link_context(
    *,
    workspace_id: str,
    source_experiment_request_id: str = "",
    source_claim_id: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    request_payload: dict[str, Any] = {}
    claim_payload: dict[str, Any] = {}
    if source_experiment_request_id:
        request_payload = experiment_request_repository.get_experiment_request(
            source_experiment_request_id,
            workspace_id=workspace_id,
        )
        claim_id = _clean_text(request_payload.get("claim_id"))
        if claim_id:
            claim_payload = claim_repository.get_claim(claim_id, workspace_id=workspace_id)
    elif source_claim_id:
        claim_payload = claim_repository.get_claim(source_claim_id, workspace_id=workspace_id)
    return request_payload, claim_payload


def build_experiment_result_record(
    *,
    session_id: str,
    workspace_id: str,
    source_experiment_request_id: str = "",
    source_claim_id: str = "",
    candidate_id: str = "",
    candidate_reference: dict[str, Any] | None = None,
    target_definition_snapshot: dict[str, Any] | None = None,
    observed_value: Any = None,
    observed_label: str = "",
    measurement_unit: str = "",
    assay_context: str = "",
    result_quality: str = ExperimentResultQuality.provisional.value,
    result_source: str = ExperimentResultSource.manual_entry.value,
    ingested_by: str = "",
    ingested_by_user_id: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    request_payload, claim_payload = _load_link_context(
        workspace_id=workspace_id,
        source_experiment_request_id=_clean_text(source_experiment_request_id),
        source_claim_id=_clean_text(source_claim_id),
    )
    request_reference = (
        request_payload.get("candidate_reference")
        if isinstance(request_payload.get("candidate_reference"), dict)
        else {}
    )
    claim_reference = (
        claim_payload.get("candidate_reference")
        if isinstance(claim_payload.get("candidate_reference"), dict)
        else {}
    )
    explicit_reference = candidate_reference if isinstance(candidate_reference, dict) else {}
    effective_candidate_id = _clean_text(
        candidate_id
        or request_payload.get("candidate_id")
        or claim_payload.get("candidate_id")
        or explicit_reference.get("candidate_id")
        or request_reference.get("candidate_id")
        or claim_reference.get("candidate_id")
    )
    effective_reference = {
        **claim_reference,
        **request_reference,
        **explicit_reference,
        "candidate_id": effective_candidate_id,
        "candidate_label": _candidate_label({**claim_reference, **request_reference, **explicit_reference}, effective_candidate_id),
    }
    effective_target_definition = (
        target_definition_snapshot
        if isinstance(target_definition_snapshot, dict)
        else request_payload.get("target_definition_snapshot")
        if isinstance(request_payload.get("target_definition_snapshot"), dict)
        else claim_payload.get("target_definition_snapshot")
        if isinstance(claim_payload.get("target_definition_snapshot"), dict)
        else {}
    )
    effective_measurement_unit = _clean_text(
        measurement_unit
        or (
            (effective_target_definition.get("measurement_unit") if isinstance(effective_target_definition, dict) else "")
            or ""
        )
    )
    effective_observed_value = _safe_float(observed_value)
    effective_observed_label = _clean_text(observed_label)
    if not effective_candidate_id:
        raise ValueError("ExperimentResult requires a candidate reference or a linked experiment request/claim.")
    if effective_observed_value is None and not effective_observed_label:
        raise ValueError("ExperimentResult requires an observed value or observed label.")
    source_class = classify_evidence_source_class(
        evidence_type="experimental_value",
        source="uploaded_dataset" if _result_source(result_source) == ExperimentResultSource.uploaded_result.value else _result_source(result_source),
        truth_status="observed",
        result_source=_result_source(result_source),
        linked_claim_id=_clean_text(source_claim_id or claim_payload.get("claim_id") or request_payload.get("claim_id")),
        linked_request_id=_clean_text(source_experiment_request_id or request_payload.get("experiment_request_id")),
        created_by=ingested_by,
    )
    provenance = assess_provenance_confidence(
        source_class_label=source_class["source_class_label"],
        source=_result_source(result_source),
        truth_status="observed",
        ingested_by=ingested_by,
        linked_claim_id=_clean_text(source_claim_id or claim_payload.get("claim_id") or request_payload.get("claim_id")),
        linked_request_id=_clean_text(source_experiment_request_id or request_payload.get("experiment_request_id")),
    )
    trust_posture = assess_governed_evidence_posture(
        source_class_label=source_class["source_class_label"],
        provenance_confidence_label=provenance["provenance_confidence_label"],
        candidate_context=bool(
            _clean_text(source_claim_id or claim_payload.get("claim_id") or request_payload.get("claim_id"))
            or _clean_text(source_experiment_request_id or request_payload.get("experiment_request_id"))
        ),
        local_only_default=True,
    )
    return validate_experiment_result_record(
        {
            "experiment_result_id": "",
            "workspace_id": workspace_id,
            "session_id": session_id,
            "source_experiment_request_id": _clean_text(source_experiment_request_id or request_payload.get("experiment_request_id")),
            "source_claim_id": _clean_text(source_claim_id or claim_payload.get("claim_id") or request_payload.get("claim_id")),
            "candidate_id": effective_candidate_id,
            "candidate_reference": effective_reference,
            "target_definition_snapshot": effective_target_definition,
            "observed_value": effective_observed_value,
            "observed_label": effective_observed_label,
            "measurement_unit": effective_measurement_unit,
            "assay_context": _clean_text(assay_context),
            "result_quality": _result_quality(result_quality),
            "result_source": _result_source(result_source),
            "ingested_at": _utc_now(),
            "ingested_by": _clean_text(ingested_by),
            "ingested_by_user_id": _clean_text(ingested_by_user_id),
            "notes": _clean_text(notes),
            "metadata": {
                "linked_claim_id": _clean_text(source_claim_id or claim_payload.get("claim_id") or request_payload.get("claim_id")),
                "linked_experiment_request_id": _clean_text(source_experiment_request_id or request_payload.get("experiment_request_id")),
                "target_name": _clean_text((effective_target_definition or {}).get("target_name")),
                "source_class_label": source_class["source_class_label"],
                "source_class_summary": source_class["source_class_summary"],
                "provenance_confidence_label": provenance["provenance_confidence_label"],
                "provenance_confidence_summary": provenance["provenance_confidence_summary"],
                "trust_tier_label": trust_posture["trust_tier_label"],
                "trust_tier_summary": trust_posture["trust_tier_summary"],
                "governed_review_status_label": trust_posture["governed_review_status_label"],
                "governed_review_status_summary": trust_posture["governed_review_status_summary"],
                "governed_review_reason_label": trust_posture["governed_review_reason_label"],
                "governed_review_reason_summary": trust_posture["governed_review_reason_summary"],
            },
        }
    )


def ingest_experiment_result(
    *,
    session_id: str,
    workspace_id: str,
    source_experiment_request_id: str = "",
    source_claim_id: str = "",
    candidate_id: str = "",
    candidate_reference: dict[str, Any] | None = None,
    target_definition_snapshot: dict[str, Any] | None = None,
    observed_value: Any = None,
    observed_label: str = "",
    measurement_unit: str = "",
    assay_context: str = "",
    result_quality: str = ExperimentResultQuality.provisional.value,
    result_source: str = ExperimentResultSource.manual_entry.value,
    ingested_by: str = "",
    ingested_by_user_id: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    payload = build_experiment_result_record(
        session_id=session_id,
        workspace_id=workspace_id,
        source_experiment_request_id=source_experiment_request_id,
        source_claim_id=source_claim_id,
        candidate_id=candidate_id,
        candidate_reference=candidate_reference,
        target_definition_snapshot=target_definition_snapshot,
        observed_value=observed_value,
        observed_label=observed_label,
        measurement_unit=measurement_unit,
        assay_context=assay_context,
        result_quality=result_quality,
        result_source=result_source,
        ingested_by=ingested_by,
        ingested_by_user_id=ingested_by_user_id,
        notes=notes,
    )
    return experiment_result_repository.create_experiment_result(payload)


def list_session_experiment_results(
    session_id: str,
    *,
    workspace_id: str | None = None,
    source_experiment_request_id: str | None = None,
    source_claim_id: str | None = None,
) -> list[dict[str, Any]]:
    return experiment_result_repository.list_experiment_results(
        session_id=session_id,
        workspace_id=workspace_id,
        source_experiment_request_id=source_experiment_request_id,
        source_claim_id=source_claim_id,
    )


def experiment_result_refs_from_records(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        candidate_reference = result.get("candidate_reference") if isinstance(result.get("candidate_reference"), dict) else {}
        interpretation = _result_interpretation_fields(result)
        refs.append(
            validate_experiment_result_reference(
                {
                    "experiment_result_id": result.get("experiment_result_id"),
                    "source_experiment_request_id": result.get("source_experiment_request_id"),
                    "source_claim_id": result.get("source_claim_id"),
                    "candidate_id": result.get("candidate_id"),
                    "candidate_label": candidate_reference.get("candidate_label") or result.get("candidate_id"),
                    "observed_value": result.get("observed_value"),
                    "observed_label": result.get("observed_label"),
                    "measurement_unit": result.get("measurement_unit"),
                    "result_quality": result.get("result_quality"),
                    "result_source": result.get("result_source"),
                    "result_interpretation_label": interpretation["result_interpretation_label"],
                    "result_interpretation_summary": interpretation["result_interpretation_summary"],
                    "result_support_quality_label": interpretation["result_support_quality_label"],
                    "result_support_quality_summary": interpretation["result_support_quality_summary"],
                    "result_decision_usefulness_label": interpretation["result_decision_usefulness_label"],
                    "result_context_limitation_label": interpretation["result_context_limitation_label"],
                    "ingested_at": result.get("ingested_at"),
                }
            )
        )
    return refs


def experiment_result_summary_from_records(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    with_numeric_value = sum(1 for result in results if result.get("observed_value") is not None)
    with_label = sum(1 for result in results if _clean_text(result.get("observed_label")))
    interpreted = [_result_interpretation_fields(result) for result in results if isinstance(result, dict)]
    bounded_numeric = sum(1 for item in interpreted if item["bounded_numeric_interpretation"])
    unresolved_numeric = sum(1 for item in interpreted if item["unresolved_numeric_interpretation"])
    cautious_quality = sum(1 for item in interpreted if item["quality_caution"])
    assay_context_recorded = sum(1 for item in interpreted if item["assay_context_recorded"])
    support_quality_counts = rollup_quality_labels(
        [item.get("result_support_quality_label") for item in interpreted]
    )
    if total:
        parts = [
            f"{total} observed result{'' if total == 1 else 's'} {'has' if total == 1 else 'have'} been recorded for this session.",
            "Observed results are stored outcome records, not belief updates or causal proof.",
        ]
        if bounded_numeric or unresolved_numeric:
            parts.append(
                f"Numeric interpretation remains bounded: {bounded_numeric} result{'s are' if bounded_numeric != 1 else ' is'} interpretable under the current target rule and {unresolved_numeric} remain unresolved under the current numeric basis."
            )
        if cautious_quality:
            parts.append(
                f"{cautious_quality} result{'s carry' if cautious_quality != 1 else ' carries'} provisional or screening-quality caution."
            )
        if assay_context_recorded:
            parts.append(
                f"{assay_context_recorded} result{'s include' if assay_context_recorded != 1 else ' includes'} recorded assay context."
            )
        if any(support_quality_counts.values()):
            parts.append(
                "Current result usefulness remains bounded: "
                f"{support_quality_counts['decision_useful_count']} more decision-useful, "
                f"{support_quality_counts['limited_count']} limited, "
                f"{support_quality_counts['context_limited_count']} context-limited, and "
                f"{support_quality_counts['weak_count']} unresolved under the current basis."
            )
        summary_text = " ".join(parts)
    else:
        summary_text = "No observed results have been recorded for this session."
    return validate_experiment_result_summary(
        {
            "result_count": total,
            "recorded_count": total,
            "with_numeric_value_count": with_numeric_value,
            "with_label_count": with_label,
            "bounded_numeric_interpretation_count": bounded_numeric,
            "unresolved_numeric_interpretation_count": unresolved_numeric,
            "cautious_result_quality_count": cautious_quality,
            "assay_context_recorded_count": assay_context_recorded,
            "decision_useful_result_count": support_quality_counts["decision_useful_count"],
            "limited_result_support_count": support_quality_counts["limited_count"],
            "context_limited_result_count": support_quality_counts["context_limited_count"],
            "unresolved_result_support_count": support_quality_counts["weak_count"],
            "summary_text": summary_text,
            "top_results": experiment_result_refs_from_records(results[:3]),
        }
    )


def attach_experiment_results_to_scientific_session_truth(
    scientific_truth: dict[str, Any],
    experiment_results: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(scientific_truth, dict):
        return scientific_truth
    updated = dict(scientific_truth)
    updated["experiment_result_refs"] = experiment_result_refs_from_records(experiment_results)
    updated["linked_result_summary"] = experiment_result_summary_from_records(experiment_results)
    return validate_scientific_session_truth(updated)


__all__ = [
    "attach_experiment_results_to_scientific_session_truth",
    "build_experiment_result_record",
    "experiment_result_refs_from_records",
    "experiment_result_summary_from_records",
    "ingest_experiment_result",
    "list_session_experiment_results",
]
