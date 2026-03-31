from __future__ import annotations

from typing import Any, Callable

from system.discovery_workbench import humanize_timestamp
from system.session_artifacts import load_analysis_report_payload, load_decision_artifact_payload


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _measurement_summary(session: dict[str, Any], analysis_report: dict[str, Any]) -> dict[str, Any]:
    upload_metadata = session.get("upload_metadata") or {}
    validation = upload_metadata.get("validation_summary") if isinstance(upload_metadata, dict) else {}
    validation = validation if isinstance(validation, dict) else {}

    report_measurement = analysis_report.get("measurement_summary") if isinstance(analysis_report, dict) else {}
    report_measurement = report_measurement if isinstance(report_measurement, dict) else {}

    return {
        "semantic_mode": str(
            report_measurement.get("semantic_mode")
            or validation.get("semantic_mode")
            or upload_metadata.get("semantic_mode")
            or ""
        ),
        "value_column": str(
            report_measurement.get("value_column")
            or validation.get("value_column")
            or (upload_metadata.get("selected_mapping") or {}).get("value")
            or ""
        ),
        "rows_with_values": _safe_int(
            report_measurement.get("rows_with_values", validation.get("rows_with_values", 0))
        ),
        "rows_with_labels": _safe_int(
            report_measurement.get("rows_with_labels", validation.get("rows_with_labels", 0))
        ),
        "label_source": str(
            report_measurement.get("label_source")
            or validation.get("label_source")
            or ""
        ),
    }


def _session_state_label(*, job_status: str, results_ready: bool, has_upload: bool) -> tuple[str, str]:
    normalized = str(job_status or "").strip().lower()
    if normalized == "failed":
        return "Failed", "danger"
    if normalized in {"running", "queued"}:
        return "Running", "warning"
    if normalized == "succeeded" and results_ready:
        return "Ready", "success"
    if has_upload:
        return "Inspected", "muted"
    return "Stored", "muted"


def build_session_history_context(
    sessions: list[dict[str, Any]],
    *,
    workspace_id: str,
    active_session_id: str | None = None,
    latest_session_id: str | None = None,
    job_fetcher: Callable[[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    for session in sessions:
        session_id = str(session.get("session_id") or "").strip()
        if not session_id:
            continue

        upload_metadata = session.get("upload_metadata") or {}
        upload_metadata = upload_metadata if isinstance(upload_metadata, dict) else {}
        validation = upload_metadata.get("validation_summary") if isinstance(upload_metadata, dict) else {}
        validation = validation if isinstance(validation, dict) else {}
        summary_metadata = session.get("summary_metadata") or {}
        summary_metadata = summary_metadata if isinstance(summary_metadata, dict) else {}

        latest_job_id = str(session.get("latest_job_id") or "").strip()
        latest_job: dict[str, Any] | None = None
        if latest_job_id and job_fetcher is not None:
            try:
                latest_job = job_fetcher(latest_job_id, workspace_id)
            except Exception:
                latest_job = None

        decision_payload = load_decision_artifact_payload(
            session_id=session_id,
            workspace_id=workspace_id,
            allow_global_fallback=False,
        )
        analysis_report = load_analysis_report_payload(
            session_id=session_id,
            workspace_id=workspace_id,
            allow_global_fallback=False,
        )

        results_ready = str(decision_payload.get("artifact_state") or "").strip().lower() == "ok"
        measurement = _measurement_summary(session, analysis_report)
        top_summary = decision_payload.get("summary") if isinstance(decision_payload.get("summary"), dict) else {}
        job_status = str(
            (latest_job or {}).get("status")
            or summary_metadata.get("last_job_status")
            or ""
        ).strip().lower()
        state_label, state_tone = _session_state_label(
            job_status=job_status,
            results_ready=results_ready,
            has_upload=bool(upload_metadata),
        )
        ranking_policy = analysis_report.get("ranking_policy") if isinstance(analysis_report, dict) else {}
        ranking_policy = ranking_policy if isinstance(ranking_policy, dict) else {}
        recommendation_summary = str(
            analysis_report.get("top_level_recommendation_summary")
            or decision_payload.get("load_error")
            or summary_metadata.get("last_error")
            or ""
        ).strip()

        items.append(
            {
                "session_id": session_id,
                "source_name": str(session.get("source_name") or upload_metadata.get("filename") or "Untitled upload"),
                "input_type": str(session.get("input_type") or upload_metadata.get("input_type") or ""),
                "semantic_mode": measurement.get("semantic_mode") or "Not detected",
                "value_column": measurement.get("value_column") or "Not mapped",
                "rows_total": _safe_int(validation.get("total_rows", 0)),
                "valid_smiles_count": _safe_int(validation.get("valid_smiles_count", 0)),
                "duplicate_count": _safe_int(validation.get("duplicate_count", 0)),
                "rows_with_values": _safe_int(measurement.get("rows_with_values", 0)),
                "rows_with_labels": _safe_int(measurement.get("rows_with_labels", 0)),
                "candidate_count": _safe_int(top_summary.get("candidate_count", 0)),
                "top_experiment_value": _safe_float(top_summary.get("top_experiment_value", 0.0)),
                "job_status": job_status or "unknown",
                "job_status_label": state_label,
                "job_status_tone": state_tone,
                "job_stage": str((latest_job or {}).get("progress_stage") or ""),
                "job_progress_percent": _safe_int((latest_job or {}).get("progress_percent", 0)),
                "job_message": str(
                    (latest_job or {}).get("progress_message")
                    or summary_metadata.get("last_error")
                    or ""
                ),
                "created_at": humanize_timestamp(session.get("created_at")),
                "updated_at": humanize_timestamp(session.get("updated_at")),
                "results_ready": results_ready,
                "warning_count": len(analysis_report.get("warnings") or []) if isinstance(analysis_report, dict) else 0,
                "primary_score_label": str(ranking_policy.get("primary_score_label") or ""),
                "recommendation_summary": recommendation_summary,
                "is_active": bool(active_session_id and session_id == active_session_id),
                "is_latest": bool(latest_session_id and session_id == latest_session_id),
                "upload_url": f"/upload?session_id={session_id}",
                "discovery_url": f"/discovery?session_id={session_id}",
                "dashboard_url": f"/dashboard?session_id={session_id}",
                "download_url": f"/api/discovery/download?session_id={session_id}",
            }
        )

    return {
        "items": items,
        "counts": {
            "stored_sessions": len(items),
            "ready_sessions": sum(1 for item in items if item["results_ready"]),
            "measurement_sessions": sum(1 for item in items if item["rows_with_values"] > 0),
            "running_sessions": sum(1 for item in items if item["job_status"] in {"queued", "running"}),
        },
        "active_session_id": active_session_id or "",
        "latest_session_id": latest_session_id or "",
    }
