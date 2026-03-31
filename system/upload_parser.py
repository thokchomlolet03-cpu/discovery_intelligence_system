from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from system.contracts import validate_label_builder_config, validate_upload_inspection_result
from system.db.repositories import ArtifactRepository, SessionRepository
from system.services.ingestion import (
    LEGACY_INPUT_TYPES,
    build_legacy_mapping,
    coerce_label,
    detect_columns,
    detect_file_type,
    derive_labels_from_values,
    infer_measurement_columns,
    infer_semantic_mode,
    infer_semantic_roles,
    normalize_columns,
    normalize_input_type,
    normalize_semantic_mapping,
    parse_sdf_bytes,
    parse_smiles_text,
    parse_tabular_bytes,
    summarize_validation,
)
from system.services.artifact_service import uploaded_session_dir, write_upload_inspection_artifact
from utils.free_paid_mode import assess_free_tier
from utils.validation import ensure_no_duplicate_columns


RAW_UPLOAD_NAME = "raw_upload.csv"
INSPECT_SUMMARY_NAME = "inspect_summary.json"
session_repository = SessionRepository()
artifact_repository = ArtifactRepository(session_repository=session_repository)


def session_id_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def session_dir(session_id: str) -> Path:
    return uploaded_session_dir(session_id)


def _register_session_artifacts(
    session_id: str,
    filename: str,
    input_type: str,
    target_dir: Path,
    workspace_id: str | None = None,
    created_by_user_id: str | None = None,
) -> None:
    artifact_repository.register_artifact(
        artifact_type="raw_upload_csv",
        path=target_dir / RAW_UPLOAD_NAME,
        session_id=session_id,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        metadata={"filename": filename, "input_type": input_type},
    )
    artifact_repository.register_artifact(
        artifact_type="upload_inspection_json",
        path=target_dir / INSPECT_SUMMARY_NAME,
        session_id=session_id,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        metadata={"filename": filename, "input_type": input_type},
    )


def _parse_uploaded_dataframe(file_bytes: bytes, filename: str) -> tuple[pd.DataFrame, str]:
    file_type = detect_file_type(filename)
    if file_type in {"csv", "tsv"}:
        dataframe = parse_tabular_bytes(file_bytes, filename)
    elif file_type == "smiles_txt":
        dataframe = parse_smiles_text(file_bytes, filename)
    elif file_type == "sdf":
        dataframe = parse_sdf_bytes(file_bytes, filename)
    else:  # pragma: no cover - detect_file_type guards this
        raise ValueError(f"Unsupported upload type '{file_type}'.")
    return ensure_no_duplicate_columns(normalize_columns(dataframe.copy())), file_type


def _default_label_builder_suggestion(semantic_roles: dict[str, str | None]) -> dict[str, Any]:
    value_column = semantic_roles.get("value") or ""
    suggestion = {"enabled": False, "value_column": value_column, "operator": ">=", "threshold": None}
    if value_column in {"pic50", "pec50", "pchembl_value"}:
        suggestion["threshold"] = 6.0
    return validate_label_builder_config(suggestion)


def infer_column_mapping(columns: list[str] | tuple[str, ...], dataframe: pd.DataFrame | None = None) -> dict[str, str | None]:
    semantic_roles = infer_semantic_roles(columns, dataframe=dataframe)
    return {
        **semantic_roles,
        **build_legacy_mapping(semantic_roles),
    }


def validation_summary(
    df: pd.DataFrame,
    mapping: dict[str, str | None],
    label_builder: dict[str, Any] | None = None,
    *,
    file_type: str = "",
    semantic_mode: str = "",
) -> dict[str, Any]:
    semantic_roles = normalize_semantic_mapping(mapping)
    label_builder_payload = validate_label_builder_config(label_builder or {"enabled": False})
    return summarize_validation(
        df,
        semantic_roles,
        label_builder=label_builder_payload,
        file_type=file_type,
        semantic_mode=semantic_mode,
    )


