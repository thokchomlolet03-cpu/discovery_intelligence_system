from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from system.services.data_service import canonicalize_smiles
from utils.validation import ensure_no_duplicate_columns


ALLOWED_UPLOAD_SUFFIXES = {".csv", ".tsv", ".txt", ".sdf"}
SUPPORTED_FILE_TYPES = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".txt": "smiles_txt",
    ".sdf": "sdf",
}
LEGACY_INPUT_TYPES = {
    "experimental_results": "measurement_dataset",
    "known_labeled_molecules": "labeled_tabular_dataset",
    "molecules_to_screen_only": "structure_only_screening",
    "candidate_list_for_ranking": "structure_only_screening",
}
CANONICAL_INPUT_TYPES = {
    "measurement_dataset",
    "labeled_tabular_dataset",
    "structure_only_screening",
}
SEMANTIC_ROLE_FIELDS = (
    "entity_id",
    "smiles",
    "value",
    "label",
    "target",
    "assay",
    "source",
    "notes",
)
ROLE_ALIASES = {
    "entity_id": (
        "entity_id",
        "molecule_id",
        "molecule_name",
        "compound_id",
        "compound_name",
        "name",
        "identifier",
        "id",
        "polymer",
    ),
    "smiles": ("smiles", "canonical_smiles", "structure", "compound_smiles", "molecule_smiles"),
    "value": (
        "value",
        "measurement",
        "measured_value",
        "response",
        "activity",
        "activity_value",
        "pic50",
        "pec50",
        "pchembl_value",
        "potency",
        "score",
    ),
    "label": (
        "label",
        "labels",
        "biodegradable",
        "class",
        "outcome",
        "y",
        "active",
        "activity_label",
    ),
    "target": ("target", "target_name", "protein", "gene", "receptor"),
    "assay": ("assay", "assay_name", "screen", "protocol", "experiment", "readout"),
    "source": ("source", "origin", "dataset", "source_dataset"),
    "notes": ("notes", "note", "comments", "comment", "description"),
}
DEFAULT_LABEL_BUILDER_SUGGESTIONS = {
    "pic50": {"operator": ">=", "threshold": 6.0},
    "pec50": {"operator": ">=", "threshold": 6.0},
    "pchembl_value": {"operator": ">=", "threshold": 6.0},
}


def normalize_column_name(name: Any) -> str:
    return str(name).strip().lower().replace(" ", "_")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {column: normalize_column_name(column) for column in df.columns}
    return df.rename(columns=renamed)


def detect_columns(df: pd.DataFrame) -> list[str]:
    normalized = normalize_columns(df.copy())
    return [str(column) for column in normalized.columns]


def detect_file_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_FILE_TYPES:
        supported = ", ".join(sorted(ALLOWED_UPLOAD_SUFFIXES))
        raise ValueError(f"Unsupported upload type '{suffix or '[no extension]'}'. Supported types: {supported}.")
    return SUPPORTED_FILE_TYPES[suffix]


def normalize_input_type(input_type: Any, default: str = "measurement_dataset") -> str:
    cleaned = str(input_type or "").strip()
    if cleaned in CANONICAL_INPUT_TYPES:
        return cleaned
    return LEGACY_INPUT_TYPES.get(cleaned, default)


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
        "active": 1,
        "inactive": 0,
    }
    if text in mapping:
        return mapping[text]
    try:
        numeric = int(float(text))
    except ValueError:
        return -1
    return numeric if numeric in {-1, 0, 1} else -1


def normalize_semantic_mapping(mapping: dict[str, str | None] | None) -> dict[str, str | None]:
    mapping = mapping or {}
    normalized = {field: None for field in SEMANTIC_ROLE_FIELDS}
    legacy_fallbacks = {
        "label": mapping.get("biodegradable"),
        "entity_id": mapping.get("molecule_id"),
    }
    for field in SEMANTIC_ROLE_FIELDS:
        value = mapping.get(field) or legacy_fallbacks.get(field)
        normalized[field] = normalize_column_name(value) if value else None
    return normalized


def build_legacy_mapping(mapping: dict[str, str | None] | None) -> dict[str, str | None]:
    normalized = normalize_semantic_mapping(mapping)
    return {
        "smiles": normalized.get("smiles"),
        "biodegradable": normalized.get("label"),
        "molecule_id": normalized.get("entity_id"),
        "source": normalized.get("source"),
        "notes": normalized.get("notes"),
    }


def _sample_series(series: pd.Series, limit: int = 50) -> pd.Series:
    return series.dropna().astype(str).head(limit)


