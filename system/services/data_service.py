from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem, Descriptors

from core.constants import preferred_data_path
from system.services.runtime_config import resolve_system_config


DESCRIPTOR_COLUMNS = ["mw", "rdkit_logp", "h_donors", "h_acceptors"]
DEFAULT_FINGERPRINT_BITS = 2048
DEFAULT_FINGERPRINT_COLUMNS = [f"fp_{idx}" for idx in range(DEFAULT_FINGERPRINT_BITS)]
FINGERPRINT_BITS = DEFAULT_FINGERPRINT_BITS
FINGERPRINT_COLUMNS = DEFAULT_FINGERPRINT_COLUMNS
MODEL_FEATURES = DESCRIPTOR_COLUMNS + DEFAULT_FINGERPRINT_COLUMNS
DEFAULT_DATA_PATH = Path("data.csv")

RDLogger.DisableLog("rdApp.*")


def canonicalize_smiles(smiles):
    if pd.isna(smiles):
        return None
    mol = Chem.MolFromSmiles(str(smiles))
    if mol is None:
        return None
    return Chem.MolToSmiles(mol, canonical=True)


def molecule_from_smiles(smiles):
    canonical = canonicalize_smiles(smiles)
    if canonical is None:
        return None, None
    return canonical, Chem.MolFromSmiles(canonical)


def infer_fingerprint_columns(df):
    fp_cols = sorted(
        [col for col in df.columns if str(col).startswith("fp_")],
        key=lambda name: int(str(name).split("_")[1]),
    )
    return fp_cols or list(DEFAULT_FINGERPRINT_COLUMNS)


def feature_columns_from_df(df):
    return list(DESCRIPTOR_COLUMNS) + infer_fingerprint_columns(df)


def compute_descriptors(mol):
    return {
        "mw": float(Descriptors.MolWt(mol)),
        "rdkit_logp": float(Descriptors.MolLogP(mol)),
        "h_donors": int(Descriptors.NumHDonors(mol)),
        "h_acceptors": int(Descriptors.NumHAcceptors(mol)),
    }


def compute_fingerprint(mol, n_bits=DEFAULT_FINGERPRINT_BITS):
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=n_bits)
    arr = np.zeros((n_bits,), dtype=int)
    DataStructs.ConvertToNumpyArray(fp, arr)
    return arr


def build_fingerprint_columns(n_bits):
    return [f"fp_{idx}" for idx in range(n_bits)]


def featurize_dataframe(df, smiles_column="smiles", fingerprint_columns=None):
    fp_columns = list(fingerprint_columns or infer_fingerprint_columns(df))
    n_bits = len(fp_columns)
    model_features = list(DESCRIPTOR_COLUMNS) + fp_columns
    cleaned_rows = []

    for row in df.to_dict("records"):
        canonical, mol = molecule_from_smiles(row.get(smiles_column))
        if mol is None:
            continue

        base = dict(row)
        base[smiles_column] = canonical
        base.update(compute_descriptors(mol))

        fp = compute_fingerprint(mol, n_bits=n_bits)
        for idx, bit in enumerate(fp):
            base[fp_columns[idx]] = int(bit)

        cleaned_rows.append(base)

    if not cleaned_rows:
        columns = list(dict.fromkeys(list(df.columns) + model_features))
        return pd.DataFrame(columns=columns)

    featurized = pd.DataFrame(cleaned_rows)
    for col in model_features:
        if col not in featurized.columns:
            featurized[col] = 0
    return featurized


def load_dataset(path=DEFAULT_DATA_PATH, featurize=True):
    df = pd.read_csv(path)
    if "smiles" in df.columns:
        df["smiles"] = df["smiles"].apply(canonicalize_smiles)
        df = df[df["smiles"].notna()].reset_index(drop=True)

    if featurize:
        features = feature_columns_from_df(df)
        missing = [col for col in features if col not in df.columns]
        if missing:
            df = featurize_dataframe(df, fingerprint_columns=features[len(DESCRIPTOR_COLUMNS) :])
        else:
            for col in features:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