def create_upload_session(
    file_bytes: bytes,
    filename: str,
    input_type: str,
    workspace_id: str,
    created_by_user_id: str | None = None,
    max_rows: int | None = None,
) -> dict[str, Any]:
    normalized_input_type = normalize_input_type(input_type)
    dataframe, file_type = _parse_uploaded_dataframe(file_bytes, filename)
    columns = detect_columns(dataframe)
    semantic_roles = infer_semantic_roles(columns, dataframe=dataframe)
    inferred_mapping = infer_column_mapping(columns, dataframe=dataframe)
    suggested_mode = LEGACY_INPUT_TYPES.get(normalized_input_type, "") or infer_semantic_mode(
        semantic_roles,
        rows_with_labels=0,
        rows_with_values=len(infer_measurement_columns(dataframe)),
    )
    summary = validation_summary(
        dataframe,
        semantic_roles,
        file_type=file_type,
        semantic_mode=suggested_mode,
    )
    total_rows = int(summary.get("total_rows", 0) or 0)
    if max_rows is not None and total_rows > int(max_rows):
        raise ValueError(f"Uploads on this workspace plan are limited to {int(max_rows)} rows.")
    preview_rows = dataframe.head(5).fillna("").astype(str).to_dict("records")

    session_id = session_id_now()
    target_dir = uploaded_session_dir(session_id, create=True)
    raw_upload_path = target_dir / RAW_UPLOAD_NAME
    dataframe.to_csv(raw_upload_path, index=False)

    payload = validate_upload_inspection_result(
        {
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "filename": filename,
            "input_type": normalized_input_type,
            "file_type": file_type,
            "semantic_mode": str(summary.get("semantic_mode") or suggested_mode),
            "columns": columns,
            "preview_rows": preview_rows,
            "inferred_mapping": inferred_mapping,
            "semantic_roles": semantic_roles,
            "measurement_columns": infer_measurement_columns(dataframe),
            "label_builder_suggestion": _default_label_builder_suggestion(semantic_roles),
            "validation_summary": summary,
            "free_tier_assessment": assess_free_tier(summary),
        }
    )
    write_upload_inspection_artifact(target_dir / INSPECT_SUMMARY_NAME, payload)
    session_repository.upsert_session(
        session_id=session_id,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        source_name=filename,
        input_type=normalized_input_type,
        upload_metadata=payload,
    )
    _register_session_artifacts(
        session_id,
        filename=filename,
        input_type=normalized_input_type,
        target_dir=target_dir,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
    )
    return payload


def load_session_dataframe(session_id: str, workspace_id: str | None = None) -> pd.DataFrame:
    artifact_path = artifact_repository.get_latest_artifact_path(
        artifact_type="raw_upload_csv",
        session_id=session_id,
        workspace_id=workspace_id,
    )
    if artifact_path is None:
        artifact_path = artifact_repository.get_latest_artifact_path(
            artifact_type="upload_csv",
            session_id=session_id,
            workspace_id=workspace_id,
        )
    target = artifact_path
    if target is None and workspace_id is not None:
        session_repository.get_session(session_id, workspace_id=workspace_id)
        legacy_target = session_dir(session_id) / RAW_UPLOAD_NAME
        target = legacy_target if legacy_target.exists() else None
    if target is None and workspace_id is None:
        target = session_dir(session_id) / RAW_UPLOAD_NAME
    if target is None or not target.exists():
        raise FileNotFoundError(f"No upload session found for '{session_id}'.")
    return pd.read_csv(target)


def load_session_metadata(session_id: str, workspace_id: str | None = None) -> dict[str, Any]:
    try:
        session_metadata = session_repository.get_session(session_id, workspace_id=workspace_id)
    except FileNotFoundError:
        session_metadata = {}
    upload_metadata = session_metadata.get("upload_metadata") if isinstance(session_metadata, dict) else {}
    if upload_metadata:
        return validate_upload_inspection_result(upload_metadata)

    target = session_dir(session_id) / INSPECT_SUMMARY_NAME
    if workspace_id is not None and not session_metadata:
        raise FileNotFoundError(f"No session metadata found for '{session_id}'.")
    if workspace_id is not None and session_metadata:
        session_repository.get_session(session_id, workspace_id=workspace_id)
    if not target.exists():
        raise FileNotFoundError(f"No session metadata found for '{session_id}'.")
    payload = validate_upload_inspection_result(json.loads(target.read_text()))
    session_repository.upsert_session(
        session_id=session_id,
        workspace_id=workspace_id,
        source_name=payload.get("filename"),
        input_type=payload.get("input_type"),
        upload_metadata=payload,
    )
    _register_session_artifacts(
        session_id,
        filename=str(payload.get("filename") or RAW_UPLOAD_NAME),
        input_type=str(payload.get("input_type") or ""),
        target_dir=session_dir(session_id),
        workspace_id=workspace_id,
    )
    return payload


