from __future__ import annotations

from typing import Any, Callable

from system.discovery_workbench import humanize_timestamp
from system.services.run_metadata_service import comparison_anchor_summary, infer_comparison_anchors
from system.services.scientific_session_truth_service import build_controlled_reuse_state, build_scientific_session_truth
from system.services.session_comparison_service import (
    build_candidate_preview,
    build_session_comparison_matrix,
    build_session_comparison_overview,
    compare_session_basis,
)
from system.services.session_identity_service import build_session_identity
from system.services.status_semantics_service import build_status_semantics
from system.services.workspace_feedback_service import build_session_workspace_memory, build_workspace_feedback_summary
from system.session_artifacts import (
    load_analysis_report_payload,
    load_decision_artifact_payload,
    load_scientific_session_truth_payload,
)
from system.db.repositories import ReviewRepository


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


def _scientific_truth_source_label(source_path: str, *, backfilled: bool) -> str:
    if backfilled:
        return "Compatibility backfill"
    source = str(source_path or "").strip()
    if source.endswith("scientific_session_truth.json"):
        return "Canonical scientific session truth"
    if source == "session_summary_metadata#scientific_session_truth":
        return "Session summary scientific truth"
    if source.endswith("#scientific_session_truth"):
        return "Nested result scientific truth"
    return "Scientific truth not recorded"


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


