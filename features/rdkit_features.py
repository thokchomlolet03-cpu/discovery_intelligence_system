from core.constants import DESCRIPTOR_COLUMNS
from features.fingerprint_features import infer_fingerprint_columns
from system.services.data_service import featurize_dataframe


def build_features(df, feature_contract=None):
    contract = list(dict.fromkeys(feature_contract or (DESCRIPTOR_COLUMNS + infer_fingerprint_columns(df))))
    fingerprint_contract = [column for column in contract if str(column).startswith("fp_")]
    clean = featurize_dataframe(df, fingerprint_columns=fingerprint_contract or infer_fingerprint_columns(df))
    clean = clean.loc[:, ~clean.columns.duplicated()].copy()

    X = clean.reindex(columns=contract).fillna(0)
    X = X.loc[:, ~X.columns.duplicated()].copy()
    return X, clean
