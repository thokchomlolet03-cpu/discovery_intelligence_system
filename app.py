from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from system.auth import (
    AuthContext,
    auth_service,
    build_template_auth_context,
    login_user,
    logout_user,
    get_session_cookie_name,
    get_optional_auth_context,
    get_session_middleware_options,
    require_auth_context,
    require_csrf,
    require_page_auth_context,
)
from system.billing import LIMIT_MAX_UPLOAD_ROWS, PlanEnforcementError, billing_service
from system.contracts import (
    ContractValidationError,
    validate_label_builder_config,
)
from system.db import ensure_database_ready, resolve_session_artifact_path
from system.db.repositories import SessionRepository
from system.discovery_workbench import build_discovery_workbench
from system.phase_manager import build_phase_manager_context
from system.payments import (
    PaddleConfigurationError,
    PaddleIntegrationError,
    PaddleWebhookVerificationError,
    paddle_billing_service,
)
from system.dashboard_data import build_dashboard_context
from system.job_manager import JobManager, JobNotFoundError
from system.review_manager import (
    annotate_candidates_with_reviews,
    build_review_queue,
    persist_review_queue,
    record_review_action,
    record_review_actions,
)
from system.services.governed_review_service import (
    SUBJECT_TYPE_BELIEF_STATE,
    SUBJECT_TYPE_CLAIM,
    SUBJECT_TYPE_CONTINUITY_CLUSTER,
    SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER,
    record_manual_subject_governed_review_action,
)
from system.services.governance_workflow_service import (
    build_governance_workbench,
    resolve_governance_subject_context,
)
from system.upload_parser import (
    create_upload_session,
    infer_column_mapping,
    load_session_dataframe,
    load_session_metadata,
    save_session_metadata,
    session_dir,
    validation_summary,
)
from system.services.ingestion import normalize_input_type, normalize_semantic_mapping
from system.services.active_session_comparison_service import build_active_session_comparison_context
from system.services.belief_update_service import (
    accept_belief_update,
    create_belief_update,
    reject_belief_update,
    supersede_belief_update,
)
from system.services.experiment_result_service import ingest_experiment_result
from system.services.scientific_session_truth_service import build_scientific_session_truth, persist_scientific_session_truth
from system.services.session_identity_service import build_session_identity
from system.services.status_semantics_service import build_status_semantics, persisted_status_snapshot
from system.services.support_quality_service import (
    REVIEW_REASON_APPROVED,
    REVIEW_REASON_CONTRADICTION,
    REVIEW_REASON_DOWNGRADED,
    REVIEW_REASON_QUARANTINED,
    REVIEW_REASON_SELECTIVE,
    REVIEW_REASON_STRONGER_TRUST_NEEDED,
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_BLOCKED,
    REVIEW_STATUS_DEFERRED,
    REVIEW_STATUS_DOWNGRADED,
    REVIEW_STATUS_QUARANTINED,
)
from system.services.workspace_feedback_service import annotate_candidates_with_workspace_memory, build_session_workspace_memory
from system.session_history import build_session_history_context
from system.session_artifacts import (
    load_analysis_report_payload,
    load_decision_artifact_payload,
    load_evaluation_summary_payload,
    load_result_payload,
    load_scientific_session_truth_payload,
)


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Discovery Intelligence System",
    description="Decision-support interface for prioritizing molecules worth testing next.",
    version="2.0.0",
)
app.add_middleware(SessionMiddleware, **get_session_middleware_options())
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
job_manager = JobManager()
session_repository = SessionRepository()
UPLOAD_ROLE_FIELDS = ("entity_id", "smiles", "value", "label", "target", "assay", "source", "notes")
ACTIVE_SESSION_ID_KEY = "active_session_id"
ACTIVE_SESSION_WORKSPACE_KEY = "active_session_workspace_id"


@app.on_event("startup")
async def startup_event() -> None:
    ensure_database_ready()
    auth_service.ensure_bootstrap_identity()


@app.exception_handler(PlanEnforcementError)
async def plan_enforcement_error_handler(request: Request, exc: PlanEnforcementError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


def _load_json(path: Path | None) -> Any:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text())


def _template_context(request: Request, **extra: Any) -> dict[str, Any]:
    auth = get_optional_auth_context(request)
    active_session_id = ""
    if auth is not None:
        stored_workspace = str(request.session.get(ACTIVE_SESSION_WORKSPACE_KEY) or "")
        stored_session_id = str(request.session.get(ACTIVE_SESSION_ID_KEY) or "")
        if stored_session_id and stored_workspace == auth.workspace_id:
            try:
                session_repository.get_session(stored_session_id, workspace_id=auth.workspace_id)
                active_session_id = stored_session_id
            except FileNotFoundError:
                request.session.pop(ACTIVE_SESSION_ID_KEY, None)
                request.session.pop(ACTIVE_SESSION_WORKSPACE_KEY, None)
    return {
        "request": request,
        **build_template_auth_context(request),
        "current_workspace_plan": billing_service.plan_summary(auth.workspace) if auth is not None else None,
        "active_session_id": active_session_id,
        "nav_sessions_url": "/sessions",
        "nav_discovery_url": f"/discovery?session_id={active_session_id}" if active_session_id else "/discovery",
        "nav_dashboard_url": f"/dashboard?session_id={active_session_id}" if active_session_id else "/dashboard",
        "nav_governance_url": f"/governance?session_id={active_session_id}" if active_session_id else "/governance",
        **extra,
    }


def _render_template(
    request: Request,
    template_name: str,
    *,
    status_code: int | None = None,
    **extra: Any,
) -> Response:
    context = _template_context(request, **extra)
    if status_code is None:
        return templates.TemplateResponse(template_name, context)
    return templates.TemplateResponse(template_name, context, status_code=status_code)


def _page_auth_or_redirect(request: Request) -> AuthContext | RedirectResponse:
    return require_page_auth_context(request)


def _workspace_plan_summary(auth: AuthContext) -> dict[str, Any]:
    return billing_service.plan_summary(auth.workspace)


def _require_workspace_owner(auth: AuthContext) -> None:
    if str(auth.membership.get("role") or "").strip().lower() != "owner":
        raise HTTPException(status_code=403, detail="Only workspace owners can manage billing for this workspace.")


