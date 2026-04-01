from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.services.run_metadata_service import comparison_anchor_summary, infer_comparison_anchors
from system.services.session_comparison_service import build_candidate_preview, compare_session_basis
from system.services.status_semantics_service import build_status_semantics
from system.session_artifacts import load_analysis_report_payload, load_decision_artifact_payload


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
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


def _measurement_rows(session_record: dict[str, Any], analysis_report: dict[str, Any]) -> int:
    report_measurement = analysis_report.get("measurement_summary") if isinstance(analysis_report, dict) else {}
    report_measurement = report_measurement if isinstance(report_measurement, dict) else {}
    upload_metadata = session_record.get("upload_metadata") if isinstance(session_record, dict) else {}
    upload_metadata = upload_metadata if isinstance(upload_metadata, dict) else {}
    validation = upload_metadata.get("validation_summary") if isinstance(upload_metadata, dict) else {}
    validation = validation if isinstance(validation, dict) else {}
    return _safe_int(report_measurement.get("rows_with_values", validation.get("rows_with_values", 0)))


def _candidate_count(decision_payload: dict[str, Any]) -> int:
    summary = decision_payload.get("summary") if isinstance(decision_payload.get("summary"), dict) else {}
    return _safe_int(summary.get("candidate_count", 0))


def _top_experiment_value(decision_payload: dict[str, Any]) -> float | None:
    summary = decision_payload.get("summary") if isinstance(decision_payload.get("summary"), dict) else {}
    return _safe_float(summary.get("top_experiment_value"))


def _outcome_profile(decision_payload: dict[str, Any], analysis_report: dict[str, Any]) -> dict[str, Any]:
    decision_rows = decision_payload.get("top_experiments") if isinstance(decision_payload, dict) else []
    decision_rows = decision_rows if isinstance(decision_rows, list) else []
    bucket_counts = {"exploit": 0, "learn": 0, "explore": 0, "unassigned": 0}
    high_caution_count = 0

    for row in decision_rows:
        if not isinstance(row, dict):
            continue
        bucket = _clean_text(row.get("bucket") or row.get("selection_bucket"), default="unassigned").lower()
        if bucket not in bucket_counts:
            bucket = "unassigned"
        bucket_counts[bucket] += 1

        rationale = row.get("rationale") if isinstance(row.get("rationale"), dict) else {}
        trust_label = _clean_text(rationale.get("trust_label") or row.get("trust_label")).lower()
        if trust_label == "high caution" or _clean_text(row.get("domain_status")).lower() == "out_of_domain" or _clean_text(row.get("risk")).lower() == "high":
            high_caution_count += 1

    ranking_diagnostics = analysis_report.get("ranking_diagnostics") if isinstance(analysis_report, dict) else {}
    ranking_diagnostics = ranking_diagnostics if isinstance(ranking_diagnostics, dict) else {}
    leading_bucket = max(bucket_counts.items(), key=lambda item: item[1], default=("unassigned", 0))[0]
    return {
        "leading_bucket": leading_bucket,
        "bucket_counts": bucket_counts,
        "high_caution_count": high_caution_count,
        "out_of_domain_rate": _safe_float(ranking_diagnostics.get("out_of_domain_rate"), default=None),
        "spearman_rank_correlation": _safe_float(ranking_diagnostics.get("spearman_rank_correlation"), default=None),
    }


def _comparison_rank(comparison: dict[str, Any], *, results_ready: bool) -> tuple[int, int]:
    status = _clean_text(comparison.get("status"))
    if status == "directly_comparable":
        return (0, 0 if results_ready else 1)
    if status == "partially_comparable":
        return (1, 0 if results_ready else 1)
    return (2, 0 if results_ready else 1)


