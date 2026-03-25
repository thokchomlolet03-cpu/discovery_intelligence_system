from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline_utils import write_json_log
from utils.artifact_writer import uploaded_session_dir
from utils.free_paid_mode import assess_free_tier
from utils.upload_validation import (
    coerce_label,
    detect_columns,
    infer_column_mapping,
    normalize_columns,
    validation_summary,
)
from utils.validation import ensure_no_duplicate_columns


RAW_UPLOAD_NAME = "raw_upload.csv"
INSPECT_SUMMARY_NAME = "inspect_summary.json"


def session_id_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def session_dir(session_id: str) -> Path:
    return uploaded_session_dir(session_id)


def create_upload_session(file_bytes: bytes, filename: str, input_type: str) -> dict[str, Any]:
    dataframe = pd.read_csv(io.BytesIO(file_bytes))
    session_id = session_id_now()
    target_dir = uploaded_session_dir(session_id, create=True)
    (target_dir / RAW_UPLOAD_NAME).write_bytes(file_bytes)

    columns = detect_columns(dataframe)
    inferred_mapping = infer_column_mapping(columns)
    summary = validation_summary(dataframe, inferred_mapping)
    preview_rows = dataframe.head(5).fillna("").astype(str).to_dict("records")

    payload = {
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
        "input_type": input_type,
        "columns": columns,
        "preview_rows": preview_rows,
        "inferred_mapping": inferred_mapping,
        "validation_summary": summary,
        "free_tier_assessment": assess_free_tier(summary),
    }
    write_json_log(target_dir / INSPECT_SUMMARY_NAME, payload)
    return payload


def load_session_dataframe(session_id: str) -> pd.DataFrame:
    target = session_dir(session_id) / RAW_UPLOAD_NAME
    if not target.exists():
        raise FileNotFoundError(f"No upload session found for '{session_id}'.")
    return pd.read_csv(target)


def load_session_metadata(session_id: str) -> dict[str, Any]:
    target = session_dir(session_id) / INSPECT_SUMMARY_NAME
    if not target.exists():
        raise FileNotFoundError(f"No session metadata found for '{session_id}'.")
    return json.loads(target.read_text())


def save_session_metadata(session_id: str, payload: dict[str, Any]) -> None:
    write_json_log(session_dir(session_id) / INSPECT_SUMMARY_NAME, payload)


def apply_column_mapping(df: pd.DataFrame, mapping: dict[str, str | None]) -> pd.DataFrame:
    normalized = ensure_no_duplicate_columns(normalize_columns(df.copy()))
    mapped = normalized.copy()

    smiles_column = mapping.get("smiles")
    if not smiles_column or smiles_column not in mapped.columns:
        raise ValueError("A SMILES column must be mapped before analysis can run.")

    mapped["smiles"] = mapped[smiles_column]

    label_column = mapping.get("biodegradable")
    if label_column and label_column in mapped.columns:
        mapped["biodegradable"] = mapped[label_column].apply(coerce_label)
    else:
        mapped["biodegradable"] = -1

    optional_mappings = {
        "molecule_id": mapping.get("molecule_id"),
        "source": mapping.get("source"),
        "notes": mapping.get("notes"),
    }
    for field, column in optional_mappings.items():
        if column and column in mapped.columns:
            mapped[field] = mapped[column]
        elif field == "molecule_id" and "polymer" in mapped.columns:
            mapped[field] = mapped["polymer"]
        else:
            mapped[field] = ""

    return mapped