def _looks_like_smiles(series: pd.Series) -> bool:
    sample = _sample_series(series)
    if sample.empty:
        return False
    valid = sample.apply(canonicalize_smiles).notna().sum()
    return bool(valid) and (valid / len(sample)) >= 0.7


def _looks_like_label(series: pd.Series) -> bool:
    sample = _sample_series(series)
    if sample.empty:
        return False
    valid = sample.apply(coerce_label).isin([0, 1]).sum()
    return bool(valid) and (valid / len(sample)) >= 0.8


def infer_measurement_columns(df: pd.DataFrame) -> list[str]:
    normalized = ensure_no_duplicate_columns(normalize_columns(df.copy()))
    candidates: list[tuple[str, float]] = []
    for column in normalized.columns:
        series = pd.to_numeric(normalized[column], errors="coerce")
        coverage = float(series.notna().mean()) if len(series) else 0.0
        unique = int(series.dropna().nunique())
        if coverage < 0.5 or unique < 3:
            continue
        name = normalize_column_name(column)
        score = coverage
        if any(alias in name for alias in ("pic50", "pec50", "activity", "measurement", "value", "score", "potency", "pchembl")):
            score += 1.0
        candidates.append((name, score))
    candidates.sort(key=lambda item: item[1], reverse=True)
    return [name for name, _ in candidates]


def infer_semantic_roles(columns: list[str] | tuple[str, ...], dataframe: pd.DataFrame | None = None) -> dict[str, str | None]:
    normalized_columns = [normalize_column_name(column) for column in columns]
    mapping: dict[str, str | None] = {}
    for field, aliases in ROLE_ALIASES.items():
        mapping[field] = next((column for column in normalized_columns if column in aliases), None)

    if dataframe is not None:
        normalized_df = ensure_no_duplicate_columns(normalize_columns(dataframe.copy()))
        if not mapping.get("smiles"):
            mapping["smiles"] = next(
                (column for column in normalized_df.columns if _looks_like_smiles(normalized_df[column])),
                None,
            )
        if not mapping.get("label"):
            mapping["label"] = next(
                (
                    column
                    for column in normalized_df.columns
                    if column not in {mapping.get("smiles"), mapping.get("value")}
                    and _looks_like_label(normalized_df[column])
                ),
                None,
            )
        if not mapping.get("value"):
            measurement_columns = infer_measurement_columns(normalized_df)
            mapping["value"] = measurement_columns[0] if measurement_columns else None
    return normalize_semantic_mapping(mapping)


def infer_semantic_mode(
    mapping: dict[str, str | None] | None,
    *,
    rows_with_labels: int = 0,
    rows_with_values: int = 0,
) -> str:
    normalized = normalize_semantic_mapping(mapping)
    if rows_with_labels > 0 or normalized.get("label"):
        return "labeled_tabular_dataset"
    if rows_with_values > 0 or normalized.get("value"):
        return "measurement_dataset"
    return "structure_only_screening"


def _compare_values(series: pd.Series, operator: str, threshold: float) -> pd.Series:
    if operator == ">":
        return series > threshold
    if operator == ">=":
        return series >= threshold
    if operator == "<":
        return series < threshold
    if operator == "<=":
        return series <= threshold
    if operator in {"=", "=="}:
        return series == threshold
    raise ValueError(f"Unsupported label-builder operator '{operator}'.")


def derive_labels_from_values(
    values: pd.Series,
    label_builder: dict[str, Any] | None,
) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    labels = pd.Series([-1] * len(numeric), index=numeric.index, dtype=int)
    if not label_builder or not label_builder.get("enabled"):
        return labels

    threshold = label_builder.get("threshold")
    if threshold in (None, ""):
        return labels
    operator = str(label_builder.get("operator") or ">=").strip()
    positive_label = int(label_builder.get("positive_label", 1))
    negative_label = int(label_builder.get("negative_label", 0))
    mask = _compare_values(numeric, operator, float(threshold))
    labels.loc[numeric.notna() & mask] = positive_label
    labels.loc[numeric.notna() & ~mask] = negative_label
    return labels


