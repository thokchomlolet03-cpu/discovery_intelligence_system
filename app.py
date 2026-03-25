from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from system.discovery_workbench import build_discovery_workbench
from system.dashboard_data import build_dashboard_context
from system.review_manager import (
    annotate_candidates_with_reviews,
    build_review_queue,
    persist_review_queue,
    record_review_action,
    record_review_actions,
)
from system.run_pipeline import run_pipeline
from system.upload_parser import (
    create_upload_session,
    infer_column_mapping,
    load_session_dataframe,
    load_session_metadata,
    session_dir,
    validation_summary,
)


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"


app = FastAPI(
    title="Discovery Intelligence System",
    description="Decision-support interface for prioritizing molecules worth testing next.",
    version="2.0.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _load_json(path: Path | None) -> Any:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text())


def session_artifact_path(session_id: str | None, filename: str) -> Path | None:
    if not session_id:
        return None
    target = session_dir(session_id) / filename
    return target if target.exists() else None


def load_decision_output(session_id: str | None = None) -> dict[str, Any]:
    candidate_paths = []
    if session_id:
        candidate_paths.append(session_dir(session_id) / "decision_output.json")
    candidate_paths.extend([DATA_DIR / "decision_output.json", BASE_DIR / "decision_output.json"])

    default_payload = {
        "iteration": 0,
        "summary": {"top_k": 0, "candidate_count": 0, "risk_counts": {}, "top_experiment_value": 0.0},
        "top_experiments": [],
        "artifact_state": "missing",
    }
    for path in candidate_paths:
        if path.exists():
            try:
                payload = _load_json(path) or dict(default_payload)
            except (json.JSONDecodeError, OSError) as exc:
                return {
                    **default_payload,
                    "artifact_state": "error",
                    "load_error": str(exc),
                    "source_path": str(path),
                }
            resolved = path.resolve()
            payload["source_path"] = str(resolved.relative_to(BASE_DIR)) if resolved.is_relative_to(BASE_DIR) else str(path)
            payload["source_updated_at"] = path.stat().st_mtime
            payload["artifact_state"] = "ok"
            return payload
    return default_payload


def load_analysis_report(session_id: str | None = None) -> dict[str, Any]:
    candidate_paths = []
    if session_id:
        candidate_paths.append(session_dir(session_id) / "analysis_report.json")
    candidate_paths.append(DATA_DIR / "uploads" / "latest_result.json")
    for path in candidate_paths:
        if path.exists():
            payload = _load_json(path)
            if isinstance(payload, dict):
                return payload.get("analysis_report", payload)
    return {}


def load_evaluation_summary(session_id: str | None = None) -> dict[str, Any]:
    candidate_paths = []
    if session_id:
        candidate_paths.append(session_dir(session_id) / "evaluation_summary.json")
    candidate_paths.extend([BASE_DIR / "evaluation_summary.json", DATA_DIR / "evaluation_summary.json"])
    for path in candidate_paths:
        if path.exists():
            try:
                payload = _load_json(path)
            except (json.JSONDecodeError, OSError):
                return {}
            return payload if isinstance(payload, dict) else {}
    return {}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    decision_output = load_decision_output()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "title": "Discovery Intelligence System",
            "active_page": "home",
            "decision_output": decision_output,
        },
    )


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "about.html",
        {
            "title": "About / Method / Limitations",
            "active_page": "about",
        },
    )


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "upload.html",
        {
            "title": "Upload / Analyze",
            "active_page": "upload",
        },
    )


@app.post("/api/upload/inspect")
async def inspect_upload(
    file: UploadFile = File(...),
    input_type: str = Form("molecules_to_screen_only"),
) -> JSONResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    try:
        session_payload = create_upload_session(payload, filename=file.filename, input_type=input_type)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not inspect CSV file: {exc}") from exc
    return JSONResponse(session_payload)


