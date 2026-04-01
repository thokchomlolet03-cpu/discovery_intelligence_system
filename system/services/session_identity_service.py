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
from system.services.run_metadata_service import build_run_provenance


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

    analysis_anchors = analysis_report.get("comparison_anchors") if isinstance(analysis_report.get("comparison_anchors"), dict) else {}
    decision_anchors = decision_payload.get("comparison_anchors") if isinstance(decision_payload.get("comparison_anchors"), dict) else {}
    anchor_target = {
        "target_name": _first_text(decision_anchors.get("target_name"), analysis_anchors.get("target_name")),
        "target_kind": _first_text(decision_anchors.get("target_kind"), analysis_anchors.get("target_kind")),
        "optimization_direction": _first_text(
            decision_anchors.get("optimization_direction"),
            analysis_anchors.get("optimization_direction"),
        ),
        "measurement_column": _first_text(
            decision_anchors.get("measurement_column"),
            analysis_anchors.get("measurement_column"),
        ),
        "label_column": _first_text(decision_anchors.get("label_column"), analysis_anchors.get("label_column")),
        "measurement_unit": _first_text(
            decision_anchors.get("measurement_unit"),
            analysis_anchors.get("measurement_unit"),
        ),
        "dataset_type": _first_text(decision_anchors.get("dataset_type"), analysis_anchors.get("dataset_type")),
        "mapping_confidence": _first_text(
            decision_anchors.get("mapping_confidence"),
            analysis_anchors.get("mapping_confidence"),
        ),
    }
    anchor_target = {key: value for key, value in anchor_target.items() if value}

    existing = _first_dict(
        analysis_report.get("target_definition"),
        decision_payload.get("target_definition"),
        anchor_target,
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


def build_trust_context(
    *,
    target_definition: dict[str, Any] | None,
    modeling_mode: str | None,
    analysis_report: dict[str, Any] | None = None,
    decision_payload: dict[str, Any] | None = None,
    validation_summary: dict[str, Any] | None = None,
    ranking_policy: dict[str, Any] | None = None,
    run_provenance: dict[str, Any] | None = None,
) -> dict[str, str]:
    target_definition = target_definition or {}
    analysis_report = analysis_report or {}
    decision_payload = decision_payload or {}
    validation_summary = validation_summary or {}
    ranking_policy = ranking_policy or {}
    run_provenance = run_provenance or {}

    target_name = _clean_text(target_definition.get("target_name"), default="the session target")
    dataset_type = _clean_text(
        target_definition.get("dataset_type")
        or validation_summary.get("semantic_mode")
    )
    modeling_mode = normalize_modeling_mode(modeling_mode, default=ModelingMode.ranking_only.value)

    measurement_summary = analysis_report.get("measurement_summary") if isinstance(analysis_report, dict) else {}
    measurement_summary = measurement_summary if isinstance(measurement_summary, dict) else {}
    rows_with_values = int(
        measurement_summary.get("rows_with_values", validation_summary.get("rows_with_values", 0)) or 0
    )
    rows_with_labels = int(
        measurement_summary.get("rows_with_labels", validation_summary.get("rows_with_labels", 0)) or 0
    )
    if rows_with_values <= 0 and isinstance(decision_payload.get("top_experiments"), list):
        rows_with_values = sum(
            1
            for row in decision_payload.get("top_experiments", [])
            if isinstance(row, dict) and row.get("observed_value") is not None
        )
    label_source = _clean_text(
        measurement_summary.get("label_source", validation_summary.get("label_source")),
        default="not recorded",
    )

    ranking_diagnostics = analysis_report.get("ranking_diagnostics") if isinstance(analysis_report, dict) else {}
    ranking_diagnostics = ranking_diagnostics if isinstance(ranking_diagnostics, dict) else {}
    out_of_domain_rate = ranking_diagnostics.get("out_of_domain_rate")
    try:
        out_of_domain_rate = float(out_of_domain_rate) if out_of_domain_rate is not None else None
    except (TypeError, ValueError):
        out_of_domain_rate = None

    evidence_basis_label = "Structure-driven session context"
    if rows_with_values > 0:
        evidence_basis_label = "Observed measurement evidence"
        evidence_basis_summary = (
            f"{rows_with_values} uploaded row{'s' if rows_with_values != 1 else ''} carry observed values, so the "
            "shortlist can be cross-checked against measured evidence rather than read as model truth."
        )
    elif rows_with_labels > 0:
        evidence_basis_label = "Labeled class evidence"
        evidence_basis_summary = (
            f"{rows_with_labels} uploaded row{'s' if rows_with_labels != 1 else ''} carry class labels "
            f"({label_source.replace('_', ' ')}), but no observed value column is available for direct value-based cross-checking."
        )
    elif dataset_type == "structure_only":
        evidence_basis_summary = (
            "This session is working from structure-only chemistry input, so the shortlist should be read as model- and "
            "policy-guided prioritization rather than measured evidence."
        )
    else:
        evidence_basis_summary = (
            "No uploaded measurements or explicit labels were recorded, so the shortlist should be interpreted as "
            "structure-driven ranking support rather than observed evidence."
        )

    if modeling_mode == ModelingMode.regression.value:
        model_basis_label = "Regression model output"
        model_basis_summary = (
            f"The model estimated a continuous value for {target_name}; predicted values are not observed measurements, "
            "and ranking compatibility is only a normalized desirability signal for ordering."
        )
    elif modeling_mode == ModelingMode.binary_classification.value:
        model_basis_label = "Classification model output"
        model_basis_summary = f"The model estimated positive-class support for {target_name}; confidence is not experimental truth."
    elif modeling_mode == ModelingMode.mutation_based_candidate_generation.value:
        model_basis_label = "Candidate generation plus ranking"
        model_basis_summary = (
            "This run used mutation-based candidate generation followed by filtering and ranking, not a broader generative discovery model."
        )
    else:
        model_basis_label = "Ranking-heavy workflow"
        model_basis_summary = (
            "This run behaved mainly as a ranking workflow, so the shortlist depends more on policy ordering than on a target-trained model."
        )

    primary_signal = _clean_text(ranking_policy.get("primary_score_label"), default="Priority score")
    scoring_mode_label = _clean_text(run_provenance.get("scoring_mode_label"), default="policy scoring")
    policy_basis_label = "Decision policy output"
    policy_basis_summary = (
        f"Final shortlist order is driven by {primary_signal} under {scoring_mode_label.lower()}, which is a policy output rather than a raw model score."
    )

    bridge_state_summary = _clean_text(run_provenance.get("bridge_state_summary"))
    if not bridge_state_summary:
        if out_of_domain_rate is not None and out_of_domain_rate >= 0.5:
            bridge_state_summary = (
                "A large share of the shortlist sits outside stronger chemistry support, so treat this run as exploratory guidance."
            )
        elif modeling_mode == ModelingMode.ranking_only.value:
            bridge_state_summary = (
                "This session is operating as a ranking-heavy workflow, so policy ordering carries more of the recommendation burden."
            )

    if bridge_state_summary or (rows_with_values <= 0 and rows_with_labels <= 0):
        evidence_support_label = "Limited evidence support"
    elif rows_with_values > 0 and (out_of_domain_rate is None or out_of_domain_rate <= 0.25):
        evidence_support_label = "Stronger evidence support"
    else:
        evidence_support_label = "Moderate evidence support"

    return {
        "evidence_basis_label": evidence_basis_label,
        "evidence_basis_summary": evidence_basis_summary,
        "model_basis_label": model_basis_label,
        "model_basis_summary": model_basis_summary,
        "policy_basis_label": policy_basis_label,
        "policy_basis_summary": policy_basis_summary,
        "bridge_state_summary": bridge_state_summary,
        "evidence_support_label": evidence_support_label,
    }


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
        confidence_text = (
            f"Predicted value means the model's continuous estimate for {target_name}; it is not an observed measurement. "
            "When ranking compatibility is shown, it reflects normalized desirability for ordering rather than the value itself."
        )
        uncertainty_text = "Prediction dispersion is spread across regression predictions, not calibrated probability."
    else:
        confidence_text = f"Confidence means the model's positive-class confidence for {target_name}, not experimental truth."
        uncertainty_text = "Uncertainty reflects how close the classification signal is to the model boundary."

    fact_text = (
        "Observed values, labels, mapped columns, and target metadata come from the uploaded session or derived session mapping, not from the model."
    )
    novelty_text = "Novelty measures structural difference from the reference chemistry set."
    applicability_text = "Applicability domain measures similarity support from known chemistry and should not be confused with novelty."
    experiment_value_text = "Experiment value is a policy-level estimate of how informative or useful a follow-up test could be."
    priority_text = "Priority score is the final policy-weighted shortlist score, not a direct model output."
    primary_label = _clean_text(ranking_policy.get("primary_score_label"), default="Primary ranking signal")
    primary_text = f"{primary_label} is the main ranking signal used to order the current shortlist."
    if target_kind == TargetKind.regression.value:
        primary_text += " For measurement sessions, this ranking signal should be read alongside predicted value, not as a substitute for it."

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
        {"label": "Observed or derived data facts", "text": fact_text},
        {"label": "Modeling mode", "text": mode_text},
        {"label": "Primary ranking signal", "text": primary_text},
        {"label": "Model judgment", "text": confidence_text},
        {"label": "Prediction uncertainty", "text": uncertainty_text},
        {"label": "Applicability and novelty", "text": f"{applicability_text} {novelty_text}"},
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

    run_contract = (
        analysis_report.get("run_contract") if isinstance(analysis_report.get("run_contract"), dict) else {}
    ) or (
        decision_payload.get("run_contract") if isinstance(decision_payload.get("run_contract"), dict) else {}
    )
    comparison_anchors = (
        analysis_report.get("comparison_anchors") if isinstance(analysis_report.get("comparison_anchors"), dict) else {}
    ) or (
        decision_payload.get("comparison_anchors") if isinstance(decision_payload.get("comparison_anchors"), dict) else {}
    )
    run_provenance = build_run_provenance(
        run_contract=run_contract,
        comparison_anchors=comparison_anchors,
    )
    trust_context = build_trust_context(
        target_definition=target_definition,
        modeling_mode=modeling_mode,
        analysis_report=analysis_report,
        decision_payload=decision_payload,
        validation_summary=_first_dict(
            upload_metadata.get("validation_summary"),
            upload_summary.get("validation_summary"),
        ),
        ranking_policy=analysis_report.get("ranking_policy") if isinstance(analysis_report.get("ranking_policy"), dict) else {},
        run_provenance=run_provenance,
    )

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
        "evidence_support_label": trust_context.get("evidence_support_label", ""),
        "evidence_summary": trust_context.get("evidence_basis_summary", ""),
        "bridge_state_summary": trust_context.get("bridge_state_summary", ""),
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
    "build_trust_context",
    "build_metric_interpretation",
    "build_session_identity",
    "domain_chip_label",
]