def _delta_lines(
    *,
    current_session: dict[str, Any],
    current_analysis_report: dict[str, Any],
    current_decision_payload: dict[str, Any],
    baseline_session: dict[str, Any],
    baseline_analysis_report: dict[str, Any],
    baseline_decision_payload: dict[str, Any],
    comparison: dict[str, Any],
) -> list[str]:
    lines: list[str] = []

    current_rows = _safe_int(
        ((current_session.get("upload_metadata") or {}).get("validation_summary") or {}).get("total_rows", 0)
    )
    baseline_rows = _safe_int(
        ((baseline_session.get("upload_metadata") or {}).get("validation_summary") or {}).get("total_rows", 0)
    )
    if current_rows or baseline_rows:
        delta = current_rows - baseline_rows
        if delta > 0:
            lines.append(f"The current session has {delta} more uploaded rows than the baseline session.")
        elif delta < 0:
            lines.append(f"The current session has {abs(delta)} fewer uploaded rows than the baseline session.")
        else:
            lines.append("The current and baseline sessions have the same uploaded row count.")

    current_measurements = _measurement_rows(current_session, current_analysis_report)
    baseline_measurements = _measurement_rows(baseline_session, baseline_analysis_report)
    if current_measurements or baseline_measurements:
        delta = current_measurements - baseline_measurements
        if delta > 0:
            lines.append(f"The current session carries {delta} more rows with recorded values.")
        elif delta < 0:
            lines.append(f"The current session carries {abs(delta)} fewer rows with recorded values.")
        else:
            lines.append("Both sessions carry the same number of rows with recorded values.")

    current_candidates = _candidate_count(current_decision_payload)
    baseline_candidates = _candidate_count(baseline_decision_payload)
    if current_candidates or baseline_candidates:
        delta = current_candidates - baseline_candidates
        if delta > 0:
            lines.append(f"The current shortlist exposes {delta} more scored candidates.")
        elif delta < 0:
            lines.append(f"The current shortlist exposes {abs(delta)} fewer scored candidates.")
        else:
            lines.append("Both sessions expose the same number of scored candidates.")

    if _clean_text(comparison.get("status")) == "directly_comparable":
        current_top = _top_experiment_value(current_decision_payload)
        baseline_top = _top_experiment_value(baseline_decision_payload)
        if current_top is not None and baseline_top is not None:
            delta = current_top - baseline_top
            if delta > 0:
                lines.append(f"The current top policy experiment value is higher by {delta:.3f}.")
            elif delta < 0:
                lines.append(f"The current top policy experiment value is lower by {abs(delta):.3f}.")
            else:
                lines.append("The current and baseline sessions have the same top policy experiment value.")

    current_outcome = _outcome_profile(current_decision_payload, current_analysis_report)
    baseline_outcome = _outcome_profile(baseline_decision_payload, baseline_analysis_report)

    current_bucket = _clean_text(current_outcome.get("leading_bucket"))
    baseline_bucket = _clean_text(baseline_outcome.get("leading_bucket"))
    if current_bucket and baseline_bucket and current_bucket != baseline_bucket:
        lines.append(
            f"The shortlist emphasis shifted from {_clean_text(baseline_bucket).replace('_', ' ')} to {_clean_text(current_bucket).replace('_', ' ')}."
        )

    current_caution = int(current_outcome.get("high_caution_count") or 0)
    baseline_caution = int(baseline_outcome.get("high_caution_count") or 0)
    if current_caution != baseline_caution:
        delta = current_caution - baseline_caution
        if delta > 0:
            lines.append(f"The current shortlist contains {delta} more high-caution candidates.")
        else:
            lines.append(f"The current shortlist contains {abs(delta)} fewer high-caution candidates.")

    current_domain_rate = current_outcome.get("out_of_domain_rate")
    baseline_domain_rate = baseline_outcome.get("out_of_domain_rate")
    if current_domain_rate is not None and baseline_domain_rate is not None:
        delta = float(current_domain_rate) - float(baseline_domain_rate)
        if abs(delta) >= 0.10:
            direction = "higher" if delta > 0 else "lower"
            lines.append(f"Weak-support rate is {direction} by {abs(delta) * 100:.1f}% against the baseline.")

    return lines[:6]


