from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from features.rdkit_features import build_features
from system.services.data_service import DESCRIPTOR_COLUMNS, feature_columns_from_df, regression_subset
from system.services.prediction_service import align_features
from system.services.runtime_config import config_to_dict, resolve_system_config


DEFAULT_REGRESSION_MODEL_PATH = Path("rf_regression_model_v1.joblib")


def ensure_regression_targets(y: pd.Series) -> None:
    if len(y) < 6:
        raise ValueError("Regression requires at least 6 measured rows in the current upload.")
    if y.nunique() < 3:
        raise ValueError("Regression requires at least 3 distinct measured target values.")


def build_regression_model(config=None, random_state=None):
    cfg = resolve_system_config(config, seed=random_state)
    model = RandomForestRegressor(
        n_estimators=cfg.model.n_estimators,
        random_state=cfg.model.random_state if random_state is None else random_state,
        min_samples_leaf=cfg.model.min_samples_leaf,
        n_jobs=-1,
    )
    return Pipeline([("scaler", StandardScaler()), ("regressor", model)])


def regression_metrics(y_true: pd.Series, predictions: np.ndarray) -> dict[str, Any]:
    rmse = float(np.sqrt(mean_squared_error(y_true, predictions)))
    mae = float(mean_absolute_error(y_true, predictions))
    r2 = float(r2_score(y_true, predictions))
    payload: dict[str, Any] = {
        "rmse": rmse,
        "mae": mae,
        "r2": r2,
    }
    if len(y_true) >= 2:
        try:
            payload["spearman_rank_correlation"] = float(pd.Series(y_true).rank().corr(pd.Series(predictions).rank()))
        except Exception:
            payload["spearman_rank_correlation"] = None
    else:
        payload["spearman_rank_correlation"] = None
    return payload


def regression_cv_metrics(model, X: pd.DataFrame, y: pd.Series, config=None) -> dict[str, Any]:
    cfg = resolve_system_config(config)
    splits = max(2, min(cfg.model.evaluation_cv_splits, len(X)))
    cv = KFold(n_splits=splits, shuffle=True, random_state=cfg.model.random_state)
    rmse_scores = np.sqrt(-cross_val_score(model, X, y, cv=cv, scoring="neg_mean_squared_error"))
    mae_scores = -cross_val_score(model, X, y, cv=cv, scoring="neg_mean_absolute_error")
    r2_scores = cross_val_score(model, X, y, cv=cv, scoring="r2")
    return {
        "rmse": {"mean": float(np.mean(rmse_scores)), "std": float(np.std(rmse_scores)), "scores": [float(item) for item in rmse_scores]},
        "mae": {"mean": float(np.mean(mae_scores)), "std": float(np.std(mae_scores)), "scores": [float(item) for item in mae_scores]},
        "r2": {"mean": float(np.mean(r2_scores)), "std": float(np.std(r2_scores)), "scores": [float(item) for item in r2_scores]},
    }


def train_regression_model(df: pd.DataFrame, random_state=42, config=None):
    cfg = resolve_system_config(config, seed=random_state)
    measured = regression_subset(df)
    X, clean_measured = build_features(measured)
    features = feature_columns_from_df(clean_measured if not clean_measured.empty else measured)
    X = X.reindex(columns=features).fillna(0).astype(float)
    y = pd.to_numeric(clean_measured["target_value"], errors="coerce").dropna()
    X = X.loc[y.index]

    ensure_regression_targets(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=cfg.model.test_size,
        random_state=cfg.model.random_state,
    )
    model = build_regression_model(config=cfg, random_state=random_state)
    model.fit(X_train, y_train)
    holdout_predictions = model.predict(X_test)
    holdout = regression_metrics(y_test, holdout_predictions)

    final_model = build_regression_model(config=cfg, random_state=random_state)
    final_model.fit(X, y)
    final_model.feature_order_ = list(X.columns)

    return {
        "model": final_model,
        "model_kind": "regression",
        "features": list(X.columns),
        "descriptor_features": list(DESCRIPTOR_COLUMNS),
        "fingerprint_bits": int(len(features) - len(DESCRIPTOR_COLUMNS)),
        "training_sample_size": int(len(y)),
        "target_summary": {
            "count": int(len(y)),
            "min": float(y.min()),
            "max": float(y.max()),
            "mean": float(y.mean()),
            "median": float(y.median()),
            "std": float(y.std(ddof=0)),
        },
        "selected_model": {
            "name": "rf_regression",
            "calibration_method": "",
        },
        "benchmark": [],
        "metrics": {
            "cv": regression_cv_metrics(build_regression_model(config=cfg, random_state=random_state), X, y, config=cfg),
            "holdout": holdout,
        },
        "regression_metrics": holdout,
        "config": config_to_dict(cfg),
        "thresholds": {},
    }


