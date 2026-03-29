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
from system.contracts import ContractValidationError, normalize_loaded_decision_artifact
from system.db import ensure_database_ready, resolve_session_artifact_path
from system.db.repositories import SessionRepository
from system.discovery_workbench import build_discovery_workbench
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
from system.upload_parser import (
    create_upload_session,
    infer_column_mapping,
    load_session_dataframe,
    load_session_metadata,
    session_dir,
    validation_summary,
)
from system.services.artifact_service import artifact_display_path


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
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
    return {
        "request": request,
        **build_template_auth_context(request),
        "current_workspace_plan": billing_service.plan_summary(auth.workspace) if auth is not None else None,
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
    candidate_paths = []
    if session_id:
        target = session_artifact_path(session_id, "decision_output.json", workspace_id=workspace_id)
        if target is not None:
            candidate_paths.append(target)
    elif allow_global_fallback:
        candidate_paths.extend([DATA_DIR / "decision_output.json", BASE_DIR / "decision_output.json"])

    default_payload = {
        "session_id": session_id or "public",
        "iteration": 0,
        "summary": {"top_k": 0, "candidate_count": 0, "risk_counts": {}, "top_experiment_value": 0.0},
        "top_experiments": [],
        "artifact_state": "missing",
    }
    for path in candidate_paths:
        if path.exists():
            try:
                payload = _load_json(path) or {}
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not load decision artifact from %s: %s", path, exc)
                return {
                    **default_payload,
                    "artifact_state": "error",
                    "load_error": "Decision artifact could not be loaded.",
                    "source_path": artifact_display_path(path),
                }
            source_path = artifact_display_path(path)
            source_updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
            try:
                return normalize_loaded_decision_artifact(
                    payload,
                    session_id=session_id,
                    generated_at=source_updated_at,
                    source_path=source_path,
                    source_updated_at=source_updated_at,
                    artifact_state="ok",
                )
            except ContractValidationError as exc:
                logger.warning("Decision artifact contract validation failed for %s: %s", path, exc)
                return {
                    **default_payload,
                    "artifact_state": "error",
                    "load_error": "Decision artifact failed contract validation.",
                    "source_path": source_path,
                    "source_updated_at": source_updated_at,
                }
    return default_payload


def load_analysis_report(
    session_id: str | None = None,
    *,
    workspace_id: str | None = None,
    allow_global_fallback: bool = True,
) -> dict[str, Any]:
    candidate_paths = []
    if session_id:
        target = session_artifact_path(session_id, "analysis_report.json", workspace_id=workspace_id)
        if target is not None:
            candidate_paths.append(target)
    elif allow_global_fallback:
        candidate_paths.append(DATA_DIR / "uploads" / "latest_result.json")
    for path in candidate_paths:
        if path.exists():
            payload = _load_json(path)
            if isinstance(payload, dict):
                return payload.get("analysis_report", payload)
    return {}


def load_evaluation_summary(
    session_id: str | None = None,
    *,
    workspace_id: str | None = None,
    allow_global_fallback: bool = True,
) -> dict[str, Any]:
    candidate_paths = []
    if session_id:
        target = session_artifact_path(session_id, "evaluation_summary.json", workspace_id=workspace_id)
        if target is not None:
            candidate_paths.append(target)
    elif allow_global_fallback:
        candidate_paths.extend([BASE_DIR / "evaluation_summary.json", DATA_DIR / "evaluation_summary.json"])
    for path in candidate_paths:
        if path.exists():
            try:
                payload = _load_json(path)
            except (json.JSONDecodeError, OSError):
                return {}
            return payload if isinstance(payload, dict) else {}
    return {}


def _job_response_payload(job: dict[str, Any]) -> dict[str, Any]:
    return {
        **job,
        "job_url": f"/api/jobs/{job['job_id']}",
        "result_url": f"/api/jobs/{job['job_id']}/result",
        "discovery_url": f"/discovery?session_id={job['session_id']}",
        "dashboard_url": f"/dashboard?session_id={job['session_id']}",
    }


def _ensure_session_access(session_id: str | None, workspace_id: str) -> None:
    if not session_id:
        return
    try:
        session_repository.get_session(session_id, workspace_id=workspace_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requested session was not found.") from exc


def _resolve_column_mapping(
    *,
    session_id: str,
    workspace_id: str,
    metadata: dict[str, Any],
    submitted_mapping: dict[str, str | None],
) -> dict[str, str | None]:
    resolved = {
        field: submitted_mapping.get(field) or (metadata.get("inferred_mapping") or {}).get(field)
        for field in ("smiles", "biodegradable", "molecule_id", "source", "notes")
    }
    if resolved.get("smiles"):
        return resolved

    dataframe = load_session_dataframe(session_id, workspace_id=workspace_id)
    inferred_mapping = infer_column_mapping(list(dataframe.columns))
    return {
        field: resolved.get(field) or inferred_mapping.get(field)
        for field in ("smiles", "biodegradable", "molecule_id", "source", "notes")
    }


async def _enqueue_analysis_job(
    *,
    auth: AuthContext,
    file: UploadFile | None,
    session_id: str | None,
    input_type: str,
    intent: str,
    scoring_mode: str,
    consent_choice: str,
    smiles_column: str | None,
    biodegradable_column: str | None,
    molecule_id_column: str | None,
    source_column: str | None,
    notes_column: str | None,
) -> JSONResponse:
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
            raise HTTPException(status_code=400, detail="Provide a CSV file or an existing session_id.")
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
            raise HTTPException(status_code=400, detail=f"Could not inspect CSV file: {exc}") from exc
        session_id = str(metadata["session_id"])
        upload_rows = int(((metadata.get("validation_summary") or {}).get("total_rows")) or 0)

    source_name = str(metadata.get("filename") or (session_dir(session_id) / "raw_upload.csv").name)
    billing_service.ensure_upload_allowed(auth.workspace, upload_rows=upload_rows, creating_new_session=False)
    billing_service.ensure_analysis_allowed(auth.workspace, intent=intent)
    submitted_mapping = {
        "smiles": smiles_column,
        "biodegradable": biodegradable_column,
        "molecule_id": molecule_id_column,
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
        },
    )
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
    return _render_template(
        request,
        "index.html",
        title="Discovery Intelligence System",
        active_page="home",
        decision_output=decision_output,
    )


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request) -> HTMLResponse:
    return _render_template(
        request,
        "about.html",
        title="About / Method / Limitations",
        active_page="about",
    )


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
async def upload_page(request: Request) -> Response:
    auth = _page_auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    workspace_plan = _workspace_plan_summary(auth)
    return _render_template(
        request,
        "upload.html",
        title="Upload / Analyze",
        active_page="upload",
        workspace_plan=workspace_plan,
    )