def _billing_page_redirect(
    *,
    message: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    query: dict[str, str] = {}
    if message:
        query["message"] = message
    if error:
        query["error"] = error
    target = "/billing"
    if query:
        target = f"{target}?{urlencode(query)}"
    return RedirectResponse(url=target, status_code=303)


def _create_upload_session_with_plan(
    *,
    auth: AuthContext,
    payload: bytes,
    filename: str,
    input_type: str,
) -> dict[str, Any]:
    input_type = normalize_input_type(input_type)
    plan_summary = billing_service.ensure_upload_allowed(auth.workspace, creating_new_session=True)
    upload_rows_limit = plan_summary["limits"].get(LIMIT_MAX_UPLOAD_ROWS)
    try:
        session_payload = create_upload_session(
            payload,
            filename=filename,
            input_type=input_type,
            workspace_id=auth.workspace_id,
            created_by_user_id=auth.user_id,
            max_rows=upload_rows_limit,
        )
    except ValueError as exc:
        if upload_rows_limit is not None and str(exc).startswith("Uploads on this workspace plan are limited to "):
            raise PlanEnforcementError(
                code="upload_too_large",
                message=f"This workspace plan allows uploads up to {int(upload_rows_limit)} rows. Upgrade to analyze larger datasets.",
                status_code=413,
                plan_tier=str(auth.workspace.get("plan_tier") or "free"),
                effective_plan_tier=billing_service.effective_plan_tier(auth.workspace),
                limit=int(upload_rows_limit),
            ) from exc
        raise
    validation = session_payload.get("validation_summary") or {}
    billing_service.record_upload_session(
        workspace_id=auth.workspace_id,
        session_id=str(session_payload["session_id"]),
        filename=filename,
        input_type=input_type,
        row_count=int(validation.get("total_rows", 0) or 0),
    )
    return session_payload


def _workspace_fallback_path(session_id: str, filename: str, workspace_id: str | None) -> Path | None:
    if workspace_id is not None:
        return None
    return session_dir(session_id) / filename


def session_artifact_path(session_id: str | None, filename: str, workspace_id: str | None = None) -> Path | None:
    if not session_id:
        return None
    return resolve_session_artifact_path(
        session_id,
        filename,
        fallback_path=_workspace_fallback_path(session_id, filename, workspace_id),
        workspace_id=workspace_id,
    )


def load_decision_output(
    session_id: str | None = None,
    *,
    workspace_id: str | None = None,
    allow_global_fallback: bool = True,
) -> dict[str, Any]:
    return load_decision_artifact_payload(
        session_id=session_id,
        workspace_id=workspace_id,
        allow_global_fallback=allow_global_fallback,
    )


def load_analysis_report(
    session_id: str | None = None,
    *,
    workspace_id: str | None = None,
    allow_global_fallback: bool = True,
) -> dict[str, Any]:
    return load_analysis_report_payload(
        session_id=session_id,
        workspace_id=workspace_id,
        allow_global_fallback=allow_global_fallback,
    )


def load_evaluation_summary(
    session_id: str | None = None,
    *,
    workspace_id: str | None = None,
    allow_global_fallback: bool = True,
) -> dict[str, Any]:
    return load_evaluation_summary_payload(
        session_id=session_id,
        workspace_id=workspace_id,
        allow_global_fallback=allow_global_fallback,
    )


def _job_response_payload(job: dict[str, Any]) -> dict[str, Any]:
    return {
        **job,
        "status_semantics": persisted_status_snapshot(
            status=str(job.get("status") or ""),
            progress_stage=str(job.get("progress_stage") or ""),
            error=str(job.get("error") or ""),
            viewable_artifacts=bool((job.get("artifact_refs") or {}).get("result_json")),
        ),
        "job_url": f"/api/jobs/{job['job_id']}",
        "result_url": f"/api/jobs/{job['job_id']}/result",
        "discovery_url": f"/discovery?session_id={job['session_id']}",
        "dashboard_url": f"/dashboard?session_id={job['session_id']}",
    }


def _latest_job_payload_for_session(session_record: dict[str, Any] | None, workspace_id: str) -> dict[str, Any] | None:
    latest_job_id = str((session_record or {}).get("latest_job_id") or "").strip()
    if not latest_job_id:
        return None
    try:
        return _job_response_payload(job_manager.get_job(latest_job_id, workspace_id=workspace_id))
    except JobNotFoundError:
        return None


def _persist_active_session(request: Request, workspace_id: str, session_id: str | None) -> None:
    if not session_id:
        request.session.pop(ACTIVE_SESSION_ID_KEY, None)
        request.session.pop(ACTIVE_SESSION_WORKSPACE_KEY, None)
        return
    request.session[ACTIVE_SESSION_ID_KEY] = str(session_id)
    request.session[ACTIVE_SESSION_WORKSPACE_KEY] = str(workspace_id)


def _stored_active_session_id(request: Request, workspace_id: str) -> str | None:
    stored_session_id = str(request.session.get(ACTIVE_SESSION_ID_KEY) or "").strip()
    stored_workspace_id = str(request.session.get(ACTIVE_SESSION_WORKSPACE_KEY) or "").strip()
    if not stored_session_id or stored_workspace_id != workspace_id:
        return None
    try:
        session_repository.get_session(stored_session_id, workspace_id=workspace_id)
    except FileNotFoundError:
        request.session.pop(ACTIVE_SESSION_ID_KEY, None)
        request.session.pop(ACTIVE_SESSION_WORKSPACE_KEY, None)
        return None
    return stored_session_id


def _session_job_status(session_metadata: dict[str, Any] | None) -> str:
    metadata = (session_metadata or {}).get("summary_metadata") if isinstance(session_metadata, dict) else {}
    return str((metadata or {}).get("last_job_status") or "").strip().lower()


def _session_has_results(session_id: str, workspace_id: str) -> bool:
    for filename in ("decision_output.json", "result.json"):
        target = session_artifact_path(session_id, filename, workspace_id=workspace_id)
        if target is not None and target.exists():
            return True
    return False


def _latest_workspace_session(workspace_id: str) -> dict[str, Any] | None:
    sessions = session_repository.list_sessions(workspace_id, limit=25)
    for session in sessions:
        if _session_job_status(session) == "succeeded" and _session_has_results(session["session_id"], workspace_id):
            return session
    for session in sessions:
        if _session_has_results(session["session_id"], workspace_id):
            return session
    return sessions[0] if sessions else None


def _resolve_session_view(
    request: Request,
    auth: AuthContext,
    requested_session_id: str | None,
) -> dict[str, Any]:
    latest_session = _latest_workspace_session(auth.workspace_id)
    latest_session_id = str((latest_session or {}).get("session_id") or "")
    stored_session_id = _stored_active_session_id(request, auth.workspace_id)

    if requested_session_id:
        _ensure_session_access(requested_session_id, auth.workspace_id)
        resolved_session_id = requested_session_id
        selection_reason = "requested"
    else:
        resolved_session_id = stored_session_id or latest_session_id or None
        selection_reason = "active" if resolved_session_id and resolved_session_id == stored_session_id else "latest_completed"
        if not resolved_session_id:
            selection_reason = "none"

    session_record: dict[str, Any] | None = None
    if resolved_session_id:
        try:
            session_record = session_repository.get_session(resolved_session_id, workspace_id=auth.workspace_id)
            _persist_active_session(request, auth.workspace_id, resolved_session_id)
        except FileNotFoundError:
            resolved_session_id = None
            selection_reason = "none"

    return {
        "session_id": resolved_session_id,
        "requested_session_id": requested_session_id,
        "selection_reason": selection_reason,
        "latest_session_id": latest_session_id or None,
        "latest_session": latest_session,
        "session_record": session_record,
    }


def _persist_upload_session_state(
    *,
    session_id: str,
    auth: AuthContext,
    metadata: dict[str, Any],
    column_mapping: dict[str, str | None],
    label_builder: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    selected_mapping = normalize_semantic_mapping(column_mapping)
    payload = {
        **metadata,
        "session_id": session_id,
        "filename": str(metadata.get("filename") or (session_dir(session_id) / "raw_upload.csv").name),
        "input_type": normalize_input_type(metadata.get("input_type")),
        "file_type": str(validation.get("file_type") or metadata.get("file_type") or ""),
        "semantic_mode": str(validation.get("semantic_mode") or metadata.get("semantic_mode") or ""),
        "semantic_roles": metadata.get("semantic_roles") or metadata.get("inferred_mapping") or selected_mapping,
        "selected_mapping": selected_mapping,
        "label_builder_config": validate_label_builder_config(label_builder),
        "validation_summary": validation,
    }
    save_session_metadata(
        session_id,
        payload,
        workspace_id=auth.workspace_id,
        created_by_user_id=auth.user_id,
    )
    return load_session_metadata(session_id, workspace_id=auth.workspace_id)


def _load_upload_session_context(
    request: Request,
    auth: AuthContext,
    *,
    requested_session_id: str | None = None,
    fresh: bool = False,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if fresh:
        return {
            "session_id": None,
            "requested_session_id": requested_session_id,
            "selection_reason": "fresh",
            "latest_session_id": None,
            "latest_session": None,
            "session_record": None,
        }, None

    session_view = _resolve_session_view(request, auth, requested_session_id)
    session_id = str(session_view.get("session_id") or "").strip()
    if not session_id:
        return session_view, None

    try:
        metadata = load_session_metadata(session_id, workspace_id=auth.workspace_id)
    except FileNotFoundError:
        return session_view, None

    session_record = session_view.get("session_record") if isinstance(session_view, dict) else {}
    latest_job_id = str((session_record or {}).get("latest_job_id") or "").strip()
    latest_job = _latest_job_payload_for_session(session_record, auth.workspace_id) if latest_job_id else None

    result_payload = load_result_payload(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    restored_result = result_payload.get("payload") if isinstance(result_payload.get("payload"), dict) else None

    selected_mapping = metadata.get("selected_mapping") or metadata.get("semantic_roles") or metadata.get("inferred_mapping") or {}
    label_builder_config = metadata.get("label_builder_config") or metadata.get("label_builder_suggestion") or {}

    return session_view, {
        "session_id": session_id,
        "filename": str(metadata.get("filename") or ""),
        "input_type": normalize_input_type(metadata.get("input_type")),
        "file_type": str(metadata.get("file_type") or ""),
        "semantic_mode": str(metadata.get("semantic_mode") or ""),
        "columns": metadata.get("columns") or [],
        "preview_rows": metadata.get("preview_rows") or [],
        "measurement_columns": metadata.get("measurement_columns") or [],
        "selected_mapping": selected_mapping,
        "inferred_mapping": metadata.get("inferred_mapping") or {},
        "label_builder_suggestion": metadata.get("label_builder_suggestion") or label_builder_config,
        "label_builder_config": label_builder_config,
        "validation_summary": metadata.get("validation_summary") or {},
        "target_definition": metadata.get("target_definition") or {},
        "decision_intent": metadata.get("decision_intent") or "",
        "comparison_anchors": metadata.get("comparison_anchors") or {},
        "contract_versions": metadata.get("contract_versions") or {},
        "latest_job": latest_job,
        "result": restored_result,
    }


def _ensure_session_access(session_id: str | None, workspace_id: str) -> None:
    if not session_id:
        return
    try:
        session_repository.get_session(session_id, workspace_id=workspace_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requested session was not found.") from exc


MANUAL_GOVERNANCE_ACTIONS: dict[str, tuple[str, str]] = {
    "approved": (REVIEW_STATUS_APPROVED, REVIEW_REASON_APPROVED),
    "blocked": (REVIEW_STATUS_BLOCKED, REVIEW_REASON_CONTRADICTION),
    "deferred": (REVIEW_STATUS_DEFERRED, REVIEW_REASON_SELECTIVE),
    "downgraded": (REVIEW_STATUS_DOWNGRADED, REVIEW_REASON_DOWNGRADED),
    "quarantined": (REVIEW_STATUS_QUARANTINED, REVIEW_REASON_QUARANTINED),
    "reopened": (REVIEW_STATUS_DEFERRED, REVIEW_REASON_STRONGER_TRUST_NEEDED),
    "revised": (REVIEW_STATUS_DEFERRED, REVIEW_REASON_SELECTIVE),
}

MANUAL_GOVERNANCE_STATUS_CODES: dict[str, tuple[str, str]] = {
    "approved": (REVIEW_STATUS_APPROVED, REVIEW_REASON_APPROVED),
    "blocked": (REVIEW_STATUS_BLOCKED, REVIEW_REASON_CONTRADICTION),
    "deferred": (REVIEW_STATUS_DEFERRED, REVIEW_REASON_SELECTIVE),
    "downgraded": (REVIEW_STATUS_DOWNGRADED, REVIEW_REASON_DOWNGRADED),
    "quarantined": (REVIEW_STATUS_QUARANTINED, REVIEW_REASON_QUARANTINED),
}

MANUAL_GOVERNANCE_ACTION_LABELS: dict[str, str] = {
    "approved": "approved_by_reviewer",
    "blocked": "blocked_by_reviewer",
    "deferred": "deferred_by_reviewer",
    "downgraded": "downgraded_by_reviewer",
    "quarantined": "quarantined_by_reviewer",
    "reopened": "reopened_for_review",
    "revised": "revised_by_reviewer",
}

GOVERNANCE_LAYER_LABELS = {
    SUBJECT_TYPE_CLAIM: "Claim governance",
    SUBJECT_TYPE_BELIEF_STATE: "Belief-state governance",
    SUBJECT_TYPE_CONTINUITY_CLUSTER: "Continuity-cluster governance",
    SUBJECT_TYPE_SESSION_FAMILY_CARRYOVER: "Session-family carryover governance",
}


def _build_current_scientific_truth_for_session(
    *,
    session_id: str,
    workspace_id: str,
    created_by_user_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    session_record = session_repository.get_session(session_id, workspace_id=workspace_id)
    decision_output = load_decision_artifact_payload(
        session_id=session_id,
        workspace_id=workspace_id,
        allow_global_fallback=False,
    )
    analysis_report = load_analysis_report_payload(
        session_id=session_id,
        workspace_id=workspace_id,
        allow_global_fallback=False,
    )
    candidates = annotate_candidates_with_reviews(
        decision_output.get("top_experiments", []),
        session_id=session_id,
        workspace_id=workspace_id,
    )
    annotated_candidates = annotate_candidates_with_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=workspace_id,
    )
    workspace_memory = build_session_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=workspace_id,
    )
    review_queue = build_review_queue(
        candidates,
        session_id=session_id,
        workspace_id=workspace_id,
    )
    scientific_truth = build_scientific_session_truth(
        session_id=session_id,
        workspace_id=workspace_id,
        source_name=str(session_record.get("source_name") or ""),
        session_record=session_record,
        upload_metadata=session_record.get("upload_metadata") if isinstance(session_record.get("upload_metadata"), dict) else {},
        analysis_report=analysis_report,
        decision_payload={**decision_output, "top_experiments": annotated_candidates},
        review_queue=review_queue,
        workspace_memory=workspace_memory,
    )
    if created_by_user_id is not None:
        persist_scientific_session_truth(
            scientific_truth,
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            register_artifact=True,
        )
    return scientific_truth, session_record, decision_output, analysis_report


def _resolve_governed_review_subject_context(
    *,
    scientific_truth: dict[str, Any],
    subject_type: str,
    subject_id: str,
) -> dict[str, Any]:
    context = resolve_governance_subject_context(
        scientific_truth=scientific_truth,
        subject_type=subject_type,
        subject_id=subject_id,
    )
    return {
        **context,
        "layer_label": str(context.get("layer_label") or GOVERNANCE_LAYER_LABELS.get(subject_type, "Governance")).strip(),
        "derived_context": {
            "derived_review_status_label": str(context.get("derived_review_status_label") or context.get("effective_review_status_label") or "").strip(),
            "derived_review_status_summary": str(context.get("derived_review_status_summary") or context.get("effective_review_status_summary") or "").strip(),
            "derived_review_reason_label": str(context.get("derived_review_reason_label") or context.get("effective_review_reason_label") or "").strip(),
            "derived_review_reason_summary": str(context.get("derived_review_reason_summary") or context.get("effective_review_reason_summary") or "").strip(),
            "effective_review_origin_label": str(context.get("effective_review_origin_label") or "derived").strip(),
            "effective_review_status_label": str(context.get("effective_review_status_label") or "").strip(),
        },
    }


def _manual_governance_summaries(
    *,
    action_code: str,
    layer_label: str,
    derived_context: dict[str, Any],
    governance_note: str,
    reviewer_label: str,
    review_status_label: str,
    review_reason_label: str,
) -> tuple[str, str, str, str]:
    prior_status = str(derived_context.get("effective_review_status_label") or derived_context.get("derived_review_status_label") or "not recorded").strip()
    if action_code == "reopened":
        decision_summary = (
            f"{layer_label} is reopened for reconsideration under bounded human review."
            f" Current reviewed posture is reset to {review_status_label.lower()} while derived posture remains visible as {prior_status.lower() or 'not recorded'}."
        )
        review_reason_summary = (
            governance_note.strip()
            or f"{reviewer_label} reopened this layer for reconsideration rather than allowing the earlier broader-carryover boundary to stand unchanged."
        )
    elif action_code == "revised":
        decision_summary = (
            f"{layer_label} was manually revised to {review_status_label.lower()} under bounded human review."
            f" Derived posture suggested {prior_status.lower() or 'not recorded'}."
        )
        review_reason_summary = (
            governance_note.strip()
            or f"{reviewer_label} revised this layer after re-reading the derived posture and current carryover implications."
        )
    else:
        decision_summary = (
            f"{layer_label} is manually {action_code} under bounded human review."
            f" Derived posture suggested {prior_status.lower() or 'not recorded'}."
        )
        review_reason_summary = (
            governance_note.strip()
            or f"{reviewer_label} manually {action_code} this layer after reviewing the derived posture."
        )
    return review_status_label, review_reason_label, decision_summary, review_reason_summary


def _resolve_manual_governance_action(
    *,
    action_code: str,
    review_status_override: str,
) -> tuple[str, str, str]:
    normalized_override = str(review_status_override or "").strip().lower()
    if action_code == "revised" and normalized_override in MANUAL_GOVERNANCE_STATUS_CODES:
        review_status_label, review_reason_label = MANUAL_GOVERNANCE_STATUS_CODES[normalized_override]
    elif action_code == "reopened" and normalized_override in {"approved", "blocked", "downgraded", "quarantined"}:
        review_status_label, review_reason_label = MANUAL_GOVERNANCE_STATUS_CODES[normalized_override]
    else:
        review_status_label, review_reason_label = MANUAL_GOVERNANCE_ACTIONS[action_code]
    return (
        review_status_label,
        review_reason_label,
        MANUAL_GOVERNANCE_ACTION_LABELS.get(action_code, ""),
    )


def _resolve_column_mapping(
    *,
    session_id: str,
    workspace_id: str,
    metadata: dict[str, Any],
    submitted_mapping: dict[str, str | None],
) -> dict[str, str | None]:
    metadata_roles = metadata.get("semantic_roles") or metadata.get("inferred_mapping") or {}
    resolved = {
        field: submitted_mapping.get(field) or metadata_roles.get(field)
        for field in UPLOAD_ROLE_FIELDS
    }
    if resolved.get("smiles"):
        return resolved

    dataframe = load_session_dataframe(session_id, workspace_id=workspace_id)
    inferred_mapping = infer_column_mapping(list(dataframe.columns), dataframe=dataframe)
    return {
        field: resolved.get(field) or inferred_mapping.get(field)
        for field in UPLOAD_ROLE_FIELDS
    }


def _resolve_label_builder_config(
    *,
    value_column: str | None,
    enabled: str | bool | None,
    operator: str | None,
    threshold: str | float | None,
) -> dict[str, Any]:
    enabled_flag = enabled if isinstance(enabled, bool) else str(enabled or "").strip().lower() in {"1", "true", "yes", "on"}
    threshold_value: float | None
    if threshold in (None, ""):
        threshold_value = None
    else:
        threshold_value = float(threshold)
    return validate_label_builder_config(
        {
            "enabled": enabled_flag,
            "value_column": value_column or "",
            "operator": operator or ">=",
            "threshold": threshold_value,
        }
    )


async def _enqueue_analysis_job(
    *,
    request: Request,
    auth: AuthContext,
    file: UploadFile | None,
    session_id: str | None,
    input_type: str,
    intent: str,
    scoring_mode: str,
    consent_choice: str,
    value_column: str | None,
    label_column: str | None,
    entity_id_column: str | None,
    target_column: str | None,
    assay_column: str | None,
    smiles_column: str | None,
    biodegradable_column: str | None,
    molecule_id_column: str | None,
    source_column: str | None,
    notes_column: str | None,
    label_builder_enabled: str | bool | None,
    label_builder_operator: str | None,
    label_builder_threshold: str | float | None,
) -> JSONResponse:
    input_type = normalize_input_type(input_type)
    metadata: dict[str, Any]
    upload_rows = 0

    if session_id:
        try:
            metadata = load_session_metadata(session_id, workspace_id=auth.workspace_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        upload_rows = int(((metadata.get("validation_summary") or {}).get("total_rows")) or 0)
        billing_service.ensure_upload_allowed(auth.workspace, upload_rows=upload_rows, creating_new_session=False)
    else:
        if file is None or not file.filename:
            raise HTTPException(status_code=400, detail="Provide a supported data file or an existing session_id.")
        payload = await file.read()
        if not payload:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
        try:
            metadata = _create_upload_session_with_plan(
                auth=auth,
                payload=payload,
                filename=file.filename,
                input_type=input_type,
            )
        except PlanEnforcementError:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not inspect uploaded file: {exc}") from exc
        session_id = str(metadata["session_id"])
        upload_rows = int(((metadata.get("validation_summary") or {}).get("total_rows")) or 0)

    source_name = str(metadata.get("filename") or (session_dir(session_id) / "raw_upload.csv").name)
    billing_service.ensure_upload_allowed(auth.workspace, upload_rows=upload_rows, creating_new_session=False)
    billing_service.ensure_analysis_allowed(auth.workspace, intent=intent)
    submitted_mapping = {
        "entity_id": entity_id_column or molecule_id_column,
        "smiles": smiles_column,
        "value": value_column,
        "label": label_column or biodegradable_column,
        "target": target_column,
        "assay": assay_column,
        "source": source_column,
        "notes": notes_column,
    }

    try:
        column_mapping = _resolve_column_mapping(
            session_id=session_id,
            workspace_id=auth.workspace_id,
            metadata=metadata,
            submitted_mapping=submitted_mapping,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        label_builder = _resolve_label_builder_config(
            value_column=column_mapping.get("value"),
            enabled=label_builder_enabled,
            operator=label_builder_operator,
            threshold=label_builder_threshold,
        )
    except (ContractValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid label builder configuration: {exc}") from exc

    validation = metadata.get("validation_summary") or {}
    try:
        session_dataframe = load_session_dataframe(session_id, workspace_id=auth.workspace_id)
    except FileNotFoundError:
        session_dataframe = None
    if session_dataframe is not None:
        validation = validation_summary(
            session_dataframe,
            column_mapping,
            label_builder=label_builder,
            file_type=str(metadata.get("file_type") or ""),
            semantic_mode=str(metadata.get("semantic_mode") or ""),
        )
        metadata = _persist_upload_session_state(
            session_id=str(session_id),
            auth=auth,
            metadata=metadata,
            column_mapping=column_mapping,
            label_builder=label_builder,
            validation=validation,
        )

    job = job_manager.start_analysis_job(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        created_by_user_id=auth.user_id,
        source_name=source_name,
        analysis_options={
            "session_id": session_id,
            "workspace_id": auth.workspace_id,
            "input_type": input_type,
            "intent": intent,
            "scoring_mode": scoring_mode,
            "consent_learning": consent_choice == "allow_learning",
            "column_mapping": column_mapping,
            "label_builder": label_builder,
            "validation_context": metadata.get("validation_summary") or validation,
        },
    )
    _persist_active_session(request, auth.workspace_id, session_id)
    billing_service.record_analysis_job(
        workspace_id=auth.workspace_id,
        session_id=session_id,
        job_id=job["job_id"],
        intent=intent,
        input_type=input_type,
    )
    return JSONResponse(_job_response_payload(job), status_code=202)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    decision_output = load_decision_output()
    auth = get_optional_auth_context(request)
    home_session_history = {"items": [], "focus_session": None, "continuation_items": [], "archive_items": [], "counts": {}}
    session_view = {"session_id": None, "selection_reason": "none", "latest_session_id": None, "latest_session": None, "session_record": None}
    if auth is not None:
        session_view = _resolve_session_view(request, auth, None)
        sessions = session_repository.list_sessions(auth.workspace_id, limit=6)
        home_session_history = build_session_history_context(
            sessions,
            workspace_id=auth.workspace_id,
            active_session_id=str(session_view.get("session_id") or ""),
            latest_session_id=str(session_view.get("latest_session_id") or ""),
            job_fetcher=lambda job_id, workspace_id: job_manager.get_job(job_id, workspace_id=workspace_id),
        )
    return _render_template(
        request,
        "index.html",
        title="Discovery Intelligence System",
        active_page="home",
        decision_output=decision_output,
        home_session_history=home_session_history,
        session_view=session_view,
    )


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request) -> HTMLResponse:
    return _render_template(
        request,
        "about.html",
        title="About / Method / Limitations",
        active_page="about",
    )


@app.get("/roadmap", response_class=HTMLResponse)
async def roadmap_page(request: Request) -> Response:
    auth = _page_auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    return _render_template(
        request,
        "roadmap.html",
        title="Roadmap / Phase Manager",
        active_page="roadmap",
        roadmap=build_phase_manager_context(),
    )


@app.get("/api/roadmap")
async def roadmap_api(request: Request) -> JSONResponse:
    require_auth_context(request)
    return JSONResponse(build_phase_manager_context())


@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    next: str | None = Query(default=None),
) -> Response:
    if get_optional_auth_context(request) is not None:
        return RedirectResponse(url=next or "/upload", status_code=303)
    return _render_template(
        request,
        "login.html",
        title="Login",
        active_page="login",
        error="",
        next_target=next or "/upload",
    )


@app.post("/login")
async def login_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    next: str = Form("/upload"),
) -> Response:
    try:
        require_csrf(request, csrf_token)
    except HTTPException as exc:
        return _render_template(
            request,
            "login.html",
            status_code=exc.status_code,
            title="Login",
            active_page="login",
            error=exc.detail,
            next_target=next or "/upload",
        )
    try:
        auth = auth_service.authenticate(email=email, password=password)
    except ValueError as exc:
        return _render_template(
            request,
            "login.html",
            status_code=400,
            title="Login",
            active_page="login",
            error=str(exc),
            next_target=next or "/upload",
        )

    login_user(request, user_id=auth.user_id, workspace_id=auth.workspace_id)
    return RedirectResponse(url=next or "/upload", status_code=303)


@app.post("/logout")
async def logout_action(request: Request, csrf_token: str = Form(...)) -> RedirectResponse:
    require_csrf(request, csrf_token)
    logout_user(request)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(get_session_cookie_name())
    return response


@app.post("/workspaces/switch")
async def switch_workspace(
    request: Request,
    workspace_id: str = Form(...),
    csrf_token: str = Form(...),
    next: str = Form("/upload"),
) -> RedirectResponse:
    require_csrf(request, csrf_token)
    auth = require_auth_context(request)
    context = auth_service.resolve_context(user_id=auth.user_id, workspace_id=workspace_id)
    login_user(request, user_id=context.user_id, workspace_id=context.workspace_id)
    return RedirectResponse(url=next or "/upload", status_code=303)


@app.get("/billing", response_class=HTMLResponse)
async def billing_page(
    request: Request,
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> Response:
    auth = _page_auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    workspace_plan = _workspace_plan_summary(auth)
    is_owner = str(auth.membership.get("role") or "").strip().lower() == "owner"
    return _render_template(
        request,
        "billing.html",
        title="Billing",
        active_page="billing",
        workspace_plan=workspace_plan,
        billing_message=message or "",
        billing_error=error or "",
        billing_owner=is_owner,
        paddle_checkout_available=paddle_billing_service.checkout_available(),
        paddle_management_available=paddle_billing_service.management_available(),
    )


@app.post("/billing/checkout")
async def billing_checkout(request: Request, csrf_token: str = Form(...)) -> RedirectResponse:
    auth = require_auth_context(request)
    require_csrf(request, csrf_token)
    _require_workspace_owner(auth)
    try:
        checkout = paddle_billing_service.create_pro_checkout(workspace=auth.workspace, user=auth.user)
    except PaddleConfigurationError as exc:
        return _billing_page_redirect(error=str(exc))
    except PaddleIntegrationError as exc:
        return _billing_page_redirect(error=str(exc))
    return RedirectResponse(url=checkout["checkout_url"], status_code=303)


@app.post("/billing/manage")
async def billing_manage(request: Request, csrf_token: str = Form(...)) -> RedirectResponse:
    auth = require_auth_context(request)
    require_csrf(request, csrf_token)
    _require_workspace_owner(auth)
    try:
        session_payload = paddle_billing_service.create_management_session(workspace=auth.workspace)
    except PaddleConfigurationError as exc:
        return _billing_page_redirect(error=str(exc))
    except PaddleIntegrationError as exc:
        return _billing_page_redirect(error=str(exc))
    return RedirectResponse(url=session_payload["management_url"], status_code=303)


@app.post("/api/webhooks/paddle")
async def paddle_webhook(request: Request) -> JSONResponse:
    raw_body = await request.body()
    signature = request.headers.get("Paddle-Signature", "")
    try:
        result = paddle_billing_service.handle_webhook(raw_body, signature)
    except PaddleWebhookVerificationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except PaddleConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PaddleIntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(result)


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(
    request: Request,
    session_id: str | None = Query(default=None),
    fresh: bool = Query(default=False),
) -> Response:
    auth = _page_auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    workspace_plan = _workspace_plan_summary(auth)
    session_view, upload_session_context = _load_upload_session_context(
        request,
        auth,
        requested_session_id=session_id,
        fresh=fresh,
    )
    status_semantics = build_status_semantics(
        session_record=session_view.get("session_record") if isinstance(session_view, dict) else {},
        upload_metadata=upload_session_context or {},
        decision_payload=(upload_session_context or {}).get("result") or {},
        current_job=(upload_session_context or {}).get("latest_job") if isinstance(upload_session_context, dict) else None,
    )
    session_identity = build_session_identity(
        session_record=session_view.get("session_record") if isinstance(session_view, dict) else {},
        upload_metadata=upload_session_context or {},
        decision_payload=(upload_session_context or {}).get("result") or {},
        current_job=(upload_session_context or {}).get("latest_job") if isinstance(upload_session_context, dict) else None,
    )
    return _render_template(
        request,
        "upload.html",
        title="Upload / Analyze",
        active_page="upload",
        workspace_plan=workspace_plan,
        upload_session_context=upload_session_context,
        session_identity=session_identity,
        status_semantics=status_semantics,
        session_view=session_view,
        restored_upload_session=bool(upload_session_context),
    )


@app.get("/sessions", response_class=HTMLResponse)
async def sessions_page(
    request: Request,
    session_id: str | None = Query(default=None),
) -> Response:
    auth = _page_auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    workspace_plan = _workspace_plan_summary(auth)
    session_view = _resolve_session_view(request, auth, session_id)
    session_history = build_session_history_context(
        session_repository.list_sessions(auth.workspace_id, limit=100),
        workspace_id=auth.workspace_id,
        active_session_id=str(session_view.get("session_id") or ""),
        latest_session_id=str(session_view.get("latest_session_id") or ""),
        job_fetcher=lambda job_id, workspace_id: job_manager.get_job(job_id, workspace_id=workspace_id),
    )
    governance_workbench = build_governance_workbench(
        session_history=session_history,
        selected_session_id=str(session_view.get("session_id") or ""),
    )
    return _render_template(
        request,
        "sessions.html",
        title="Sessions",
        active_page="sessions",
        workspace_plan=workspace_plan,
        session_view=session_view,
        session_history=session_history,
        governance_workbench=governance_workbench,
        session_identity=(session_history.get("focus_session") or {}).get("session_identity"),
        status_semantics=(session_history.get("focus_session") or {}).get("status_semantics"),
    )


@app.get("/governance", response_class=HTMLResponse)
async def governance_page(
    request: Request,
    session_id: str | None = Query(default=None),
    item_id: str | None = Query(default=None),
) -> Response:
    auth = _page_auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    workspace_plan = _workspace_plan_summary(auth)
    session_view = _resolve_session_view(request, auth, session_id)
    session_history = build_session_history_context(
        session_repository.list_sessions(auth.workspace_id, limit=100),
        workspace_id=auth.workspace_id,
        active_session_id=str(session_view.get("session_id") or ""),
        latest_session_id=str(session_view.get("latest_session_id") or ""),
        job_fetcher=lambda job_id, workspace_id: job_manager.get_job(job_id, workspace_id=workspace_id),
    )
    governance_workbench = build_governance_workbench(
        session_history=session_history,
        selected_item_id=str(item_id or ""),
        selected_session_id=str(session_view.get("session_id") or ""),
    )
    return _render_template(
        request,
        "governance.html",
        title="Governance",
        active_page="governance",
        workspace_plan=workspace_plan,
        session_view=session_view,
        session_history=session_history,
        governance_workbench=governance_workbench,
        session_identity=(governance_workbench.get("selected_session") or {}).get("session_identity"),
        status_semantics=(governance_workbench.get("selected_session") or {}).get("status_semantics"),
    )


@app.post("/api/upload/inspect")
async def inspect_upload(
    request: Request,
    file: UploadFile = File(...),
    csrf_token: str = Form(...),
    input_type: str = Form("measurement_dataset"),
) -> JSONResponse:
    auth = require_auth_context(request)
    require_csrf(request, csrf_token)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Select a supported data file before inspection.")

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    try:
        session_payload = _create_upload_session_with_plan(
            auth=auth,
            payload=payload,
            filename=file.filename,
            input_type=input_type,
        )
    except PlanEnforcementError:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not inspect uploaded file: {exc}") from exc
    _persist_active_session(request, auth.workspace_id, str(session_payload.get("session_id") or ""))
    return JSONResponse(session_payload)


@app.post("/api/upload/validate")
async def validate_upload(request: Request, payload: dict[str, Any] = Body(...)) -> JSONResponse:
    auth = require_auth_context(request)
    require_csrf(request)
    session_id = payload.get("session_id")
    mapping = payload.get("mapping") or {}
    submitted_label_builder = payload.get("label_builder") or {"enabled": False}
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")
    try:
        dataframe = load_session_dataframe(session_id, workspace_id=auth.workspace_id)
        metadata = load_session_metadata(session_id, workspace_id=auth.workspace_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        label_builder = _resolve_label_builder_config(
            value_column=(mapping or {}).get("value"),
            enabled=submitted_label_builder.get("enabled"),
            operator=submitted_label_builder.get("operator"),
            threshold=submitted_label_builder.get("threshold"),
        )
    except (ContractValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid label builder configuration: {exc}") from exc

    summary = validation_summary(
        dataframe,
        mapping,
        label_builder=label_builder,
        file_type=str(metadata.get("file_type") or ""),
        semantic_mode=str(metadata.get("semantic_mode") or ""),
    )
    _persist_upload_session_state(
        session_id=str(session_id),
        auth=auth,
        metadata=metadata,
        column_mapping=mapping,
        label_builder=label_builder,
        validation=summary,
    )
    _persist_active_session(request, auth.workspace_id, str(session_id))
    refreshed = load_session_metadata(str(session_id), workspace_id=auth.workspace_id)
    return JSONResponse(
        {
            "session_id": session_id,
            "validation_summary": summary,
            "target_definition": refreshed.get("target_definition") or {},
            "comparison_anchors": refreshed.get("comparison_anchors") or {},
            "contract_versions": refreshed.get("contract_versions") or {},
        }
    )


@app.post("/api/jobs/analysis")
@app.post("/upload")
async def upload_dataset(
    request: Request,
    file: UploadFile | None = File(None),
    session_id: str | None = Form(None),
    csrf_token: str = Form(...),
    input_type: str = Form("measurement_dataset"),
    intent: str = Form("rank_uploaded_molecules"),
    scoring_mode: str = Form("balanced"),
    consent_choice: str = Form("private"),
    entity_id_column: str | None = Form(None),
    smiles_column: str | None = Form(None),
    value_column: str | None = Form(None),
    label_column: str | None = Form(None),
    target_column: str | None = Form(None),
    assay_column: str | None = Form(None),
    biodegradable_column: str | None = Form(None),
    molecule_id_column: str | None = Form(None),
    source_column: str | None = Form(None),
    notes_column: str | None = Form(None),
    label_builder_enabled: str | None = Form(None),
    label_builder_operator: str | None = Form(None),
    label_builder_threshold: str | None = Form(None),
) -> JSONResponse:
    auth = require_auth_context(request)
    require_csrf(request, csrf_token)
    return await _enqueue_analysis_job(
        request=request,
        auth=auth,
        file=file,
        session_id=session_id,
        input_type=input_type,
        intent=intent,
        scoring_mode=scoring_mode,
        consent_choice=consent_choice,
        value_column=value_column,
        label_column=label_column,
        entity_id_column=entity_id_column,
        target_column=target_column,
        assay_column=assay_column,
        smiles_column=smiles_column,
        biodegradable_column=biodegradable_column,
        molecule_id_column=molecule_id_column,
        source_column=source_column,
        notes_column=notes_column,
        label_builder_enabled=label_builder_enabled,
        label_builder_operator=label_builder_operator,
        label_builder_threshold=label_builder_threshold,
    )


@app.get("/discovery", response_class=HTMLResponse)
async def discovery_page(
    request: Request,
    session_id: str | None = Query(default=None),
) -> Response:
    auth = _page_auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    session_view = _resolve_session_view(request, auth, session_id)
    effective_session_id = session_view["session_id"]
    workspace_plan = _workspace_plan_summary(auth)
    workspace_sessions = session_repository.list_sessions(auth.workspace_id, limit=25)

    decision_output = load_decision_output(
        session_id=effective_session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    candidates = annotate_candidates_with_reviews(
        decision_output.get("top_experiments", []),
        session_id=effective_session_id,
        workspace_id=auth.workspace_id,
    )
    candidates = annotate_candidates_with_workspace_memory(
        candidates,
        session_id=effective_session_id,
        workspace_id=auth.workspace_id,
    )
    review_queue = build_review_queue(candidates, session_id=effective_session_id, workspace_id=auth.workspace_id)
    analysis_report = load_analysis_report(
        session_id=effective_session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    evaluation_summary = load_evaluation_summary(
        session_id=effective_session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    workbench_decision_output = {**decision_output, "top_experiments": candidates}
    scientific_session_truth = load_scientific_session_truth_payload(
        session_id=effective_session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    if str(scientific_session_truth.get("artifact_state") or "") != "ok":
        workspace_memory = build_session_workspace_memory(
            candidates,
            session_id=effective_session_id,
            workspace_id=auth.workspace_id,
        )
        scientific_session_truth = build_scientific_session_truth(
            session_id=effective_session_id,
            workspace_id=auth.workspace_id,
            source_name=str((session_view.get("session_record") or {}).get("source_name") or ""),
            session_record=session_view.get("session_record") if isinstance(session_view, dict) else {},
            upload_metadata=(session_view.get("session_record") or {}).get("upload_metadata") if isinstance((session_view.get("session_record") or {}).get("upload_metadata"), dict) else {},
            analysis_report=analysis_report,
            decision_payload=workbench_decision_output,
            review_queue=review_queue,
            workspace_memory=workspace_memory,
        )
    workbench = build_discovery_workbench(
        decision_output=workbench_decision_output,
        analysis_report=analysis_report,
        review_queue=review_queue,
        session_id=effective_session_id,
        evaluation_summary=evaluation_summary,
        system_version=app.version,
        scientific_session_truth=scientific_session_truth,
    )
    session_identity = build_session_identity(
        session_record=session_view.get("session_record") if isinstance(session_view, dict) else {},
        analysis_report=analysis_report,
        decision_payload=decision_output,
        current_job=_latest_job_payload_for_session(session_view.get("session_record"), auth.workspace_id)
        if isinstance(session_view, dict)
        else None,
        state_kind=str((workbench.get("state") or {}).get("kind") or ""),
    )
    status_semantics = build_status_semantics(
        session_record=session_view.get("session_record") if isinstance(session_view, dict) else {},
        analysis_report=analysis_report,
        decision_payload=decision_output,
        current_job=_latest_job_payload_for_session(session_view.get("session_record"), auth.workspace_id)
        if isinstance(session_view, dict)
        else None,
    )
    active_session_comparison = build_active_session_comparison_context(
        current_session_record=session_view.get("session_record") if isinstance(session_view, dict) else {},
        current_analysis_report=analysis_report,
        current_decision_payload=decision_output,
        workspace_sessions=workspace_sessions,
        workspace_id=auth.workspace_id,
    )
    governance_session_history = build_session_history_context(
        workspace_sessions,
        workspace_id=auth.workspace_id,
        active_session_id=effective_session_id,
        latest_session_id=str(session_view.get("latest_session_id") or ""),
        job_fetcher=lambda job_id, workspace_id: job_manager.get_job(job_id, workspace_id=workspace_id),
    )
    governance_workbench = build_governance_workbench(
        session_history=governance_session_history,
        selected_session_id=effective_session_id,
    )

    return _render_template(
        request,
        "discovery.html",
        title="Discovery Results",
        active_page="discovery",
        session_id=effective_session_id,
        session_view=session_view,
        decision_output=decision_output,
        analysis_report=analysis_report,
        candidates=candidates,
        review_queue=review_queue,
        evaluation_summary=evaluation_summary,
        workbench=workbench,
        session_identity=session_identity,
        status_semantics=status_semantics,
        active_session_comparison=active_session_comparison,
        governance_workbench=governance_workbench,
        workspace_plan=workspace_plan,
    )


@app.post("/api/reviews")
async def create_review(request: Request, payload: dict[str, Any] = Body(...)) -> JSONResponse:
    auth = require_auth_context(request)
    require_csrf(request)
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required for review actions.")
    _persist_active_session(request, auth.workspace_id, str(session_id))
    items = payload.get("items")
    reviewer_name = str(auth.user.get("display_name") or auth.user.get("email") or "unassigned").strip() or "unassigned"
    if isinstance(items, list):
        _ensure_session_access(session_id, auth.workspace_id)
        for item in items:
            item_session_id = str(item.get("session_id") or session_id).strip()
            if item_session_id != session_id:
                raise HTTPException(status_code=400, detail="Bulk review items must match the requested session_id.")
        try:
            normalized_items = [
                {
                    **item,
                    "session_id": session_id,
                    "reviewer": item.get("reviewer") or reviewer_name,
                    "actor_user_id": item.get("actor_user_id") or auth.user_id,
                }
                for item in items
            ]
            records = record_review_actions(
                normalized_items,
                session_id=session_id,
                workspace_id=auth.workspace_id,
                actor_user_id=auth.user_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not records:
            raise HTTPException(status_code=400, detail="At least one review item with a smiles value is required.")

        decision_output = load_decision_output(
            session_id=session_id,
            workspace_id=auth.workspace_id,
            allow_global_fallback=False,
        )
        candidates = annotate_candidates_with_reviews(
            decision_output.get("top_experiments", []),
            session_id=session_id,
            workspace_id=auth.workspace_id,
        )
        review_queue = persist_review_queue(
            candidates,
            session_id=session_id,
            workspace_id=auth.workspace_id,
            created_by_user_id=auth.user_id,
        )
        analysis_report = load_analysis_report(
            session_id=session_id,
            workspace_id=auth.workspace_id,
            allow_global_fallback=False,
        )
        session_record = session_repository.get_session(session_id, workspace_id=auth.workspace_id)
        annotated_candidates = annotate_candidates_with_workspace_memory(
            candidates,
            session_id=session_id,
            workspace_id=auth.workspace_id,
        )
        workspace_memory = build_session_workspace_memory(
            candidates,
            session_id=session_id,
            workspace_id=auth.workspace_id,
        )
        updated_truth = build_scientific_session_truth(
            session_id=session_id,
            workspace_id=auth.workspace_id,
            source_name=str(session_record.get("source_name") or ""),
            session_record=session_record,
            upload_metadata=session_record.get("upload_metadata") if isinstance(session_record.get("upload_metadata"), dict) else {},
            analysis_report=analysis_report,
            decision_payload={**decision_output, "top_experiments": annotated_candidates},
            review_queue=review_queue,
            workspace_memory=workspace_memory,
        )
        persist_scientific_session_truth(
            updated_truth,
            session_id=session_id,
            workspace_id=auth.workspace_id,
            created_by_user_id=auth.user_id,
            register_artifact=True,
        )
        return JSONResponse({"reviews": records, "review_queue": review_queue})

    smiles = payload.get("smiles")
    if not smiles:
        raise HTTPException(status_code=400, detail="smiles is required for review actions.")
    _ensure_session_access(session_id, auth.workspace_id)

    try:
        record = record_review_action(
            session_id=session_id,
            workspace_id=auth.workspace_id,
            candidate_id=payload.get("candidate_id"),
            smiles=smiles,
            action=str(payload.get("action") or "later"),
            status=payload.get("status"),
            note=str(payload.get("note") or ""),
            reviewer=str(payload.get("reviewer") or reviewer_name),
            actor_user_id=auth.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    decision_output = load_decision_output(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    candidates = annotate_candidates_with_reviews(
        decision_output.get("top_experiments", []),
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    review_queue = persist_review_queue(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
        created_by_user_id=auth.user_id,
    )
    analysis_report = load_analysis_report(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    session_record = session_repository.get_session(session_id, workspace_id=auth.workspace_id)
    annotated_candidates = annotate_candidates_with_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    workspace_memory = build_session_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    updated_truth = build_scientific_session_truth(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        source_name=str(session_record.get("source_name") or ""),
        session_record=session_record,
        upload_metadata=session_record.get("upload_metadata") if isinstance(session_record.get("upload_metadata"), dict) else {},
        analysis_report=analysis_report,
        decision_payload={**decision_output, "top_experiments": annotated_candidates},
        review_queue=review_queue,
        workspace_memory=workspace_memory,
    )
    persist_scientific_session_truth(
        updated_truth,
        session_id=session_id,
        workspace_id=auth.workspace_id,
        created_by_user_id=auth.user_id,
        register_artifact=True,
    )
    return JSONResponse({"review": record, "review_queue": review_queue})


@app.post("/experiment-results")
async def create_experiment_result_action(
    request: Request,
    session_id: str = Form(...),
    csrf_token: str = Form(...),
    source_experiment_request_id: str | None = Form(None),
    source_claim_id: str | None = Form(None),
    candidate_id: str | None = Form(None),
    observed_value: str | None = Form(None),
    observed_label: str | None = Form(None),
    measurement_unit: str | None = Form(None),
    assay_context: str | None = Form(None),
    result_quality: str = Form("provisional"),
    notes: str | None = Form(None),
    next: str = Form("/discovery"),
) -> RedirectResponse:
    auth = require_auth_context(request)
    require_csrf(request, csrf_token)
    if not str(observed_value or "").strip() and not str(observed_label or "").strip():
        raise HTTPException(status_code=400, detail="An observed value or observed label is required to record a result.")
    _ensure_session_access(session_id, auth.workspace_id)
    _persist_active_session(request, auth.workspace_id, session_id)

    ingested_by = str(auth.user.get("display_name") or auth.user.get("email") or "scientist").strip() or "scientist"
    try:
        ingest_experiment_result(
            session_id=session_id,
            workspace_id=auth.workspace_id,
            source_experiment_request_id=str(source_experiment_request_id or "").strip(),
            source_claim_id=str(source_claim_id or "").strip(),
            candidate_id=str(candidate_id or "").strip(),
            observed_value=observed_value,
            observed_label=str(observed_label or "").strip(),
            measurement_unit=str(measurement_unit or "").strip(),
            assay_context=str(assay_context or "").strip(),
            result_quality=str(result_quality or "provisional").strip(),
            ingested_by=ingested_by,
            ingested_by_user_id=auth.user_id,
            notes=str(notes or "").strip(),
        )
    except (ContractValidationError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    decision_output = load_decision_output(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    candidates = annotate_candidates_with_reviews(
        decision_output.get("top_experiments", []),
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    review_queue = persist_review_queue(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
        created_by_user_id=auth.user_id,
    )
    analysis_report = load_analysis_report(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    session_record = session_repository.get_session(session_id, workspace_id=auth.workspace_id)
    annotated_candidates = annotate_candidates_with_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    workspace_memory = build_session_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    updated_truth = build_scientific_session_truth(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        source_name=str(session_record.get("source_name") or ""),
        session_record=session_record,
        upload_metadata=session_record.get("upload_metadata") if isinstance(session_record.get("upload_metadata"), dict) else {},
        analysis_report=analysis_report,
        decision_payload={**decision_output, "top_experiments": annotated_candidates},
        review_queue=review_queue,
        workspace_memory=workspace_memory,
    )
    persist_scientific_session_truth(
        updated_truth,
        session_id=session_id,
        workspace_id=auth.workspace_id,
        created_by_user_id=auth.user_id,
        register_artifact=True,
    )
    target = str(next or "").strip() or f"/discovery?session_id={session_id}"
    return RedirectResponse(url=target, status_code=303)


@app.post("/belief-updates")
async def create_belief_update_action(
    request: Request,
    session_id: str = Form(...),
    csrf_token: str = Form(...),
    claim_id: str | None = Form(None),
    experiment_result_id: str | None = Form(None),
    next: str = Form("/discovery"),
) -> RedirectResponse:
    auth = require_auth_context(request)
    require_csrf(request, csrf_token)
    _ensure_session_access(session_id, auth.workspace_id)
    _persist_active_session(request, auth.workspace_id, session_id)

    created_by = str(auth.user.get("display_name") or auth.user.get("email") or "scientist").strip() or "scientist"
    try:
        create_belief_update(
            session_id=session_id,
            workspace_id=auth.workspace_id,
            claim_id=str(claim_id or "").strip(),
            experiment_result_id=str(experiment_result_id or "").strip(),
            created_by=created_by,
            created_by_user_id=auth.user_id,
        )
    except (ContractValidationError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    decision_output = load_decision_output(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    candidates = annotate_candidates_with_reviews(
        decision_output.get("top_experiments", []),
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    review_queue = persist_review_queue(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
        created_by_user_id=auth.user_id,
    )
    analysis_report = load_analysis_report(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    session_record = session_repository.get_session(session_id, workspace_id=auth.workspace_id)
    annotated_candidates = annotate_candidates_with_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    workspace_memory = build_session_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    updated_truth = build_scientific_session_truth(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        source_name=str(session_record.get("source_name") or ""),
        session_record=session_record,
        upload_metadata=session_record.get("upload_metadata") if isinstance(session_record.get("upload_metadata"), dict) else {},
        analysis_report=analysis_report,
        decision_payload={**decision_output, "top_experiments": annotated_candidates},
        review_queue=review_queue,
        workspace_memory=workspace_memory,
    )
    persist_scientific_session_truth(
        updated_truth,
        session_id=session_id,
        workspace_id=auth.workspace_id,
        created_by_user_id=auth.user_id,
        register_artifact=True,
    )
    target = str(next or "").strip() or f"/discovery?session_id={session_id}"
    return RedirectResponse(url=target, status_code=303)


@app.post("/belief-updates/{belief_update_id}/accept")
async def accept_belief_update_action(
    request: Request,
    belief_update_id: str,
    session_id: str = Form(...),
    csrf_token: str = Form(...),
    governance_note: str | None = Form(None),
    next: str = Form("/discovery"),
) -> RedirectResponse:
    auth = require_auth_context(request)
    require_csrf(request, csrf_token)
    _ensure_session_access(session_id, auth.workspace_id)
    _persist_active_session(request, auth.workspace_id, session_id)

    reviewed_by = str(auth.user.get("display_name") or auth.user.get("email") or "scientist").strip() or "scientist"
    try:
        accept_belief_update(
            belief_update_id=belief_update_id,
            workspace_id=auth.workspace_id,
            session_id=session_id,
            reviewed_by=reviewed_by,
            reviewed_by_user_id=auth.user_id,
            governance_note=str(governance_note or "").strip(),
        )
    except (ContractValidationError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session_record = session_repository.get_session(session_id, workspace_id=auth.workspace_id)
    decision_output = load_decision_output(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    candidates = annotate_candidates_with_reviews(
        decision_output.get("top_experiments", []),
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    review_queue = persist_review_queue(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
        created_by_user_id=auth.user_id,
    )
    analysis_report = load_analysis_report(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    annotated_candidates = annotate_candidates_with_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    workspace_memory = build_session_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    updated_truth = build_scientific_session_truth(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        source_name=str(session_record.get("source_name") or ""),
        session_record=session_record,
        upload_metadata=session_record.get("upload_metadata") if isinstance(session_record.get("upload_metadata"), dict) else {},
        analysis_report=analysis_report,
        decision_payload={**decision_output, "top_experiments": annotated_candidates},
        review_queue=review_queue,
        workspace_memory=workspace_memory,
    )
    persist_scientific_session_truth(
        updated_truth,
        session_id=session_id,
        workspace_id=auth.workspace_id,
        created_by_user_id=auth.user_id,
        register_artifact=True,
    )
    target = str(next or "").strip() or f"/discovery?session_id={session_id}"
    return RedirectResponse(url=target, status_code=303)


@app.post("/belief-updates/{belief_update_id}/reject")
async def reject_belief_update_action(
    request: Request,
    belief_update_id: str,
    session_id: str = Form(...),
    csrf_token: str = Form(...),
    governance_note: str | None = Form(None),
    next: str = Form("/discovery"),
) -> RedirectResponse:
    auth = require_auth_context(request)
    require_csrf(request, csrf_token)
    _ensure_session_access(session_id, auth.workspace_id)
    _persist_active_session(request, auth.workspace_id, session_id)

    reviewed_by = str(auth.user.get("display_name") or auth.user.get("email") or "scientist").strip() or "scientist"
    try:
        reject_belief_update(
            belief_update_id=belief_update_id,
            workspace_id=auth.workspace_id,
            session_id=session_id,
            reviewed_by=reviewed_by,
            reviewed_by_user_id=auth.user_id,
            governance_note=str(governance_note or "").strip(),
        )
    except (ContractValidationError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session_record = session_repository.get_session(session_id, workspace_id=auth.workspace_id)
    decision_output = load_decision_output(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    candidates = annotate_candidates_with_reviews(
        decision_output.get("top_experiments", []),
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    review_queue = persist_review_queue(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
        created_by_user_id=auth.user_id,
    )
    analysis_report = load_analysis_report(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    annotated_candidates = annotate_candidates_with_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    workspace_memory = build_session_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    updated_truth = build_scientific_session_truth(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        source_name=str(session_record.get("source_name") or ""),
        session_record=session_record,
        upload_metadata=session_record.get("upload_metadata") if isinstance(session_record.get("upload_metadata"), dict) else {},
        analysis_report=analysis_report,
        decision_payload={**decision_output, "top_experiments": annotated_candidates},
        review_queue=review_queue,
        workspace_memory=workspace_memory,
    )
    persist_scientific_session_truth(
        updated_truth,
        session_id=session_id,
        workspace_id=auth.workspace_id,
        created_by_user_id=auth.user_id,
        register_artifact=True,
    )
    target = str(next or "").strip() or f"/discovery?session_id={session_id}"
    return RedirectResponse(url=target, status_code=303)


@app.post("/belief-updates/{belief_update_id}/supersede")
async def supersede_belief_update_action(
    request: Request,
    belief_update_id: str,
    session_id: str = Form(...),
    csrf_token: str = Form(...),
    supersede_reason: str | None = Form(None),
    next: str = Form("/discovery"),
) -> RedirectResponse:
    auth = require_auth_context(request)
    require_csrf(request, csrf_token)
    _ensure_session_access(session_id, auth.workspace_id)
    _persist_active_session(request, auth.workspace_id, session_id)

    reviewed_by = str(auth.user.get("display_name") or auth.user.get("email") or "scientist").strip() or "scientist"
    try:
        supersede_belief_update(
            belief_update_id=belief_update_id,
            workspace_id=auth.workspace_id,
            session_id=session_id,
            reviewed_by=reviewed_by,
            reviewed_by_user_id=auth.user_id,
            supersede_reason=str(supersede_reason or "").strip(),
        )
    except (ContractValidationError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session_record = session_repository.get_session(session_id, workspace_id=auth.workspace_id)
    decision_output = load_decision_output(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    candidates = annotate_candidates_with_reviews(
        decision_output.get("top_experiments", []),
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    review_queue = persist_review_queue(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
        created_by_user_id=auth.user_id,
    )
    analysis_report = load_analysis_report(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    annotated_candidates = annotate_candidates_with_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    workspace_memory = build_session_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=auth.workspace_id,
    )
    updated_truth = build_scientific_session_truth(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        source_name=str(session_record.get("source_name") or ""),
        session_record=session_record,
        upload_metadata=session_record.get("upload_metadata") if isinstance(session_record.get("upload_metadata"), dict) else {},
        analysis_report=analysis_report,
        decision_payload={**decision_output, "top_experiments": annotated_candidates},
        review_queue=review_queue,
        workspace_memory=workspace_memory,
    )
    persist_scientific_session_truth(
        updated_truth,
        session_id=session_id,
        workspace_id=auth.workspace_id,
        created_by_user_id=auth.user_id,
        register_artifact=True,
    )
    target = str(next or "").strip() or f"/discovery?session_id={session_id}"
    return RedirectResponse(url=target, status_code=303)


@app.post("/governed-review/manual-action")
async def record_manual_governed_review_action(
    request: Request,
    session_id: str = Form(...),
    subject_type: str = Form(...),
    subject_id: str = Form(...),
    manual_action: str = Form(...),
    review_status_override: str | None = Form(None),
    csrf_token: str = Form(...),
    governance_note: str | None = Form(None),
    next: str = Form("/discovery"),
) -> RedirectResponse:
    auth = require_auth_context(request)
    require_csrf(request, csrf_token)
    _ensure_session_access(session_id, auth.workspace_id)
    _persist_active_session(request, auth.workspace_id, session_id)

    action_code = str(manual_action or "").strip().lower()
    if action_code not in MANUAL_GOVERNANCE_ACTIONS:
        raise HTTPException(status_code=400, detail="Unsupported manual governance action.")

    reviewed_by = str(auth.user.get("display_name") or auth.user.get("email") or "scientist").strip() or "scientist"
    try:
        scientific_truth, _, _, _ = _build_current_scientific_truth_for_session(
            session_id=session_id,
            workspace_id=auth.workspace_id,
        )
        subject_context = _resolve_governed_review_subject_context(
            scientific_truth=scientific_truth,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        review_status_label, review_reason_label, manual_action_label = _resolve_manual_governance_action(
            action_code=action_code,
            review_status_override=str(review_status_override or ""),
        )
        review_status_label, review_reason_label, decision_summary, review_reason_summary = _manual_governance_summaries(
            action_code=action_code,
            layer_label=str(subject_context.get("layer_label") or "Governance"),
            derived_context=subject_context.get("derived_context") if isinstance(subject_context.get("derived_context"), dict) else {},
            governance_note=str(governance_note or "").strip(),
            reviewer_label=reviewed_by,
            review_status_label=review_status_label,
            review_reason_label=review_reason_label,
        )
        record_manual_subject_governed_review_action(
            {
                "workspace_id": auth.workspace_id,
                "session_id": session_id,
                "subject_type": subject_type,
                "subject_id": subject_id,
                "target_key": subject_context.get("target_key", ""),
                "candidate_id": subject_context.get("candidate_id", ""),
                "source_class_label": subject_context.get("source_class_label", ""),
                "provenance_confidence_label": subject_context.get("provenance_confidence_label", ""),
                "trust_tier_label": subject_context.get("trust_tier_label", ""),
                "review_status_label": review_status_label,
                "review_reason_label": review_reason_label,
                "review_reason_summary": review_reason_summary,
                "promotion_gate_status_label": subject_context.get("promotion_gate_status_label", ""),
                "promotion_block_reason_label": subject_context.get("promotion_block_reason_label", ""),
                "manual_action_label": manual_action_label,
                "decision_summary": decision_summary,
                "recorded_by": reviewed_by,
                "actor_user_id": auth.user_id,
                "reviewer_label": reviewed_by,
                "reviewer_user_id": auth.user_id,
                "derived_context": subject_context.get("derived_context", {}),
                "metadata": {
                    "governance_note": str(governance_note or "").strip(),
                    "review_status_override": str(review_status_override or "").strip(),
                    "review_action_code": action_code,
                    "subject_layer_label": subject_context.get("layer_label", ""),
                    "derived_context": subject_context.get("derived_context", {}),
                },
            }
        )
        _build_current_scientific_truth_for_session(
            session_id=session_id,
            workspace_id=auth.workspace_id,
            created_by_user_id=auth.user_id,
        )
    except (ContractValidationError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    target = str(next or "").strip() or f"/discovery?session_id={session_id}"
    return RedirectResponse(url=target, status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    session_id: str | None = Query(default=None),
) -> Response:
    auth = _page_auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    session_view = _resolve_session_view(request, auth, session_id)
    workspace_plan = _workspace_plan_summary(auth)
    workspace_sessions = session_repository.list_sessions(auth.workspace_id, limit=25)
    dashboard_context = build_dashboard_context(session_id=session_view["session_id"], workspace_id=auth.workspace_id)
    session_identity = build_session_identity(
        session_record=session_view.get("session_record") if isinstance(session_view, dict) else {},
        analysis_report=dashboard_context.get("analysis_report") if isinstance(dashboard_context, dict) else {},
        decision_payload={"summary": {"candidate_count": len(dashboard_context.get("top_candidates") or [])}, **dashboard_context}
        if isinstance(dashboard_context, dict)
        else {},
        current_job=_latest_job_payload_for_session(session_view.get("session_record"), auth.workspace_id)
        if isinstance(session_view, dict)
        else None,
        state_kind=str((dashboard_context.get("state") or {}).get("kind") or ""),
    )
    status_semantics = build_status_semantics(
        session_record=session_view.get("session_record") if isinstance(session_view, dict) else {},
        analysis_report=dashboard_context.get("analysis_report") if isinstance(dashboard_context, dict) else {},
        decision_payload={
            "artifact_state": dashboard_context.get("artifact_state"),
            "summary": {"candidate_count": len(dashboard_context.get("top_candidates") or [])},
            "source_path": dashboard_context.get("source_path"),
        }
        if isinstance(dashboard_context, dict)
        else {},
        current_job=_latest_job_payload_for_session(session_view.get("session_record"), auth.workspace_id)
        if isinstance(session_view, dict)
        else None,
    )
    active_session_comparison = build_active_session_comparison_context(
        current_session_record=session_view.get("session_record") if isinstance(session_view, dict) else {},
        current_analysis_report=dashboard_context.get("analysis_report") if isinstance(dashboard_context, dict) else {},
        current_decision_payload={
            "artifact_state": dashboard_context.get("artifact_state"),
            "summary": {"candidate_count": len(dashboard_context.get("top_candidates") or [])},
            "source_path": dashboard_context.get("source_path"),
            "target_definition": dashboard_context.get("target_definition") or {},
            "modeling_mode": dashboard_context.get("modeling_mode") or "",
            "decision_intent": dashboard_context.get("decision_intent") or "",
            "run_contract": dashboard_context.get("run_contract") or {},
            "comparison_anchors": dashboard_context.get("comparison_anchors") or {},
        }
        if isinstance(dashboard_context, dict)
        else {},
        workspace_sessions=workspace_sessions,
        workspace_id=auth.workspace_id,
    )
    governance_session_history = build_session_history_context(
        workspace_sessions,
        workspace_id=auth.workspace_id,
        active_session_id=str(session_view.get("session_id") or ""),
        latest_session_id=str(session_view.get("latest_session_id") or ""),
        job_fetcher=lambda job_id, workspace_id: job_manager.get_job(job_id, workspace_id=workspace_id),
    )
    governance_workbench = build_governance_workbench(
        session_history=governance_session_history,
        selected_session_id=str(session_view.get("session_id") or ""),
    )
    return _render_template(
        request,
        "dashboard.html",
        title="Dashboard",
        active_page="dashboard",
        dashboard=dashboard_context,
        session_id=session_view["session_id"],
        session_identity=session_identity,
        status_semantics=status_semantics,
        active_session_comparison=active_session_comparison,
        governance_workbench=governance_workbench,
        session_view=session_view,
        workspace_plan=workspace_plan,
    )


@app.get("/api/discovery")
async def discovery_api(request: Request, session_id: str | None = Query(default=None)) -> JSONResponse:
    auth = require_auth_context(request)
    _ensure_session_access(session_id, auth.workspace_id)
    return JSONResponse(
        load_decision_output(
            session_id=session_id,
            workspace_id=auth.workspace_id,
            allow_global_fallback=False,
        )
    )


@app.get("/api/discovery/download")
async def discovery_download(request: Request, session_id: str | None = Query(default=None)) -> JSONResponse:
    auth = require_auth_context(request)
    _ensure_session_access(session_id, auth.workspace_id)
    billing_service.ensure_export_allowed(auth.workspace)
    payload = load_decision_output(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    billing_service.record_export(workspace_id=auth.workspace_id, session_id=session_id)
    target = f"decision_package_{session_id or 'workspace'}.json"
    return JSONResponse(
        payload,
        headers={"Content-Disposition": f'attachment; filename="{target}"'},
    )


@app.get("/api/jobs/{job_id}")
async def get_job_status(request: Request, job_id: str) -> JSONResponse:
    auth = require_auth_context(request)
    try:
        job = job_manager.get_job(job_id, workspace_id=auth.workspace_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requested job was not found.") from exc
    return JSONResponse(_job_response_payload(job))


@app.get("/api/jobs/{job_id}/result")
async def get_job_result(request: Request, job_id: str) -> JSONResponse:
    auth = require_auth_context(request)
    try:
        job = job_manager.get_job(job_id, workspace_id=auth.workspace_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requested job was not found.") from exc

    if job["status"] != "succeeded":
        raise HTTPException(status_code=409, detail=f"Job '{job_id}' is not complete yet.")

    result_path = job_manager.artifact_repository.get_latest_artifact_path(
        artifact_type="result_json",
        session_id=job["session_id"],
        job_id=job_id,
        workspace_id=auth.workspace_id,
    )
    if result_path is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' completed without a result artifact.")

    try:
        payload = _load_json(result_path)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not load result artifact for job %s: %s", job_id, exc)
        raise HTTPException(status_code=500, detail="Could not load the completed job result artifact.") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail=f"Job '{job_id}' result artifact has an invalid shape.")
    return JSONResponse(payload)


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
