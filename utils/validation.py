from core.constants import DESCRIPTOR_COLUMNS
from system.services.data_service import canonicalize_smiles


def validate_smiles(smiles):
    return canonicalize_smiles(smiles) is not None


def ensure_no_duplicate_columns(df):
    return df.loc[:, ~df.columns.duplicated()].copy()


def raw_columns_only(df):
    return df[
        [
            column
            for column in df.columns
            if not str(column).startswith("fp_") and column not in DESCRIPTOR_COLUMNS
        ]
    ].copy()
