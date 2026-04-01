from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.contracts import (
    DecisionIntent,
    DomainStatus,
    JobStatus,
    ModelingMode,
    TargetKind,
    validate_session_identity,
)
from system.services.target_definition_service import (
    infer_target_definition,
    normalize_decision_intent,
    normalize_modeling_mode,
)
from system.services.status_semantics_service import build_status_semantics


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return dict(value)
    return {}


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return default


def _to_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _humanize_timestamp(value: Any) -> str:
    parsed = _to_datetime(value)
    if parsed is None:
        return "Not available"
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _humanize_token(value: str, *, default: str = "Not specified") -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return default
    return cleaned.replace("_", " ").strip().title()


def _normalize_target_definition(
    *,
    session_record: dict[str, Any] | None,
    upload_metadata: dict[str, Any] | None,
    analysis_report: dict[str, Any] | None,
    decision_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    session_record = session_record or {}
    upload_metadata = upload_metadata or {}
    analysis_report = analysis_report or {}
    decision_payload = decision_payload or {}
    summary_metadata = session_record.get("summary_metadata") if isinstance(session_record, dict) else {}
    summary_metadata = summary_metadata if isinstance(summary_metadata, dict) else {}
    upload_summary = summary_metadata.get("upload_session_summary") if isinstance(summary_metadata.get("upload_session_summary"), dict) else {}

    existing = _first_dict(
        analysis_report.get("target_definition"),
        decision_payload.get("target_definition"),
        upload_metadata.get("target_definition"),
        upload_summary.get("target_definition"),
    )
    if existing:
        return dict(existing)

    mapping = _first_dict(
        upload_metadata.get("selected_mapping"),
        upload_metadata.get("semantic_roles"),
        upload_metadata.get("inferred_mapping"),
    )
    validation_summary = _first_dict(
        upload_metadata.get("validation_summary"),
        upload_summary.get("validation_summary"),
    )
    label_builder = _first_dict(
        upload_metadata.get("label_builder_config"),
        upload_metadata.get("label_builder_suggestion"),
    )
    return infer_target_definition(
        mapping=mapping,
        validation_summary=validation_summary,
        label_builder=label_builder,
        existing={},
    )


def _resolve_job_status(
    *,
    current_job: dict[str, Any] | None,
    session_record: dict[str, Any] | None,
) -> str:
    if isinstance(current_job, dict):
        current = _clean_text(current_job.get("status")).lower()
        if current:
            return current
    summary_metadata = (session_record or {}).get("summary_metadata")
    if isinstance(summary_metadata, dict):
        stored = _clean_text(summary_metadata.get("last_job_status")).lower()
        if stored:
            return stored
    return ""


def _scientific_purpose(target_definition: dict[str, Any], decision_intent: str) -> str:
    target = _clean_text(target_definition.get("target_name"), default="the current target")
    target_kind = _clean_text(target_definition.get("target_kind"), default=TargetKind.classification.value)
    success = _clean_text(target_definition.get("success_definition"))
    if decision_intent == DecisionIntent.generate_candidates.value:
        return f"Use the current chemistry set to propose follow-up candidates for {target}, while keeping the recommendation policy explicit."
    if decision_intent == DecisionIntent.reduce_uncertainty.value:
        return f"Prioritize molecules that reduce uncertainty around {target} rather than treating the shortlist as confirmed truth."
    if target_kind == TargetKind.regression.value:
        base = f"Estimate continuous values for {target} and prioritize molecules that look experimentally useful to test."
        if success:
            return f"{base} {success}"
        return base
    if success:
        return success
    if decision_intent == DecisionIntent.estimate_labels.value and target_kind == TargetKind.classification.value:
        return f"Estimate whether molecules belong to the positive class for {target}."
    return f"Prioritize molecules likely to support the current target objective for {target}."


def _trust_summary(
    *,
    session_status: str,
    analysis_report: dict[str, Any] | None,
    decision_payload: dict[str, Any] | None,
) -> str:
    analysis_report = analysis_report or {}
    decision_payload = decision_payload or {}

    if session_status == "analysis_failed_viewable":
        return "The latest analysis failed, but some saved artifacts are still viewable. Treat them as recovery context rather than a clean recommendation package."
    if session_status == "analysis_failed":
        return "The latest analysis failed. Previously saved upload data may still be useful, but the current run output should not be trusted."
    if session_status in {"analysis_queued", "analysis_running"}:
        return "Analysis is still running, so no trustworthy model interpretation is available yet."

    warnings = analysis_report.get("warnings")
    if isinstance(warnings, list):
        for warning in warnings:
            text = _clean_text(warning)
            if text:
                return text

    ranking_diagnostics = analysis_report.get("ranking_diagnostics") if isinstance(analysis_report, dict) else {}
    ranking_diagnostics = ranking_diagnostics if isinstance(ranking_diagnostics, dict) else {}
    out_of_domain_rate = ranking_diagnostics.get("out_of_domain_rate")
    try:
        out_of_domain_rate = float(out_of_domain_rate) if out_of_domain_rate is not None else None
    except (TypeError, ValueError):
        out_of_domain_rate = None

    measurement_summary = analysis_report.get("measurement_summary") if isinstance(analysis_report, dict) else {}
    measurement_summary = measurement_summary if isinstance(measurement_summary, dict) else {}
    rows_with_values = int(measurement_summary.get("rows_with_values", 0) or 0)

    if out_of_domain_rate is not None and out_of_domain_rate >= 0.5:
        return "A large share of the shortlist sits outside stronger chemistry support, so treat the run as exploratory guidance."
    if rows_with_values > 0:
        return "Uploaded measurements are available, so the ranking can be cross-checked against observed evidence rather than treated as model truth."

    artifact_state = _clean_text(decision_payload.get("artifact_state"), default="").lower()
    if artifact_state == "missing":
        return "Inspection is saved, but no decision artifact is available yet."
    return "Use this session as model-guided prioritization support, not as experimental truth."


def _latest_result_summary(
    *,
    session_status: str,
    analysis_report: dict[str, Any] | None,
    decision_payload: dict[str, Any] | None,
    current_job: dict[str, Any] | None,
) -> str:
    analysis_report = analysis_report or {}
    decision_payload = decision_payload or {}

    if session_status in {"analysis_queued", "analysis_running"} and isinstance(current_job, dict):
        progress_message = _clean_text(current_job.get("progress_message"))
        if progress_message:
            return progress_message

    report_summary = _clean_text(analysis_report.get("top_level_recommendation_summary"))
    if report_summary:
        return report_summary

    decision_summary = decision_payload.get("summary") if isinstance(decision_payload.get("summary"), dict) else {}
    candidate_count = int(decision_summary.get("candidate_count", 0) or 0)
    if candidate_count > 0:
        return f"{candidate_count} saved candidates are available for review."

    if session_status in {"analysis_failed", "analysis_failed_viewable"}:
        return _clean_text(
            (current_job or {}).get("error")
            or decision_payload.get("load_error")
            or analysis_report.get("load_error"),
            default="The latest analysis did not produce a trustworthy result package.",
        )
    if session_status == "inspection_ready":
        return "Inspection and validation are saved, but analysis has not produced a decision package yet."
    return "No saved run summary is available yet."


def build_metric_interpretation(
    *,
    target_definition: dict[str, Any] | None,
    modeling_mode: str | None,
    ranking_policy: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    target_definition = target_definition or {}
    ranking_policy = ranking_policy or {}
    target_name = _clean_text(target_definition.get("target_name"), default="the session target")
    target_kind = _clean_text(target_definition.get("target_kind"), default=TargetKind.classification.value)
    optimization_direction = _clean_text(target_definition.get("optimization_direction"))
    mode = normalize_modeling_mode(modeling_mode, default=ModelingMode.ranking_only.value)

    if target_kind == TargetKind.regression.value:
        confidence_text = f"Predicted value means the model's continuous estimate for {target_name}; it is not an observed measurement."
        uncertainty_text = "Uncertainty is dispersion across regression predictions, not calibrated probability."
    else:
        confidence_text = f"Confidence means the model's positive-class confidence for {target_name}, not experimental truth."
        uncertainty_text = "Uncertainty reflects how close the classification signal is to the model boundary."

    novelty_text = "Novelty measures structural difference from the reference chemistry set."
    applicability_text = "Applicability domain measures similarity support from known chemistry and should not be confused with novelty."
    experiment_value_text = "Experiment value is a policy-level estimate of how informative or useful a follow-up test could be."
    priority_text = "Priority score is the final policy-weighted shortlist score, not a direct model output."
    primary_label = _clean_text(ranking_policy.get("primary_score_label"), default="Primary ranking signal")
    primary_text = f"{primary_label} is the main ranking signal used to order the current shortlist."

    if mode == ModelingMode.mutation_based_candidate_generation.value:
        mode_text = "This run used mutation-based candidate generation followed by filtering and ranking; it is not learned generative chemistry."
    elif mode == ModelingMode.regression.value:
        direction_text = ""
        if optimization_direction == "maximize":
            direction_text = f" Higher predicted {target_name} values are treated as more favorable."
        elif optimization_direction == "minimize":
            direction_text = f" Lower predicted {target_name} values are treated as more favorable."
        mode_text = f"This run used a regression model to estimate a continuous target.{direction_text}"
    elif mode == ModelingMode.binary_classification.value:
        mode_text = "This run used a binary classification model plus a separate decision policy to build the shortlist."
    else:
        mode_text = "This run is operating as a ranking-only workflow, so policy ordering may matter more than model discrimination."

    return [
        {"label": "Modeling mode", "text": mode_text},
        {"label": "Primary ranking signal", "text": primary_text},
        {"label": "Model judgment", "text": confidence_text},
        {"label": "Prediction uncertainty", "text": uncertainty_text},
        {"label": "Applicability domain", "text": applicability_text},
        {"label": "Novelty", "text": novelty_text},
        {"label": "Decision policy", "text": experiment_value_text},
        {"label": "Final recommendation", "text": priority_text},
    ]


def build_session_identity(
    *,
    session_record: dict[str, Any] | None,
    upload_metadata: dict[str, Any] | None = None,
    analysis_report: dict[str, Any] | None = None,
    decision_payload: dict[str, Any] | None = None,
    current_job: dict[str, Any] | None = None,
    state_kind: str | None = None,
) -> dict[str, Any] | None:
    session_record = session_record or {}
    upload_metadata = upload_metadata or {}
    analysis_report = analysis_report or {}
    decision_payload = decision_payload or {}
    summary_metadata = session_record.get("summary_metadata") if isinstance(session_record.get("summary_metadata"), dict) else {}
    upload_summary = summary_metadata.get("upload_session_summary") if isinstance(summary_metadata.get("upload_session_summary"), dict) else {}

    session_id = _first_text(
        session_record.get("session_id"),
        upload_metadata.get("session_id"),
        analysis_report.get("session_id"),
        decision_payload.get("session_id"),
    )
    if not session_id:
        return None

    target_definition = _normalize_target_definition(
        session_record=session_record,
        upload_metadata=upload_metadata,
        analysis_report=analysis_report,
        decision_payload=decision_payload,
    )
    decision_intent = normalize_decision_intent(
        _first_text(
            analysis_report.get("decision_intent"),
            decision_payload.get("decision_intent"),
            upload_metadata.get("decision_intent"),
            upload_summary.get("decision_intent"),
        )
    )
    modeling_mode = normalize_modeling_mode(
        _first_text(
            analysis_report.get("modeling_mode"),
            decision_payload.get("modeling_mode"),
            upload_summary.get("modeling_mode"),
            summary_metadata.get("modeling_mode"),
        ),
        default=ModelingMode.ranking_only.value,
    )
    job_status = _resolve_job_status(current_job=current_job, session_record=session_record)
    artifact_state = _clean_text(decision_payload.get("artifact_state"), default="")
    has_results = bool(
        artifact_state == "ok"
        or isinstance(decision_payload.get("summary"), dict) and int((decision_payload.get("summary") or {}).get("candidate_count", 0) or 0) > 0
    )
    has_upload = bool(upload_metadata or upload_summary or session_record)
    status_semantics = build_status_semantics(
        session_record=session_record,
        upload_metadata=upload_metadata,
        analysis_report=analysis_report,
        decision_payload=decision_payload,
        current_job=current_job,
    ) or {}
    session_status = _clean_text(status_semantics.get("status_code"))
    session_status_tone = _clean_text(status_semantics.get("status_tone"))
    if not session_status:
        if job_status == JobStatus.failed.value:
            session_status, session_status_tone = "analysis_failed", "danger"
        elif job_status in {JobStatus.running.value, JobStatus.queued.value}:
            session_status, session_status_tone = job_status, "warning"
        elif has_results:
            session_status, session_status_tone = "results_ready", "success"
        elif has_upload:
            session_status, session_status_tone = "inspection_ready", "muted"
        else:
            session_status, session_status_tone = "not_started", "muted"
    if state_kind in {"artifact_missing", "empty"} and session_status == "results_ready":
        session_status, session_status_tone = "inspection_ready", "muted"

    payload = {
        "session_id": session_id,
        "source_name": _first_text(
            session_record.get("source_name"),
            upload_metadata.get("filename"),
            decision_payload.get("source_name"),
            default="Untitled upload",
        ),
        "created_at": session_record.get("created_at") or upload_metadata.get("created_at"),
        "created_at_label": _humanize_timestamp(session_record.get("created_at") or upload_metadata.get("created_at")),
        "workspace_id": _first_text(session_record.get("workspace_id")),
        "target_definition": target_definition,
        "modeling_mode": modeling_mode,
        "modeling_mode_label": _humanize_token(modeling_mode),
        "decision_intent": decision_intent,
        "decision_intent_label": _humanize_token(decision_intent),
        "session_status": session_status,
        "session_status_tone": session_status_tone,
        "current_job_status": job_status or None,
        "scientific_purpose": _scientific_purpose(target_definition, decision_intent),
        "trust_summary": _trust_summary(
            session_status=session_status,
            analysis_report=analysis_report,
            decision_payload=decision_payload,
        ),
        "latest_result_summary": _latest_result_summary(
            session_status=session_status,
            analysis_report=analysis_report,
            decision_payload=decision_payload,
            current_job=current_job,
        ),
    }
    return validate_session_identity(payload)


def domain_chip_label(status: str | None) -> str:
    cleaned = _clean_text(status).lower()
    if cleaned == DomainStatus.in_domain.value:
        return "In-domain chemistry support"
    if cleaned == DomainStatus.near_boundary.value:
        return "Near domain boundary"
    if cleaned == DomainStatus.out_of_domain.value:
        return "Weak chemistry support"
    return "Domain support unavailable"


__all__ = [
    "build_metric_interpretation",
    "build_session_identity",
    "domain_chip_label",
]
