from __future__ import annotations

from typing import Any

import pandas as pd

from system.services.data_service import canonicalize_smiles
from utils.validation import ensure_no_duplicate_columns


FIELD_ALIASES = {
    "smiles": ("smiles", "canonical_smiles", "molecule", "molecules", "structure", "compound_smiles"),
    "biodegradable": ("biodegradable", "label", "labels", "target", "targets", "class", "outcome", "y"),
    "molecule_id": ("molecule_id", "molecule_name", "name", "id", "identifier", "polymer", "compound"),
    "source": ("source", "origin", "dataset", "source_dataset"),
    "notes": ("notes", "note", "comments", "comment", "description"),
}


def normalize_column_name(name: Any) -> str:
    return str(name).strip().lower().replace(" ", "_")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {column: normalize_column_name(column) for column in df.columns}
    return df.rename(columns=renamed)


def detect_columns(df: pd.DataFrame) -> list[str]:
    normalized = normalize_columns(df.copy())
    return [str(column) for column in normalized.columns]


def coerce_label(value: Any) -> int:
    if pd.isna(value):
        return -1
    if isinstance(value, bool):
        return int(value)

    text = str(value).strip().lower()
    mapping = {
        "1": 1,
        "0": 0,
        "-1": -1,
        "true": 1,
        "false": 0,
        "yes": 1,
        "no": 0,
        "positive": 1,
        "negative": 0,
        "biodegradable": 1,
        "non_biodegradable": 0,
        "non-biodegradable": 0,
    }
    if text in mapping:
        return mapping[text]

    try:
        numeric = int(float(text))
    except ValueError:
        return -1
    return numeric if numeric in {-1, 0, 1} else -1


def infer_column_mapping(columns: list[str] | tuple[str, ...]) -> dict[str, str | None]:
    normalized = [normalize_column_name(column) for column in columns]
    mapping: dict[str, str | None] = {}
    for field, aliases in FIELD_ALIASES.items():
        mapping[field] = next((column for column in normalized if column in aliases), None)
    return mapping


def validation_summary(df: pd.DataFrame, mapping: dict[str, str | None]) -> dict[str, Any]:
    normalized = ensure_no_duplicate_columns(normalize_columns(df.copy()))
    total_rows = int(len(normalized))
    smiles_column = mapping.get("smiles")
    label_column = mapping.get("biodegradable")

    if not smiles_column or smiles_column not in normalized.columns:
        return {
            "total_rows": total_rows,
            "valid_smiles_count": 0,
            "invalid_smiles_count": total_rows,
            "duplicate_count": 0,
            "rows_with_labels": 0,
            "rows_without_labels": total_rows,
            "positive_label_count": 0,
            "negative_label_count": 0,
            "unlabeled_label_count": total_rows,
            "label_counts": {
                "positive": 0,
                "negative": 0,
                "unlabeled": total_rows,
            },
            "missing_fields": ["smiles"],
            "warnings": ["Map a SMILES column before analysis can run."],
            "can_run_analysis": False,
        }

    canonical = normalized[smiles_column].apply(canonicalize_smiles)
    valid_smiles_count = int(canonical.notna().sum())
    invalid_smiles_count = int(total_rows - valid_smiles_count)
    duplicate_count = int(canonical[canonical.notna()].duplicated().sum())

    if label_column and label_column in normalized.columns:
        labels = normalized[label_column].apply(coerce_label)
        rows_with_labels = int(labels.isin([0, 1]).sum())
        positive_label_count = int(labels.eq(1).sum())
        negative_label_count = int(labels.eq(0).sum())
    else:
        rows_with_labels = 0
        positive_label_count = 0
        negative_label_count = 0

    unlabeled_label_count = int(max(total_rows - rows_with_labels, 0))

    missing_fields = [field for field in ("smiles",) if not mapping.get(field)]
    warnings: list[str] = []
    if invalid_smiles_count:
        warnings.append(f"{invalid_smiles_count} rows could not be parsed as valid SMILES.")
    if duplicate_count:
        warnings.append(f"{duplicate_count} duplicate molecules were detected.")
    if rows_with_labels == 0:
        warnings.append("No usable labels were detected; the run will rely on ranking or prediction rather than session-trained discovery.")

    return {
        "total_rows": total_rows,
        "valid_smiles_count": valid_smiles_count,
        "invalid_smiles_count": invalid_smiles_count,
        "duplicate_count": duplicate_count,
        "rows_with_labels": rows_with_labels,
        "rows_without_labels": int(total_rows - rows_with_labels),
        "positive_label_count": positive_label_count,
        "negative_label_count": negative_label_count,
        "unlabeled_label_count": unlabeled_label_count,
        "label_counts": {
            "positive": positive_label_count,
            "negative": negative_label_count,
            "unlabeled": unlabeled_label_count,
        },
        "missing_fields": missing_fields,
        "warnings": warnings,
        "can_run_analysis": not missing_fields and valid_smiles_count > 0,
    }