def build_active_session_comparison_context(
    *,
    current_session_record: dict[str, Any] | None,
    current_analysis_report: dict[str, Any] | None,
    current_decision_payload: dict[str, Any] | None,
    workspace_sessions: list[dict[str, Any]] | None,
    workspace_id: str,
) -> dict[str, Any]:
    current_session_record = current_session_record if isinstance(current_session_record, dict) else {}
    current_analysis_report = current_analysis_report if isinstance(current_analysis_report, dict) else {}
    current_decision_payload = current_decision_payload if isinstance(current_decision_payload, dict) else {}
    workspace_sessions = workspace_sessions if isinstance(workspace_sessions, list) else []

    current_session_id = _clean_text(current_session_record.get("session_id"))
    if not current_session_id:
        return {}

    current_upload_metadata = current_session_record.get("upload_metadata") if isinstance(current_session_record.get("upload_metadata"), dict) else {}
    current_focus = {
        "comparison_anchors": infer_comparison_anchors(
            session_record=current_session_record,
            upload_metadata=current_upload_metadata,
            analysis_report=current_analysis_report,
            decision_payload=current_decision_payload,
        ),
        "status_semantics": build_status_semantics(
            session_record=current_session_record,
            upload_metadata=current_upload_metadata,
            analysis_report=current_analysis_report,
            decision_payload=current_decision_payload,
            current_job=None,
        ),
        "outcome_profile": _outcome_profile(current_decision_payload, current_analysis_report),
        "candidate_preview": build_candidate_preview(current_decision_payload),
    }

    best_candidate: dict[str, Any] | None = None
    best_analysis_report: dict[str, Any] | None = None
    best_decision_payload: dict[str, Any] | None = None
    best_comparison: dict[str, Any] | None = None
    best_sort_key: tuple[int, int, float] | None = None

    for session in workspace_sessions:
        session_id = _clean_text((session or {}).get("session_id"))
        if not session_id or session_id == current_session_id:
            continue

        analysis_report = load_analysis_report_payload(
            session_id=session_id,
            workspace_id=workspace_id,
            allow_global_fallback=False,
        )
        decision_payload = load_decision_artifact_payload(
            session_id=session_id,
            workspace_id=workspace_id,
            allow_global_fallback=False,
        )
        upload_metadata = session.get("upload_metadata") if isinstance(session.get("upload_metadata"), dict) else {}
        candidate_focus = {
            "comparison_anchors": infer_comparison_anchors(
                session_record=session,
                upload_metadata=upload_metadata,
                analysis_report=analysis_report,
                decision_payload=decision_payload,
            ),
            "status_semantics": build_status_semantics(
                session_record=session,
                upload_metadata=upload_metadata,
                analysis_report=analysis_report,
                decision_payload=decision_payload,
                current_job=None,
            ),
            "outcome_profile": _outcome_profile(decision_payload, analysis_report),
            "candidate_preview": build_candidate_preview(decision_payload),
        }
        comparison = compare_session_basis(
            focus_session=current_focus,
            candidate_session=candidate_focus,
        )
        results_ready = bool((candidate_focus["status_semantics"] or {}).get("trustworthy_recommendations"))
        updated_at = _to_datetime(session.get("updated_at") or session.get("created_at"))
        updated_rank = -(updated_at.timestamp() if updated_at else 0.0)
        sort_key = (*_comparison_rank(comparison, results_ready=results_ready), updated_rank)
        if best_sort_key is None or sort_key < best_sort_key:
            best_sort_key = sort_key
            best_candidate = session
            best_analysis_report = analysis_report
            best_decision_payload = decision_payload
            best_comparison = comparison

    if best_candidate is None or best_comparison is None:
        return {
            "available": False,
            "headline": "No scientifically comparable prior session was found.",
            "summary": "This session does not yet have a recorded baseline in the same workspace that matches its target and modeling contract closely enough for useful read-across.",
            "comparison": {},
            "baseline": {},
            "delta_lines": [],
        }

    best_analysis_report = best_analysis_report if isinstance(best_analysis_report, dict) else {}
    best_decision_payload = best_decision_payload if isinstance(best_decision_payload, dict) else {}
    baseline_session_id = _clean_text(best_candidate.get("session_id"))
    baseline_source_name = _clean_text(
        best_candidate.get("source_name")
        or ((best_candidate.get("upload_metadata") or {}).get("filename"))
        or "Baseline session"
    )
    baseline_anchors = infer_comparison_anchors(
        session_record=best_candidate,
        upload_metadata=best_candidate.get("upload_metadata") if isinstance(best_candidate.get("upload_metadata"), dict) else {},
        analysis_report=best_analysis_report,
        decision_payload=best_decision_payload,
    )
    delta_lines = _delta_lines(
        current_session=current_session_record,
        current_analysis_report=current_analysis_report,
        current_decision_payload=current_decision_payload,
        baseline_session=best_candidate,
        baseline_analysis_report=best_analysis_report,
        baseline_decision_payload=best_decision_payload,
        comparison=best_comparison,
    )

    headline_map = {
        "directly_comparable": f"Compared against the nearest directly comparable prior session: {baseline_source_name}.",
        "partially_comparable": f"Compared cautiously against the nearest partially comparable prior session: {baseline_source_name}.",
        "not_comparable": f"The nearest prior session is not directly comparable: {baseline_source_name}.",
    }

    return {
        "available": True,
        "headline": headline_map.get(best_comparison["status"], f"Compared against {baseline_source_name}."),
        "summary": best_comparison.get("summary") or "",
        "comparison": best_comparison,
        "baseline": {
            "session_id": baseline_session_id,
            "source_name": baseline_source_name,
            "created_at_label": _humanize_timestamp(best_candidate.get("created_at")),
            "updated_at_label": _humanize_timestamp(best_candidate.get("updated_at")),
            "comparison_basis_label": comparison_anchor_summary(baseline_anchors),
            "upload_url": f"/upload?session_id={baseline_session_id}",
            "discovery_url": f"/discovery?session_id={baseline_session_id}",
            "dashboard_url": f"/dashboard?session_id={baseline_session_id}",
        },
        "delta_lines": delta_lines,
    }


__all__ = ["build_active_session_comparison_context"]