def save_session_metadata(
    session_id: str,
    payload: dict[str, Any],
    workspace_id: str,
    created_by_user_id: str | None = None,
) -> None:
    validated = validate_upload_inspection_result(payload)
    target_dir = uploaded_session_dir(session_id, create=True)
    write_upload_inspection_artifact(target_dir / INSPECT_SUMMARY_NAME, validated)
    session_repository.upsert_session(
        session_id=session_id,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        source_name=validated.get("filename"),
        input_type=validated.get("input_type"),
        upload_metadata=validated,
    )
    _register_session_artifacts(
        session_id,
        filename=str(validated.get("filename") or RAW_UPLOAD_NAME),
        input_type=str(validated.get("input_type") or ""),
        target_dir=target_dir,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
    )


def apply_column_mapping(df: pd.DataFrame, mapping: dict[str, str | None]) -> pd.DataFrame:
    normalized = ensure_no_duplicate_columns(normalize_columns(df.copy()))
    roles = normalize_semantic_mapping(mapping)
    mapped = normalized.copy()

    smiles_column = roles.get("smiles")
    if not smiles_column or smiles_column not in mapped.columns:
        raise ValueError("A SMILES column must be mapped before analysis can run.")

    mapped["smiles"] = mapped[smiles_column]
    return mapped


def build_analysis_frame(
    df: pd.DataFrame,
    mapping: dict[str, str | None],
    label_builder: dict[str, Any] | None = None,
) -> pd.DataFrame:
    normalized = ensure_no_duplicate_columns(normalize_columns(df.copy()))
    roles = normalize_semantic_mapping(mapping)
    label_builder_payload = validate_label_builder_config(label_builder or {"enabled": False})

    smiles_column = roles.get("smiles")
    if not smiles_column or smiles_column not in normalized.columns:
        raise ValueError("A SMILES column must be mapped before analysis can run.")

    mapped = normalized.copy()
    mapped["smiles"] = mapped[smiles_column]

    value_column = roles.get("value")
    if value_column and value_column in mapped.columns:
        mapped["value"] = pd.to_numeric(mapped[value_column], errors="coerce")
    else:
        mapped["value"] = pd.Series([pd.NA] * len(mapped), index=mapped.index, dtype="object")

    label_column = roles.get("label")
    if label_column and label_column in mapped.columns:
        mapped["biodegradable"] = mapped[label_column].apply(coerce_label)
    elif label_builder_payload.get("enabled") and value_column and value_column in mapped.columns:
        mapped["biodegradable"] = derive_labels_from_values(mapped[value_column], label_builder_payload)
    else:
        mapped["biodegradable"] = pd.Series([-1] * len(mapped), index=mapped.index, dtype=int)

    optional_mappings = {
        "entity_id": roles.get("entity_id"),
        "target": roles.get("target"),
        "assay": roles.get("assay"),
        "source": roles.get("source"),
        "notes": roles.get("notes"),
    }
    for field, column in optional_mappings.items():
        if column and column in mapped.columns:
            mapped[field] = mapped[column]
        elif field == "entity_id" and "polymer" in mapped.columns:
            mapped[field] = mapped["polymer"]
        else:
            mapped[field] = ""

    mapped["molecule_id"] = mapped["entity_id"]
    mapped["biodegradable"] = pd.to_numeric(mapped["biodegradable"], errors="coerce").fillna(-1).astype(int)
    return mapped