@app.post("/api/upload/validate")
async def validate_upload(payload: dict[str, Any] = Body(...)) -> JSONResponse:
    session_id = payload.get("session_id")
    mapping = payload.get("mapping") or {}
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")
    try:
        dataframe = load_session_dataframe(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    summary = validation_summary(dataframe, mapping)
    return JSONResponse({"session_id": session_id, "validation_summary": summary})


@app.post("/upload")
async def upload_dataset(
    file: UploadFile | None = File(None),
    session_id: str | None = Form(None),
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
    dataframe: pd.DataFrame
    source_name: str

    if session_id:
        try:
            dataframe = load_session_dataframe(session_id)
            metadata = load_session_metadata(session_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        source_name = str(metadata.get("filename") or (session_dir(session_id) / "raw_upload.csv").name)
    else:
        if file is None or not file.filename:
            raise HTTPException(status_code=400, detail="Provide a CSV file or an existing session_id.")
        payload = await file.read()
        if not payload:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
        try:
            dataframe = pd.read_csv(io.BytesIO(payload))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not parse CSV file: {exc}") from exc
        source_name = file.filename

    column_mapping = {
        "smiles": smiles_column,
        "biodegradable": biodegradable_column,
        "molecule_id": molecule_id_column,
        "source": source_column,
        "notes": notes_column,
    }
    if not column_mapping["smiles"]:
        column_mapping = infer_column_mapping(list(dataframe.columns))

    try:
        result = run_pipeline(
            dataframe,
            persist_artifacts=True,
            update_discovery_snapshot=False,
            source_name=source_name,
            analysis_options={
                "session_id": session_id,
                "input_type": input_type,
                "intent": intent,
                "scoring_mode": scoring_mode,
                "consent_learning": consent_choice == "allow_learning",
                "column_mapping": column_mapping,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {exc}") from exc

    return JSONResponse(result)


@app.get("/discovery", response_class=HTMLResponse)
async def discovery_page(
    request: Request,
    session_id: str | None = Query(default=None),
) -> HTMLResponse:
    decision_output = load_decision_output(session_id=session_id)
    candidates = annotate_candidates_with_reviews(decision_output.get("top_experiments", []), session_id=session_id)
    review_queue = build_review_queue(candidates, session_id=session_id)
    analysis_report = load_analysis_report(session_id=session_id)
    evaluation_summary = load_evaluation_summary(session_id=session_id)
    workbench = build_discovery_workbench(
        decision_output=decision_output,
        analysis_report=analysis_report,
        review_queue=review_queue,
        session_id=session_id,
        evaluation_summary=evaluation_summary,
        system_version=app.version,
    )

    return templates.TemplateResponse(
        request,
        "discovery.html",
        {
            "title": "Discovery Results",
            "active_page": "discovery",
            "session_id": session_id,
            "decision_output": decision_output,
            "analysis_report": analysis_report,
            "candidates": candidates,
            "review_queue": review_queue,
            "evaluation_summary": evaluation_summary,
            "workbench": workbench,
        },
    )


@app.post("/api/reviews")
async def create_review(payload: dict[str, Any] = Body(...)) -> JSONResponse:
    session_id = payload.get("session_id")
    items = payload.get("items")
    if isinstance(items, list):
        records = record_review_actions(items, session_id=session_id)
        if not records:
            raise HTTPException(status_code=400, detail="At least one review item with a smiles value is required.")

        decision_output = load_decision_output(session_id=session_id)
        candidates = annotate_candidates_with_reviews(decision_output.get("top_experiments", []), session_id=session_id)
        review_queue = persist_review_queue(candidates, session_id=session_id)
        return JSONResponse({"reviews": records, "review_queue": review_queue})

    smiles = payload.get("smiles")
    if not smiles:
        raise HTTPException(status_code=400, detail="smiles is required for review actions.")

    record = record_review_action(
        session_id=session_id,
        candidate_id=payload.get("candidate_id"),
        smiles=smiles,
        action=str(payload.get("action") or "later"),
        status=payload.get("status"),
        note=str(payload.get("note") or ""),
        reviewer=str(payload.get("reviewer") or "unassigned"),
    )

    decision_output = load_decision_output(session_id=session_id)
    candidates = annotate_candidates_with_reviews(decision_output.get("top_experiments", []), session_id=session_id)
    review_queue = persist_review_queue(candidates, session_id=session_id)
    return JSONResponse({"review": record, "review_queue": review_queue})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    session_id: str | None = Query(default=None),
) -> HTMLResponse:
    dashboard_context = build_dashboard_context(session_id=session_id)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "title": "Dashboard",
            "active_page": "dashboard",
            "dashboard": dashboard_context,
            "session_id": session_id,
        },
    )


@app.get("/api/discovery")
async def discovery_api(session_id: str | None = Query(default=None)) -> JSONResponse:
    return JSONResponse(load_decision_output(session_id=session_id))


@app.get("/api/discovery/download")
async def discovery_download(session_id: str | None = Query(default=None)) -> JSONResponse:
    payload = load_decision_output(session_id=session_id)
    target = f"decision_package_{session_id or 'public'}.json"
    return JSONResponse(
        payload,
        headers={"Content-Disposition": f'attachment; filename="{target}"'},
    )


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