def _outcome_profile(decision_payload: dict[str, Any], analysis_report: dict[str, Any]) -> dict[str, Any]:
    decision_rows = decision_payload.get("top_experiments") if isinstance(decision_payload, dict) else []
    decision_rows = decision_rows if isinstance(decision_rows, list) else []
    bucket_counts = {"exploit": 0, "learn": 0, "explore": 0, "unassigned": 0}
    trust_counts = {
        "stronger_trust": 0,
        "mixed_trust": 0,
        "exploratory_trust": 0,
        "high_caution": 0,
        "unlabeled": 0,
    }

    for row in decision_rows:
        if not isinstance(row, dict):
            continue
        bucket = str(row.get("bucket") or row.get("selection_bucket") or "unassigned").strip().lower()
        if bucket not in bucket_counts:
            bucket = "unassigned"
        bucket_counts[bucket] += 1

        rationale = row.get("rationale") if isinstance(row.get("rationale"), dict) else {}
        trust_label = str(rationale.get("trust_label") or row.get("trust_label") or "").strip().lower()
        if trust_label == "stronger trust":
            trust_counts["stronger_trust"] += 1
        elif trust_label == "mixed trust":
            trust_counts["mixed_trust"] += 1
        elif trust_label == "exploratory trust":
            trust_counts["exploratory_trust"] += 1
        elif trust_label == "high caution":
            trust_counts["high_caution"] += 1
        else:
            trust_counts["unlabeled"] += 1

    ranking_diagnostics = analysis_report.get("ranking_diagnostics") if isinstance(analysis_report, dict) else {}
    ranking_diagnostics = ranking_diagnostics if isinstance(ranking_diagnostics, dict) else {}

    def _leading_label(counts: dict[str, int], fallback: str) -> str:
        best = max(counts.items(), key=lambda item: item[1], default=(fallback, 0))
        return best[0] if best[1] > 0 else fallback

    leading_bucket = _leading_label(bucket_counts, "unassigned")
    dominant_trust = _leading_label(trust_counts, "unlabeled")

    out_of_domain_rate = _safe_float(ranking_diagnostics.get("out_of_domain_rate"), default=None)
    spearman_rank_correlation = _safe_float(ranking_diagnostics.get("spearman_rank_correlation"), default=None)
    top_k_measurement_lift = _safe_float(ranking_diagnostics.get("top_k_measurement_lift"), default=None)

    bucket_summary = (
        f"Exploit {bucket_counts['exploit']} / Learn {bucket_counts['learn']} / Explore {bucket_counts['explore']}"
    )
    trust_summary = (
        f"Stronger trust {trust_counts['stronger_trust']} / Mixed {trust_counts['mixed_trust']} / "
        f"Exploratory {trust_counts['exploratory_trust']} / High caution {trust_counts['high_caution']}"
    )

    diagnostics_bits: list[str] = []
    if spearman_rank_correlation is not None:
        diagnostics_bits.append(f"Rank corr {spearman_rank_correlation:.3f}")
    if out_of_domain_rate is not None:
        diagnostics_bits.append(f"Weak-support {out_of_domain_rate * 100:.1f}%")
    if top_k_measurement_lift is not None:
        diagnostics_bits.append(f"Top-k lift {top_k_measurement_lift:.3f}")

    return {
        "bucket_counts": bucket_counts,
        "leading_bucket": leading_bucket,
        "bucket_summary": bucket_summary,
        "trust_counts": trust_counts,
        "dominant_trust": dominant_trust,
        "trust_summary": trust_summary,
        "out_of_domain_rate": out_of_domain_rate,
        "spearman_rank_correlation": spearman_rank_correlation,
        "top_k_measurement_lift": top_k_measurement_lift,
        "diagnostics_summary": " / ".join(diagnostics_bits) if diagnostics_bits else "No ranking diagnostics recorded.",
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
    workspace_reviews = ReviewRepository().list_reviews(workspace_id=workspace_id)
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
        scientific_truth_payload = load_scientific_session_truth_payload(
            session_id=session_id,
            workspace_id=workspace_id,
            allow_global_fallback=False,
        )
        scientific_truth = (
            scientific_truth_payload
            if isinstance(scientific_truth_payload, dict)
            and str(scientific_truth_payload.get("artifact_state") or "").strip().lower() == "ok"
            else summary_metadata.get("scientific_session_truth")
            if isinstance(summary_metadata.get("scientific_session_truth"), dict)
            else {}
        )
        scientific_truth_backfilled = False

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
        if not scientific_truth and (
            isinstance(analysis_report, dict) and analysis_report
            or isinstance(decision_payload, dict) and decision_payload
        ):
            scientific_truth = build_scientific_session_truth(
                session_id=session_id,
                workspace_id=workspace_id,
                source_name=str(session.get("source_name") or upload_metadata.get("filename") or ""),
                session_record=session,
                upload_metadata=upload_metadata,
                analysis_report=analysis_report,
                decision_payload=decision_payload,
            )
            scientific_truth_backfilled = True

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
        session_identity = build_session_identity(
            session_record=session,
            upload_metadata=upload_metadata,
            analysis_report=analysis_report,
            decision_payload=decision_payload,
            current_job=latest_job,
            state_kind="ready" if results_ready else "",
        )
        status_semantics = build_status_semantics(
            session_record=session,
            upload_metadata=upload_metadata,
            analysis_report=analysis_report,
            decision_payload=decision_payload,
            current_job=latest_job,
        )
        comparison_anchors = infer_comparison_anchors(
            session_record=session,
            upload_metadata=upload_metadata,
            analysis_report=analysis_report,
            decision_payload=decision_payload,
        )
        outcome_profile = _outcome_profile(decision_payload, analysis_report)
        candidate_preview = build_candidate_preview(decision_payload)
        workspace_memory_candidates = build_candidate_preview(decision_payload, limit=25)
        evidence_loop = scientific_truth.get("evidence_loop") if isinstance(scientific_truth.get("evidence_loop"), dict) else {}
        evidence_activation_policy = (
            scientific_truth.get("evidence_activation_policy")
            if isinstance(scientific_truth.get("evidence_activation_policy"), dict)
            else {}
        )
        controlled_reuse = (
            scientific_truth.get("controlled_reuse")
            if isinstance(scientific_truth.get("controlled_reuse"), dict)
            else {}
        )
        scientific_truth_source_label = _scientific_truth_source_label(
            str(scientific_truth_payload.get("source_path") or ""),
            backfilled=scientific_truth_backfilled,
        )

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
                "session_identity": session_identity,
                "scientific_session_truth": scientific_truth,
                "scientific_truth_source_label": scientific_truth_source_label,
                "claims_summary": scientific_truth.get("claims_summary") if isinstance(scientific_truth.get("claims_summary"), dict) else {},
                "claim_refs": list(scientific_truth.get("claim_refs") or []) if isinstance(scientific_truth.get("claim_refs"), list) else [],
                "experiment_request_summary": scientific_truth.get("experiment_request_summary")
                if isinstance(scientific_truth.get("experiment_request_summary"), dict)
                else {},
                "experiment_request_refs": list(scientific_truth.get("experiment_request_refs") or [])
                if isinstance(scientific_truth.get("experiment_request_refs"), list)
                else [],
                "linked_result_summary": scientific_truth.get("linked_result_summary")
                if isinstance(scientific_truth.get("linked_result_summary"), dict)
                else {},
                "experiment_result_refs": list(scientific_truth.get("experiment_result_refs") or [])
                if isinstance(scientific_truth.get("experiment_result_refs"), list)
                else [],
                "belief_update_summary": scientific_truth.get("belief_update_summary")
                if isinstance(scientific_truth.get("belief_update_summary"), dict)
                else {},
                "belief_update_refs": list(scientific_truth.get("belief_update_refs") or [])
                if isinstance(scientific_truth.get("belief_update_refs"), list)
                else [],
                "belief_state_ref": scientific_truth.get("belief_state_ref")
                if isinstance(scientific_truth.get("belief_state_ref"), dict)
                else {},
                "belief_state_summary": scientific_truth.get("belief_state_summary")
                if isinstance(scientific_truth.get("belief_state_summary"), dict)
                else {},
                "evidence_loop_summary": str((evidence_loop.get("summary")) or "").strip(),
                "learning_boundary_note": str((evidence_loop.get("learning_boundary_note")) or "").strip(),
                "activation_boundary_summary": str((evidence_loop.get("activation_boundary_summary")) or "").strip(),
                "future_activation_candidates": list(evidence_loop.get("future_activation_candidates") or [])
                if isinstance(evidence_loop.get("future_activation_candidates"), list)
                else [],
                "activation_policy_summary": str((evidence_activation_policy.get("summary")) or "").strip(),
                "recommendation_reuse_summary": str((evidence_activation_policy.get("recommendation_reuse_summary")) or "").strip(),
                "future_ranking_context_summary": str((evidence_activation_policy.get("future_ranking_context_summary")) or "").strip(),
                "future_learning_eligibility_summary": str(
                    (evidence_activation_policy.get("future_learning_eligibility_summary") or evidence_activation_policy.get("learning_eligibility_summary")) or ""
                ).strip(),
                "permanently_non_active_summary": str((evidence_activation_policy.get("permanently_non_active_summary")) or "").strip(),
                "controlled_reuse": controlled_reuse,
                "controlled_reuse_summary": str((controlled_reuse.get("recommendation_reuse_summary")) or "").strip(),
                "ranking_context_reuse_summary": str((controlled_reuse.get("ranking_context_reuse_summary")) or "").strip(),
                "interpretation_support_summary": str((controlled_reuse.get("interpretation_support_summary")) or "").strip(),
                "comparison_ready": bool(scientific_truth.get("comparison_ready")),
                "status_semantics": status_semantics,
                "comparison_anchors": comparison_anchors,
                "comparison_basis_label": comparison_anchor_summary(comparison_anchors),
                "outcome_profile": outcome_profile,
                "candidate_preview": candidate_preview,
                "workspace_memory_candidates": workspace_memory_candidates,
                "is_active": bool(active_session_id and session_id == active_session_id),
                "is_latest": bool(latest_session_id and session_id == latest_session_id),
                "upload_url": f"/upload?session_id={session_id}",
                "discovery_url": f"/discovery?session_id={session_id}",
                "dashboard_url": f"/dashboard?session_id={session_id}",
                "download_url": f"/api/discovery/download?session_id={session_id}",
            }
        )

    focus_session = next((item for item in items if item["is_active"]), None)
    if focus_session is None:
        focus_session = next((item for item in items if item["is_latest"]), None)
    if focus_session is None:
        focus_session = next((item for item in items if item["results_ready"]), None)
    if focus_session is None and items:
        focus_session = items[0]

    source_name_by_session_id = {
        str(item.get("session_id") or ""): str(item.get("source_name") or "")
        for item in items
        if item.get("session_id")
    }
    for item in items:
        item["workspace_memory"] = build_session_workspace_memory(
            item.get("workspace_memory_candidates"),
            session_id=item.get("session_id"),
            workspace_id=workspace_id,
            review_events=workspace_reviews,
            session_labels=source_name_by_session_id,
        )
        if not item.get("controlled_reuse"):
            item["controlled_reuse"] = build_controlled_reuse_state(
                evidence_activation_policy=(
                    (item.get("scientific_session_truth") or {}).get("evidence_activation_policy")
                    if isinstance(item.get("scientific_session_truth"), dict)
                    else {}
                ),
                workspace_memory=item.get("workspace_memory"),
            )
        controlled_reuse = item.get("controlled_reuse") if isinstance(item.get("controlled_reuse"), dict) else {}
        item["controlled_reuse_summary"] = str(controlled_reuse.get("recommendation_reuse_summary") or "").strip()
        item["ranking_context_reuse_summary"] = str(controlled_reuse.get("ranking_context_reuse_summary") or "").strip()
        item["interpretation_support_summary"] = str(controlled_reuse.get("interpretation_support_summary") or "").strip()

    continuation_items = [
        item
        for item in items
        if item is not focus_session and (item["results_ready"] or item["job_status"] in {"queued", "running"})
    ]
    archive_items = [item for item in items if item is not focus_session and item not in continuation_items]
    comparison_overview = build_session_comparison_overview(
        focus_session=focus_session,
        items=items,
    )

    if focus_session is not None:
        for item in continuation_items + archive_items:
            item["comparison_to_focus"] = compare_session_basis(
                focus_session=focus_session,
                candidate_session=item,
            )

    focus_candidates = []
    if isinstance(focus_session, dict):
        focus_candidates = focus_session.get("workspace_memory_candidates") or []
    workspace_feedback = build_workspace_feedback_summary(
        workspace_id=workspace_id,
        focus_session_id=(focus_session or {}).get("session_id") if isinstance(focus_session, dict) else "",
        focus_candidates=focus_candidates,
        review_events=workspace_reviews,
        session_labels=source_name_by_session_id,
    )

    return {
        "items": items,
        "focus_session": focus_session,
        "continuation_items": continuation_items,
        "archive_items": archive_items,
        "comparison_overview": comparison_overview,
        "workspace_feedback": workspace_feedback,
        "comparison_matrix": build_session_comparison_matrix(
            focus_session=focus_session,
            items=items,
        ),
        "counts": {
            "stored_sessions": len(items),
            "ready_sessions": sum(1 for item in items if item["results_ready"]),
            "measurement_sessions": sum(1 for item in items if item["rows_with_values"] > 0),
            "running_sessions": sum(1 for item in items if item["job_status"] in {"queued", "running"}),
        },
        "active_session_id": active_session_id or "",
        "latest_session_id": latest_session_id or "",
    }