def summarize_validation(
    df: pd.DataFrame,
    mapping: dict[str, str | None] | None,
    *,
    label_builder: dict[str, Any] | None = None,
    file_type: str = "",
    semantic_mode: str = "",
) -> dict[str, Any]:
    normalized = ensure_no_duplicate_columns(normalize_columns(df.copy()))
    roles = normalize_semantic_mapping(mapping)
    total_rows = int(len(normalized))
    smiles_column = roles.get("smiles")
    label_column = roles.get("label")
    value_column = roles.get("value")

    if not smiles_column or smiles_column not in normalized.columns:
        return {
            "total_rows": total_rows,
            "valid_smiles_count": 0,
            "invalid_smiles_count": total_rows,
            "duplicate_count": 0,
            "rows_with_labels": 0,
            "rows_without_labels": total_rows,
            "rows_with_values": 0,
            "rows_without_values": total_rows,
            "value_column": value_column or "",
            "positive_label_count": 0,
            "negative_label_count": 0,
            "unlabeled_label_count": total_rows,
            "label_counts": {"positive": 0, "negative": 0, "unlabeled": total_rows},
            "missing_fields": ["smiles"],
            "warnings": ["Map a SMILES column before analysis can run."],
            "can_run_analysis": False,
            "semantic_mode": semantic_mode or infer_semantic_mode(roles),
            "label_source": "missing",
            "file_type": file_type,
        }

    canonical = normalized[smiles_column].apply(canonicalize_smiles)
    valid_smiles_count = int(canonical.notna().sum())
    invalid_smiles_count = int(total_rows - valid_smiles_count)
    duplicate_count = int(canonical[canonical.notna()].duplicated().sum())

    values = pd.Series([None] * total_rows)
    rows_with_values = 0
    if value_column and value_column in normalized.columns:
        values = pd.to_numeric(normalized[value_column], errors="coerce")
        rows_with_values = int(values.notna().sum())

    label_source = "missing"
    if label_column and label_column in normalized.columns:
        labels = normalized[label_column].apply(coerce_label)
        label_source = "mapped"
    elif label_builder and label_builder.get("enabled") and value_column and value_column in normalized.columns:
        labels = derive_labels_from_values(normalized[value_column], label_builder)
        label_source = "derived"
    else:
        labels = pd.Series([-1] * total_rows, index=normalized.index, dtype=int)

    rows_with_labels = int(labels.isin([0, 1]).sum())
    positive_label_count = int(labels.eq(1).sum())
    negative_label_count = int(labels.eq(0).sum())
    unlabeled_label_count = int(max(total_rows - rows_with_labels, 0))
    resolved_mode = semantic_mode or infer_semantic_mode(
        roles,
        rows_with_labels=0 if label_source == "derived" else rows_with_labels,
        rows_with_values=rows_with_values,
    )

    warnings: list[str] = []
    if invalid_smiles_count:
        warnings.append(f"{invalid_smiles_count} rows could not be parsed as valid SMILES.")
    if duplicate_count:
        warnings.append(f"{duplicate_count} duplicate molecules were detected.")
    if rows_with_labels == 0 and rows_with_values and value_column and not (label_builder or {}).get("enabled"):
        warnings.append(
            f"Continuous measurements were detected in '{value_column}'. Add a label builder rule if you want session-trained discovery."
        )
    elif rows_with_labels == 0:
        warnings.append("No usable labels were detected; the run will rely on ranking or prediction rather than session-trained discovery.")
    if resolved_mode == "measurement_dataset" and rows_with_values == 0:
        warnings.append("Measurement mode was selected, but no usable numeric measurement column is mapped yet.")

    return {
        "total_rows": total_rows,
        "valid_smiles_count": valid_smiles_count,
        "invalid_smiles_count": invalid_smiles_count,
        "duplicate_count": duplicate_count,
        "rows_with_labels": rows_with_labels,
        "rows_without_labels": int(total_rows - rows_with_labels),
        "rows_with_values": rows_with_values,
        "rows_without_values": int(total_rows - rows_with_values),
        "value_column": value_column or "",
        "positive_label_count": positive_label_count,
        "negative_label_count": negative_label_count,
        "unlabeled_label_count": unlabeled_label_count,
        "label_counts": {
            "positive": positive_label_count,
            "negative": negative_label_count,
            "unlabeled": unlabeled_label_count,
        },
        "missing_fields": [field for field in ("smiles",) if not roles.get(field)],
        "warnings": warnings,
        "can_run_analysis": valid_smiles_count > 0,
        "semantic_mode": resolved_mode,
        "label_source": label_source,
        "file_type": file_type,
        "analyzed_rows": valid_smiles_count,
        "canonicalized_rows": valid_smiles_count,
        "duplicate_removed_count": duplicate_count,
        "usable_label_count": rows_with_labels,
        "row_count_before": total_rows,
        "row_count_after": max(valid_smiles_count - duplicate_count, 0),
    }