def clean_labels(df):
    cleaned = df.copy()
    cleaned = cleaned[cleaned["biodegradable"].isin([-1, 0, 1])].reset_index(drop=True)
    return cleaned


def labeled_subset(df):
    return df[df["biodegradable"].isin([0, 1])].copy()


def prepare_analysis_dataframe(
    df: pd.DataFrame,
    column_mapping: dict[str, str | None],
    label_builder: dict[str, Any] | None = None,
    validation_context: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    from system.upload_parser import build_analysis_frame, validation_summary

    validation_context = validation_context or {}
    mapped = build_analysis_frame(df, column_mapping, label_builder=label_builder)
    summary = validation_summary(
        df,
        column_mapping,
        label_builder=label_builder,
        file_type=str(validation_context.get("file_type") or ""),
        semantic_mode=str(validation_context.get("semantic_mode") or ""),
    )

    prepared = mapped.copy()
    prepared["smiles"] = prepared["smiles"].apply(canonicalize_smiles)
    prepared = prepared[prepared["smiles"].notna()].reset_index(drop=True)
    prepared["biodegradable"] = pd.to_numeric(prepared["biodegradable"], errors="coerce").fillna(-1).astype(int)
    if "entity_id" not in prepared.columns:
        prepared["entity_id"] = ""
    prepared["entity_id"] = prepared["entity_id"].fillna("").astype(str)
    if "molecule_id" not in prepared.columns:
        prepared["molecule_id"] = prepared["entity_id"]
    prepared["molecule_id"] = prepared["molecule_id"].fillna(prepared["entity_id"]).astype(str)
    if "value" in prepared.columns:
        prepared["value"] = pd.to_numeric(prepared["value"], errors="coerce")
    else:
        prepared["value"] = pd.Series([np.nan] * len(prepared), index=prepared.index)
    if "target" not in prepared.columns:
        prepared["target"] = ""
    if "assay" not in prepared.columns:
        prepared["assay"] = ""
    if "source" not in prepared.columns:
        prepared["source"] = ""
    if "notes" not in prepared.columns:
        prepared["notes"] = ""
    prepared["target"] = prepared["target"].fillna("").astype(str)
    prepared["assay"] = prepared["assay"].fillna("").astype(str)
    prepared["source"] = prepared["source"].fillna("").astype(str)
    prepared["notes"] = prepared["notes"].fillna("").astype(str)

    before_dedup = len(prepared)
    prepared = prepared.drop_duplicates(subset=["smiles"], keep="first").reset_index(drop=True)
    if prepared.empty:
        raise ValueError("No valid SMILES remained after applying the selected column mapping.")
    summary["duplicate_count"] = max(int(summary.get("duplicate_count", 0)), int(before_dedup - len(prepared)))
    summary["analyzed_rows"] = int(len(prepared))
    return prepared, summary


def reference_smiles_from_dataset(path: Path | None = None) -> list[str]:
    target_path = path or preferred_data_path()
    if not target_path.exists():
        return []

    reference = pd.read_csv(target_path)
    if "smiles" not in reference.columns:
        return []
    return reference["smiles"].dropna().astype(str).tolist()


__all__ = [
    "DEFAULT_DATA_PATH",
    "DEFAULT_FINGERPRINT_BITS",
    "DEFAULT_FINGERPRINT_COLUMNS",
    "DESCRIPTOR_COLUMNS",
    "FINGERPRINT_BITS",
    "FINGERPRINT_COLUMNS",
    "MODEL_FEATURES",
    "build_fingerprint_columns",
    "canonicalize_smiles",
    "clean_labels",
    "compute_descriptors",
    "compute_fingerprint",
    "feature_columns_from_df",
    "featurize_dataframe",
    "infer_fingerprint_columns",
    "labeled_subset",
    "load_dataset",
    "molecule_from_smiles",
    "prepare_analysis_dataframe",
    "reference_smiles_from_dataset",
    "resolve_system_config",
]
