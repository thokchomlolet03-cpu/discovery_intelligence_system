from __future__ import annotations

from typing import Any

from system.contracts import JobStatus, validate_status_semantics


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _artifact_state(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    return _clean_text(payload.get("artifact_state")).lower()


def _artifact_ok(payload: dict[str, Any] | None) -> bool:
    return _artifact_state(payload) == "ok"


def _artifact_index(session_record: dict[str, Any] | None) -> dict[str, Any]:
    summary_metadata = (session_record or {}).get("summary_metadata")
    if not isinstance(summary_metadata, dict):
        return {}
    value = summary_metadata.get("artifact_index")
    return value if isinstance(value, dict) else {}


def _validation_summary(upload_metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(upload_metadata, dict):
        return {}
    summary = upload_metadata.get("validation_summary")
    return summary if isinstance(summary, dict) else {}


def _resolve_job_status(current_job: dict[str, Any] | None, session_record: dict[str, Any] | None) -> str:
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


def _resolve_progress_stage(current_job: dict[str, Any] | None, session_record: dict[str, Any] | None) -> str:
    if isinstance(current_job, dict):
        current = _clean_text(current_job.get("progress_stage")).lower()
        if current:
            return current
    summary_metadata = (session_record or {}).get("summary_metadata")
    if isinstance(summary_metadata, dict):
        status_semantics = summary_metadata.get("status_semantics")
        if isinstance(status_semantics, dict):
            stored = _clean_text(status_semantics.get("where_failed")).lower()
            if stored:
                return stored
    return ""


def _resolve_last_error(current_job: dict[str, Any] | None, session_record: dict[str, Any] | None) -> str:
    if isinstance(current_job, dict):
        error = _clean_text(current_job.get("error"))
        if error:
            return error
    summary_metadata = (session_record or {}).get("summary_metadata")
    if isinstance(summary_metadata, dict):
        error = _clean_text(summary_metadata.get("last_error"))
        if error:
            return error
    return ""


def _failure_location(stage: str) -> str:
    normalized = _clean_text(stage).lower()
    if normalized in {"loading_session", "preparing_dataset"}:
        return "analysis_preparation"
    if normalized in {"scoring_candidates", "building_reports", "queueing_feedback", "persisting_artifacts"}:
        return "analysis_execution"
    if normalized == "finalizing_artifacts":
        return "artifact_finalization"
    return "unknown"


def _available_artifacts(
    *,
    session_record: dict[str, Any] | None,
    upload_metadata: dict[str, Any] | None,
    analysis_report: dict[str, Any] | None,
    decision_payload: dict[str, Any] | None,
) -> list[str]:
    artifact_index = _artifact_index(session_record)
    labels: list[str] = []

    if _artifact_ok(analysis_report) or "analysis_report_json" in artifact_index:
        labels.append("analysis report")
    if _artifact_ok(decision_payload) or "decision_output_json" in artifact_index:
        labels.append("decision package")
    if "review_queue_json" in artifact_index:
        labels.append("review queue")
    if "result_json" in artifact_index:
        labels.append("result payload")

    deduped: list[str] = []
    for item in labels:
        if item not in deduped:
            deduped.append(item)
    return deduped


def build_status_semantics(
    *,
    session_record: dict[str, Any] | None,
    upload_metadata: dict[str, Any] | None = None,
    analysis_report: dict[str, Any] | None = None,
    decision_payload: dict[str, Any] | None = None,
    current_job: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    session_record = session_record or {}
    upload_metadata = upload_metadata or {}
    analysis_report = analysis_report or {}
    decision_payload = decision_payload or {}

    session_id = _clean_text(
        session_record.get("session_id")
        or upload_metadata.get("session_id")
        or analysis_report.get("session_id")
        or decision_payload.get("session_id")
    )
    if not session_id and not upload_metadata:
        return None

    validation = _validation_summary(upload_metadata)
    has_upload = bool(upload_metadata or session_record)
    has_validation = bool(validation)
    validation_usable = bool(validation.get("can_run_analysis"))
    decision_viewable = _artifact_ok(decision_payload)
    analysis_viewable = _artifact_ok(analysis_report)
    available_artifacts = _available_artifacts(
        session_record=session_record,
        upload_metadata=upload_metadata,
        analysis_report=analysis_report,
        decision_payload=decision_payload,
    )
    viewable_artifacts = bool(available_artifacts)
    job_status = _resolve_job_status(current_job, session_record)
    progress_stage = _resolve_progress_stage(current_job, session_record)
    last_error = _resolve_last_error(current_job, session_record)

    status_code = "not_started"
    status_tone = "muted"
    where_failed = ""
    headline = "No saved session is available yet."
    detail = "Start by inspecting an upload so the system can create a durable session."
    next_steps = ["Inspect an upload to create a session."]
    rerun_possible = False
    trustworthy_recommendations = False
    can_open_discovery = False
    can_open_dashboard = False

    if job_status == JobStatus.failed.value:
        where_failed = _failure_location(progress_stage)
        status_code = "analysis_failed_viewable" if viewable_artifacts else "analysis_failed"
        status_tone = "danger"
        rerun_possible = has_upload
        trustworthy_recommendations = False
        can_open_discovery = decision_viewable
        can_open_dashboard = decision_viewable or analysis_viewable
        if viewable_artifacts:
            headline = "The latest analysis failed, but saved artifacts are still viewable."
            detail = (
                "Use saved upload or report artifacts cautiously. They may help you recover context, "
                "but the failed run should not be treated as a clean result."
            )
            next_steps = [
                "Review the saved artifacts that are still available.",
                "Rerun the analysis after checking mappings, labels, and warnings.",
            ]
        else:
            headline = "The latest analysis failed before a trustworthy result package was saved."
            detail = "Upload inspection may still be usable, but the failed run did not produce a trustworthy decision package."
            next_steps = [
                "Review the error and validation context.",
                "Adjust the session and rerun the analysis.",
            ]
    elif job_status in {JobStatus.queued.value, JobStatus.running.value}:
        status_code = f"analysis_{job_status}"
        status_tone = "warning"
        rerun_possible = False
        can_open_discovery = decision_viewable
        can_open_dashboard = decision_viewable or analysis_viewable
        headline = "Analysis is currently running for this session."
        detail = "Upload inspection remains usable while the current analysis job progresses, but the recommendation set is not final yet."
        next_steps = [
            "Wait for the current job to finish or reopen it later from Sessions.",
            "Do not treat intermediate progress as a final recommendation.",
        ]
    elif decision_viewable:
        status_code = "results_ready"
        status_tone = "success"
        rerun_possible = has_upload
        trustworthy_recommendations = True
        can_open_discovery = True
        can_open_dashboard = True
        headline = "Saved recommendation artifacts are available for review."
        detail = "You can open Discovery and Dashboard without rerunning the workflow. These results are still recommendations, not experimental truth."
        next_steps = [
            "Open Discovery to inspect candidate-level rationale.",
            "Use Dashboard to judge how much trust to place in the shortlist.",
        ]
    elif has_validation and validation_usable:
        status_code = "validation_ready"
        status_tone = "success"
        rerun_possible = True
        headline = "Upload inspection and validation are usable for analysis."
        detail = "The session has enough mapped and valid data to run the current analysis flow, but no decision package has been saved yet."
        next_steps = [
            "Run analysis when you are ready.",
            "Recheck mappings and label-derivation choices before starting the job.",
        ]
    elif has_validation:
        status_code = "validation_blocked"
        status_tone = "warning"
        rerun_possible = True
        headline = "The upload was inspected, but validation is still blocking analysis."
        detail = "The session exists and can be reopened, but missing mappings or invalid chemistry are preventing a trustworthy run."
        next_steps = [
            "Fix the missing mappings or invalid rows shown in validation.",
            "Rerun analysis only after the validation blockers are resolved.",
        ]
    elif has_upload:
        status_code = "inspection_ready"
        status_tone = "muted"
        rerun_possible = True
        headline = "The upload inspection is saved, but analysis has not started yet."
        detail = "You can reopen this session and continue configuring mappings, validation, and run settings."
        next_steps = [
            "Confirm the mapping and validation summary.",
            "Run analysis once the session configuration looks correct.",
        ]

    payload = {
        "status_code": status_code,
        "status_tone": status_tone,
        "where_failed": where_failed,
        "usable_upload": has_upload,
        "usable_validation": has_validation and validation_usable,
        "viewable_artifacts": viewable_artifacts,
        "trustworthy_recommendations": trustworthy_recommendations,
        "rerun_possible": rerun_possible,
        "can_open_discovery": can_open_discovery,
        "can_open_dashboard": can_open_dashboard,
        "available_artifacts": available_artifacts,
        "headline": headline,
        "detail": detail,
        "next_steps": next_steps,
        "last_error": last_error,
    }
    return validate_status_semantics(payload)


def persisted_status_snapshot(
    *,
    status: str,
    progress_stage: str,
    error: str = "",
    viewable_artifacts: bool = False,
) -> dict[str, Any]:
    normalized_status = _clean_text(status).lower()
    normalized_stage = _clean_text(progress_stage).lower()
    where_failed = _failure_location(normalized_stage) if normalized_status == JobStatus.failed.value else ""

    if normalized_status == JobStatus.queued.value:
        headline = "Analysis queued for execution."
        detail = "Saved upload data remains usable while the analysis job waits to start."
    elif normalized_status == JobStatus.running.value:
        headline = "Analysis is running."
        detail = "The session is active, but the recommendation package is not final yet."
    elif normalized_status == JobStatus.failed.value and viewable_artifacts:
        headline = "Analysis failed after some artifacts were saved."
        detail = "Saved artifacts may help recovery, but the failed run should not be treated as a clean result."
    elif normalized_status == JobStatus.failed.value:
        headline = "Analysis failed before a trustworthy result package was saved."
        detail = "Review the error and rerun after checking mappings, validation, and warnings."
    else:
        headline = "Recommendation artifacts are ready."
        detail = "The saved session can be reopened in Discovery and Dashboard."

    return validate_status_semantics(
        {
            "status_code": (
                "analysis_failed_viewable"
                if normalized_status == JobStatus.failed.value and viewable_artifacts
                else "results_ready"
                if normalized_status == JobStatus.succeeded.value
                else f"analysis_{normalized_status}" if normalized_status in {JobStatus.queued.value, JobStatus.running.value} else "analysis_failed"
            ),
            "status_tone": (
                "danger"
                if normalized_status == JobStatus.failed.value
                else "warning"
                if normalized_status in {JobStatus.queued.value, JobStatus.running.value}
                else "success"
            ),
            "where_failed": where_failed,
            "usable_upload": True,
            "usable_validation": normalized_status in {
                JobStatus.queued.value,
                JobStatus.running.value,
                JobStatus.failed.value,
                JobStatus.succeeded.value,
            },
            "viewable_artifacts": bool(viewable_artifacts),
            "trustworthy_recommendations": normalized_status == JobStatus.succeeded.value,
            "rerun_possible": normalized_status in {JobStatus.failed.value, JobStatus.succeeded.value},
            "can_open_discovery": normalized_status == JobStatus.succeeded.value,
            "can_open_dashboard": normalized_status == JobStatus.succeeded.value or bool(viewable_artifacts),
            "available_artifacts": [],
            "headline": headline,
            "detail": detail,
            "next_steps": [],
            "last_error": error,
        }
    )


__all__ = ["build_status_semantics", "persisted_status_snapshot"]
