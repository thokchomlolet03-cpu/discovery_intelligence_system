from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from system.contracts import ContractValidationError, normalize_loaded_decision_artifact, validate_scientific_session_truth
from system.db.repositories import SessionRepository
from system.db import resolve_session_artifact_path
from system.services.artifact_service import DATA_DIR, artifact_display_path
from system.upload_parser import load_session_metadata


REPO_ROOT = Path(__file__).resolve().parent.parent
session_repository = SessionRepository()


def _session_measurement_summary(session_id: str | None, workspace_id: str | None) -> dict[str, Any]:
    if not session_id:
        return {}
    try:
        metadata = load_session_metadata(session_id, workspace_id=workspace_id)
    except FileNotFoundError:
        return {}
    validation = metadata.get("validation_summary") if isinstance(metadata, dict) else {}
    if not isinstance(validation, dict):
        return {}
    return {
        "semantic_mode": str(validation.get("semantic_mode") or "").strip(),
        "file_type": str(validation.get("file_type") or "").strip(),
        "value_column": str(validation.get("value_column") or "").strip(),
        "rows_with_values": int(validation.get("rows_with_values", 0) or 0),
        "rows_without_values": int(validation.get("rows_without_values", 0) or 0),
        "rows_with_labels": int(validation.get("rows_with_labels", 0) or 0),
        "rows_without_labels": int(validation.get("rows_without_labels", 0) or 0),
        "label_source": str(validation.get("label_source") or "").strip(),
    }


def _session_target_definition(session_id: str | None, workspace_id: str | None) -> dict[str, Any]:
    if not session_id:
        return {}
    try:
        metadata = load_session_metadata(session_id, workspace_id=workspace_id)
    except FileNotFoundError:
        return {}
    payload = metadata.get("target_definition") if isinstance(metadata, dict) else {}
    return payload if isinstance(payload, dict) else {}


def _backfill_measurement_summary(
    report: dict[str, Any],
    *,
    session_id: str | None,
    workspace_id: str | None,
) -> dict[str, Any]:
    session_measurement = _session_measurement_summary(session_id, workspace_id)
    if not session_measurement:
        return report

    existing = report.get("measurement_summary") if isinstance(report.get("measurement_summary"), dict) else {}
    merged = dict(existing)
    updated = False

    for field in ("semantic_mode", "file_type", "value_column", "label_source"):
        if not str(merged.get(field) or "").strip() and session_measurement.get(field):
            merged[field] = session_measurement[field]
            updated = True

    for field in ("rows_with_values", "rows_without_values", "rows_with_labels", "rows_without_labels"):
        existing_value = int(merged.get(field, 0) or 0)
        session_value = int(session_measurement.get(field, 0) or 0)
        if existing_value <= 0 and session_value > 0:
            merged[field] = session_value
            updated = True

    if updated or (not existing and merged):
        report = dict(report)
        report["measurement_summary"] = merged
    return report


def _backfill_target_definition(
    payload: dict[str, Any],
    *,
    session_id: str | None,
    workspace_id: str | None,
) -> dict[str, Any]:
    session_target = _session_target_definition(session_id, workspace_id)
    if not session_target:
        return payload
    if isinstance(payload.get("target_definition"), dict) and payload.get("target_definition"):
        return payload
    enriched = dict(payload)
    enriched["target_definition"] = session_target
    return enriched


def _summary_metadata_scientific_truth(session_id: str | None, workspace_id: str | None) -> dict[str, Any]:
    if not session_id:
        return {}
    try:
        session = session_repository.get_session(session_id, workspace_id=workspace_id)
    except FileNotFoundError:
        return {}
    summary_metadata = session.get("summary_metadata") if isinstance(session.get("summary_metadata"), dict) else {}
    payload = summary_metadata.get("scientific_session_truth") if isinstance(summary_metadata.get("scientific_session_truth"), dict) else {}
    return payload if isinstance(payload, dict) else {}


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
                _backfill_target_definition(artifact["payload"] or {}, session_id=session_id, workspace_id=workspace_id),
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
                _backfill_target_definition(decision_payload, session_id=session_id, workspace_id=workspace_id),
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
                report = _backfill_measurement_summary(
                    report,
                    session_id=session_id,
                    workspace_id=workspace_id,
                )
                report = _backfill_target_definition(report, session_id=session_id, workspace_id=workspace_id)
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
        report = _backfill_measurement_summary(
            result_payload["analysis_report"],
            session_id=session_id,
            workspace_id=workspace_id,
        )
        report = _backfill_target_definition(report, session_id=session_id, workspace_id=workspace_id)
        return {
            **report,
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


def load_scientific_session_truth_payload(
    session_id: str | None = None,
    *,
    workspace_id: str | None = None,
    allow_global_fallback: bool = True,
) -> dict[str, Any]:
    candidate_paths: list[Path] = []
    if session_id:
        target = resolve_session_artifact_path(session_id, "scientific_session_truth.json", workspace_id=workspace_id)
        if target is not None:
            candidate_paths.append(target)
    elif allow_global_fallback:
        candidate_paths.append(DATA_DIR / "scientific_session_truth.json")

    for path in candidate_paths:
        artifact = _json_file_payload(path)
        if artifact["artifact_state"] != "ok":
            continue
        payload = artifact["payload"]
        if isinstance(payload, dict):
            try:
                return {
                    **validate_scientific_session_truth(payload),
                    "artifact_state": "ok",
                    "source_path": artifact["source_path"],
                    "source_updated_at": artifact["source_updated_at"],
                    "load_error": "",
                }
            except ContractValidationError:
                return {
                    "artifact_state": "error",
                    "source_path": artifact["source_path"],
                    "source_updated_at": artifact["source_updated_at"],
                    "load_error": "Scientific session truth artifact failed contract validation.",
                }

    summary_payload = _summary_metadata_scientific_truth(session_id, workspace_id)
    if summary_payload:
        try:
            return {
                **validate_scientific_session_truth(summary_payload),
                "artifact_state": "ok",
                "source_path": "session_summary_metadata#scientific_session_truth",
                "source_updated_at": "",
                "load_error": "",
            }
        except ContractValidationError:
            return {
                "artifact_state": "error",
                "source_path": "session_summary_metadata#scientific_session_truth",
                "source_updated_at": "",
                "load_error": "Scientific session truth in session metadata failed contract validation.",
            }

    result_artifact = load_result_payload(
        session_id=session_id,
        workspace_id=workspace_id,
        allow_global_fallback=allow_global_fallback,
    )
    result_payload = result_artifact.get("payload")
    nested = result_payload.get("scientific_session_truth") if isinstance(result_payload, dict) else {}
    if isinstance(nested, dict):
        try:
            return {
                **validate_scientific_session_truth(nested),
                "artifact_state": "ok",
                "source_path": f"{result_artifact.get('source_path')}#scientific_session_truth",
                "source_updated_at": result_artifact.get("source_updated_at"),
                "load_error": "",
            }
        except ContractValidationError:
            return {
                "artifact_state": "error",
                "source_path": f"{result_artifact.get('source_path')}#scientific_session_truth",
                "source_updated_at": result_artifact.get("source_updated_at"),
                "load_error": "Nested scientific session truth failed contract validation.",
            }

    return {"artifact_state": "missing", "source_path": "", "source_updated_at": "", "load_error": ""}