@app.post("/api/upload/inspect")
async def inspect_upload(
    request: Request,
    file: UploadFile = File(...),
    csrf_token: str = Form(...),
    input_type: str = Form("molecules_to_screen_only"),
) -> JSONResponse:
    auth = require_auth_context(request)
    require_csrf(request, csrf_token)
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

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
        raise HTTPException(status_code=400, detail=f"Could not inspect CSV file: {exc}") from exc
    return JSONResponse(session_payload)


@app.post("/api/upload/validate")
async def validate_upload(request: Request, payload: dict[str, Any] = Body(...)) -> JSONResponse:
    auth = require_auth_context(request)
    require_csrf(request)
    session_id = payload.get("session_id")
    mapping = payload.get("mapping") or {}
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")
    try:
        dataframe = load_session_dataframe(session_id, workspace_id=auth.workspace_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    summary = validation_summary(dataframe, mapping)
    return JSONResponse({"session_id": session_id, "validation_summary": summary})


@app.post("/api/jobs/analysis")
@app.post("/upload")
async def upload_dataset(
    request: Request,
    file: UploadFile | None = File(None),
    session_id: str | None = Form(None),
    csrf_token: str = Form(...),
    input_type: str = Form("molecules_to_screen_only"),
    intent: str = Form("rank_uploaded_molecules"),
    scoring_mode: str = Form("balanced"),
    consent_choice: str = Form("private"),
    smiles_column: str | None = Form(None),
    biodegradable_column: str | None = Form(None),
    molecule_id_column: str | None = Form(None),
    source_column: str | None = Form(None),
    notes_column: str | None = Form(None),
) -> JSONResponse:
    auth = require_auth_context(request)
    require_csrf(request, csrf_token)
    return await _enqueue_analysis_job(
        auth=auth,
        file=file,
        session_id=session_id,
        input_type=input_type,
        intent=intent,
        scoring_mode=scoring_mode,
        consent_choice=consent_choice,
        smiles_column=smiles_column,
        biodegradable_column=biodegradable_column,
        molecule_id_column=molecule_id_column,
        source_column=source_column,
        notes_column=notes_column,
    )


@app.get("/discovery", response_class=HTMLResponse)
async def discovery_page(
    request: Request,
    session_id: str | None = Query(default=None),
) -> Response:
    auth = _page_auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    _ensure_session_access(session_id, auth.workspace_id)
    workspace_plan = _workspace_plan_summary(auth)

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
    review_queue = build_review_queue(candidates, session_id=session_id, workspace_id=auth.workspace_id)
    analysis_report = load_analysis_report(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    evaluation_summary = load_evaluation_summary(
        session_id=session_id,
        workspace_id=auth.workspace_id,
        allow_global_fallback=False,
    )
    workbench_decision_output = {**decision_output, "top_experiments": candidates}
    workbench = build_discovery_workbench(
        decision_output=workbench_decision_output,
        analysis_report=analysis_report,
        review_queue=review_queue,
        session_id=session_id,
        evaluation_summary=evaluation_summary,
        system_version=app.version,
    )

    return _render_template(
        request,
        "discovery.html",
        title="Discovery Results",
        active_page="discovery",
        session_id=session_id,
        decision_output=decision_output,
        analysis_report=analysis_report,
        candidates=candidates,
        review_queue=review_queue,
        evaluation_summary=evaluation_summary,
        workbench=workbench,
        workspace_plan=workspace_plan,
    )


@app.post("/api/reviews")
async def create_review(request: Request, payload: dict[str, Any] = Body(...)) -> JSONResponse:
    auth = require_auth_context(request)
    require_csrf(request)
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required for review actions.")
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
    return JSONResponse({"review": record, "review_queue": review_queue})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    session_id: str | None = Query(default=None),
) -> Response:
    auth = _page_auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    _ensure_session_access(session_id, auth.workspace_id)
    workspace_plan = _workspace_plan_summary(auth)
    dashboard_context = build_dashboard_context(session_id=session_id, workspace_id=auth.workspace_id)
    return _render_template(
        request,
        "dashboard.html",
        title="Dashboard",
        active_page="dashboard",
        dashboard=dashboard_context,
        session_id=session_id,
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