def _ensemble_dispersion(bundle: dict[str, Any], X: pd.DataFrame) -> np.ndarray:
    pipeline = bundle["model"]
    regressor = pipeline.named_steps["regressor"]
    transformed = pipeline.named_steps["scaler"].transform(X)
    estimators = getattr(regressor, "estimators_", [])
    if not estimators:
        return np.zeros(len(X), dtype=float)
    predictions = np.vstack([estimator.predict(transformed) for estimator in estimators])
    return predictions.std(axis=0)


def _normalized_desirability(predictions: np.ndarray, target_summary: dict[str, Any], optimization_direction: str) -> np.ndarray:
    min_value = float(target_summary.get("min", 0.0) or 0.0)
    max_value = float(target_summary.get("max", 0.0) or 0.0)
    if max_value <= min_value:
        return np.full(len(predictions), 0.5, dtype=float)

    if optimization_direction == "minimize":
        desirability = (max_value - predictions) / (max_value - min_value)
    elif optimization_direction == "maximize":
        desirability = (predictions - min_value) / (max_value - min_value)
    else:
        midpoint = (max_value + min_value) / 2.0
        half_span = max((max_value - min_value) / 2.0, 1e-8)
        desirability = 1.0 - (np.abs(predictions - midpoint) / half_span)
    return np.clip(desirability, 0.0, 1.0)


def _normalized_dispersion(dispersion: np.ndarray) -> np.ndarray:
    if dispersion.size == 0:
        return np.asarray([], dtype=float)
    max_dispersion = float(np.max(dispersion))
    if max_dispersion <= 0:
        return np.zeros_like(dispersion, dtype=float)
    return np.clip(dispersion / max_dispersion, 0.0, 1.0)


def predict_regression_with_model(bundle: dict[str, Any], df: pd.DataFrame, *, optimization_direction: str = "hit_range") -> pd.DataFrame:
    scored = df.copy()
    X = align_features(scored, bundle.get("features", []))
    predictions = bundle["model"].predict(X)
    dispersion = _ensemble_dispersion(bundle, X)
    uncertainty = _normalized_dispersion(dispersion)
    desirability = _normalized_desirability(predictions, bundle.get("target_summary", {}), optimization_direction)

    scored["predicted_value"] = predictions
    scored["prediction_dispersion"] = dispersion
    scored["confidence"] = desirability
    scored["uncertainty"] = uncertainty
    scored["uncertainty_kind"] = "ensemble_prediction_std"
    if "novelty" not in scored.columns:
        scored["novelty"] = pd.to_numeric(scored.get("novel_to_dataset", 0), errors="coerce").fillna(0)
    else:
        scored["novelty"] = pd.to_numeric(scored["novelty"], errors="coerce").fillna(0)
    return scored


__all__ = [
    "DEFAULT_REGRESSION_MODEL_PATH",
    "build_regression_model",
    "ensure_regression_targets",
    "predict_regression_with_model",
    "train_regression_model",
]
