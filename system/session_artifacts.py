from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from system.contracts import ContractValidationError, normalize_loaded_decision_artifact
from system.db import resolve_session_artifact_path
from system.services.artifact_service import DATA_DIR, artifact_display_path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _json_file_payload(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"artifact_state": "missing", "payload": None, "source_path": "", "source_updated_at": "", "load_error": ""}
    source_path = artifact_display_path(path)
    source_updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    try:
        payload = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "artifact_state": "error",
            "payload": None,
            "source_path": source_path,
            "source_updated_at": source_updated_at,
            "load_error": str(exc),
        }
    return {
        "artifact_state": "ok",
        "payload": payload,
        "source_path": source_path,
        "source_updated_at": source_updated_at,
        "load_error": "",
    }


def load_result_payload(
    session_id: str | None = None,
    *,
    workspace_id: str | None = None,
    allow_global_fallback: bool = True,
) -> dict[str, Any]:
    path: Path | None = None
    if session_id:
        path = resolve_session_artifact_path(session_id, "result.json", workspace_id=workspace_id)
    elif allow_global_fallback:
        for candidate in (DATA_DIR / "uploads" / "latest_result.json", REPO_ROOT / "result.json"):
            if candidate.exists():
                path = candidate
                break
    return _json_file_payload(path)


def load_decision_artifact_payload(
    session_id: str | None = None,
    *,
    workspace_id: str | None = None,
    allow_global_fallback: bool = True,
) -> dict[str, Any]:
    default_payload = {
        "session_id": session_id or "public",
        "iteration": 0,
        "summary": {"top_k": 0, "candidate_count": 0, "risk_counts": {}, "top_experiment_value": 0.0},
        "top_experiments": [],
        "artifact_state": "missing",
        "load_error": "",
        "source_path": "",
        "source_updated_at": "",
    }

    candidate_paths: list[Path] = []
    if session_id:
        target = resolve_session_artifact_path(session_id, "decision_output.json", workspace_id=workspace_id)
        if target is not None:
            candidate_paths.append(target)
    elif allow_global_fallback:
        candidate_paths.extend([DATA_DIR / "decision_output.json", REPO_ROOT / "decision_output.json"])

    for path in candidate_paths:
        artifact = _json_file_payload(path)
        if artifact["artifact_state"] == "missing":
            continue
        if artifact["artifact_state"] == "error":
            return {
                **default_payload,
                "artifact_state": "error",
                "load_error": "Decision artifact could not be loaded.",
                "source_path": artifact["source_path"],
                "source_updated_at": artifact["source_updated_at"],
            }
        try:
            return normalize_loaded_decision_artifact(
                artifact["payload"] or {},
                session_id=session_id,
                generated_at=artifact["source_updated_at"],
                source_path=artifact["source_path"],
                source_updated_at=artifact["source_updated_at"],
                artifact_state="ok",
            )
        except ContractValidationError:
            return {
                **default_payload,
                "artifact_state": "error",
                "load_error": "Decision artifact failed contract validation.",
                "source_path": artifact["source_path"],
                "source_updated_at": artifact["source_updated_at"],
            }

    result_artifact = load_result_payload(
        session_id=session_id,
        workspace_id=workspace_id,
        allow_global_fallback=allow_global_fallback,
    )
    nested_payload = result_artifact.get("payload") if isinstance(result_artifact.get("payload"), dict) else {}
    decision_payload = nested_payload.get("decision_output") if isinstance(nested_payload, dict) else None
    if isinstance(decision_payload, dict):
        try:
            return normalize_loaded_decision_artifact(
                decision_payload,
                session_id=session_id,
                generated_at=result_artifact.get("source_updated_at"),
                source_path=f"{result_artifact.get('source_path')}#decision_output",
                source_updated_at=result_artifact.get("source_updated_at"),
                artifact_state="ok",
            )
        except ContractValidationError:
            return {
                **default_payload,
                "artifact_state": "error",
                "load_error": "Nested decision artifact inside result payload failed contract validation.",
                "source_path": f"{result_artifact.get('source_path')}#decision_output",
                "source_updated_at": result_artifact.get("source_updated_at") or "",
            }

    if session_id:
        return {
            **default_payload,
            "load_error": "No decision artifact has been saved for this session yet.",
        }
    return default_payload


def load_analysis_report_payload(
    session_id: str | None = None,
    *,
    workspace_id: str | None = None,
    allow_global_fallback: bool = True,
) -> dict[str, Any]:
    candidate_paths: list[Path] = []
    if session_id:
        target = resolve_session_artifact_path(session_id, "analysis_report.json", workspace_id=workspace_id)
        if target is not None:
            candidate_paths.append(target)
    elif allow_global_fallback:
        candidate_paths.append(DATA_DIR / "uploads" / "latest_result.json")

    for path in candidate_paths:
        artifact = _json_file_payload(path)
        if artifact["artifact_state"] != "ok":
            continue
        payload = artifact["payload"]
        if isinstance(payload, dict):
            report = payload.get("analysis_report", payload)
            if isinstance(report, dict):
                return {
                    **report,
                    "artifact_state": "ok",
                    "source_path": artifact["source_path"],
                    "source_updated_at": artifact["source_updated_at"],
                    "load_error": "",
                }

    result_artifact = load_result_payload(
        session_id=session_id,
        workspace_id=workspace_id,
        allow_global_fallback=allow_global_fallback,
    )
    result_payload = result_artifact.get("payload")
    if isinstance(result_payload, dict) and isinstance(result_payload.get("analysis_report"), dict):
        return {
            **result_payload["analysis_report"],
            "artifact_state": "ok",
            "source_path": f"{result_artifact.get('source_path')}#analysis_report",
            "source_updated_at": result_artifact.get("source_updated_at"),
            "load_error": "",
        }

    return {"artifact_state": "missing", "source_path": "", "source_updated_at": "", "load_error": ""}


def load_evaluation_summary_payload(
    session_id: str | None = None,
    *,
    workspace_id: str | None = None,
    allow_global_fallback: bool = True,
) -> dict[str, Any]:
    candidate_paths: list[Path] = []
    if session_id:
        target = resolve_session_artifact_path(session_id, "evaluation_summary.json", workspace_id=workspace_id)
        if target is not None:
            candidate_paths.append(target)
    elif allow_global_fallback:
        candidate_paths.extend([REPO_ROOT / "evaluation_summary.json", DATA_DIR / "evaluation_summary.json"])

    for path in candidate_paths:
        artifact = _json_file_payload(path)
        if artifact["artifact_state"] != "ok":
            continue
        payload = artifact["payload"]
        if isinstance(payload, dict):
            return {
                **payload,
                "artifact_state": "ok",
                "source_path": artifact["source_path"],
                "source_updated_at": artifact["source_updated_at"],
                "load_error": "",
            }

    return {"artifact_state": "missing", "source_path": "", "source_updated_at": "", "load_error": ""}
