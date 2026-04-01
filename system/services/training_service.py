from __future__ import annotations

from system.services.runtime_config import asdict, config_to_dict, resolve_system_config, ThresholdConfig

import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from models.calibration import calibrate_model
from system.contracts import validate_training_result
from system.services.data_service import (
    DEFAULT_FINGERPRINT_BITS,
    DESCRIPTOR_COLUMNS,
    MODEL_FEATURES,
    canonical_label_column,
    feature_columns_from_df,
    labeled_subset,
)


DEFAULT_MODEL_PATH = Path("rf_model_v1.joblib")
DEFAULT_EVALUATION_PATH = Path("evaluation_summary.json")


def ensure_training_labels(y):
    if y.nunique() < 2:
        raise ValueError("Training requires both positive and negative labeled samples.")


def calibration_cv_splits(y, desired_splits):
    min_class_count = int(y.value_counts().min())
    return max(2, min(desired_splits, min_class_count))


def build_model(calibration_method="isotonic", config=None, random_state=None, calibration_cv=None):
    cfg = resolve_system_config(config, seed=random_state)
    base_model = RandomForestClassifier(
        n_estimators=cfg.model.n_estimators,
        random_state=cfg.model.random_state if random_state is None else random_state,
        class_weight=cfg.model.class_weight,
        min_samples_leaf=cfg.model.min_samples_leaf,
        n_jobs=-1,
    )
    effective_cv = max(2, cfg.model.calibration_cv if calibration_cv is None else calibration_cv)
    calibrated = calibrate_model(base_model, method=calibration_method, cv=effective_cv)
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", calibrated),
        ]
    )


def summarize_series(values):
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return {"count": 0, "min": None, "max": None, "mean": None, "std": None}
    return {
        "count": int(arr.size),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
    }


def quantile_summary(values, quantiles=(0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)):
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return {str(q): None for q in quantiles}
    return {str(q): float(np.quantile(arr, q)) for q in quantiles}


def log_distribution(prefix, values):
    summary = summarize_series(values)
    if summary["count"] == 0:
        print(f"{prefix}: count=0")
        return
    print(
        f"{prefix}: count={summary['count']} min={summary['min']:.4f} "
        f"max={summary['max']:.4f} mean={summary['mean']:.4f} std={summary['std']:.4f}"
    )


def clip_probabilities(probabilities, eps):
    arr = np.asarray(probabilities, dtype=float)
    return np.clip(arr, eps, 1.0 - eps)


def per_class_probability_summary(y_true, probabilities):
    y_arr = np.asarray(y_true)
    probs = np.asarray(probabilities, dtype=float)
    return {
        f"true_{label}": {
            "summary": summarize_series(probs[y_arr == label]),
            "quantiles": quantile_summary(probs[y_arr == label]),
        }
        for label in sorted(set(y_arr.tolist()))
    }


def holdout_metrics(y_true, y_pred, raw_probabilities, clipped_probabilities):
    y_true_arr = np.asarray(y_true, dtype=int)
    raw_probs = np.asarray(raw_probabilities, dtype=float)
    probs = np.asarray(clipped_probabilities, dtype=float)
    exact_zero = np.isclose(raw_probs, 0.0)
    exact_one = np.isclose(raw_probs, 1.0)

    return {
        "accuracy": float(accuracy_score(y_true_arr, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true_arr, y_pred)),
        "f1_macro": float(f1_score(y_true_arr, y_pred, average="macro")),
        "brier_score": float(brier_score_loss(y_true_arr, probs)),
        "log_loss": float(log_loss(y_true_arr, np.column_stack([1.0 - probs, probs]), labels=[0, 1])),
        "confusion_matrix": confusion_matrix(y_true_arr, y_pred).tolist(),
        "classification_report": classification_report(y_true_arr, y_pred, output_dict=True),
        "confidence_summary": summarize_series(probs),
        "raw_confidence_summary": summarize_series(raw_probs),
        "confidence_quantiles": quantile_summary(probs),
        "raw_confidence_quantiles": quantile_summary(raw_probs),
        "exact_zero_rate_raw": float(np.mean(exact_zero)),
        "exact_one_rate_raw": float(np.mean(exact_one)),
        "exact_confidence_rate_raw": float(np.mean(exact_zero | exact_one)),
        "per_class_probability_summary": per_class_probability_summary(y_true_arr, probs),
    }


def evaluation_summary(model, X, y, config=None):
    cfg = resolve_system_config(config)
    class_counts = y.value_counts().to_dict()
    min_class_count = min(class_counts.values())
    splits = max(2, min(cfg.model.evaluation_cv_splits, min_class_count))
    cv = StratifiedKFold(n_splits=splits, shuffle=True, random_state=cfg.model.random_state)
    metrics = {}
    for metric in ("accuracy", "balanced_accuracy", "f1_macro"):
        scores = cross_val_score(model, X, y, cv=cv, scoring=metric)
        metrics[metric] = {
            "mean": float(np.mean(scores)),
            "std": float(np.std(scores)),
            "scores": [float(score) for score in scores],
        }
    return metrics


def benchmark_model_candidates(X_train, y_train, X_test, y_test, config=None):
    from dataclasses import replace

    cfg = resolve_system_config(config)
    benchmark = []
    calibration_cv = calibration_cv_splits(y_train, cfg.model.calibration_cv)

    for method in cfg.model.calibration_methods:
        method_cfg = replace(cfg, model=replace(cfg.model, calibration_cv=calibration_cv))
        candidate_model = build_model(calibration_method=method, config=method_cfg)
        candidate_model.fit(X_train, y_train)

        raw_probs = candidate_model.predict_proba(X_test)[:, 1]
        clipped_probs = clip_probabilities(raw_probs, cfg.model.probability_clip)
        y_pred = candidate_model.predict(X_test)
        metrics = holdout_metrics(y_test, y_pred, raw_probs, clipped_probs)

        benchmark.append(
            {
                "name": f"rf_{method}",
                "calibration_method": method,
                "metrics": metrics,
                "model": candidate_model,
            }
        )

    benchmark.sort(
        key=lambda item: (
            item["metrics"]["brier_score"],
            -item["metrics"]["balanced_accuracy"],
            item["metrics"]["exact_confidence_rate_raw"],
            item["metrics"]["log_loss"],
        )
    )
    return benchmark


def train_model(df, random_state=42, config=None):
    cfg = resolve_system_config(config, seed=random_state)
    labeled = labeled_subset(df)
    features = feature_columns_from_df(labeled if not labeled.empty else df)
    X = labeled.reindex(columns=features).fillna(0).astype(float)
    y = labeled[canonical_label_column(labeled)].astype(int)

    ensure_training_labels(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=cfg.model.test_size,
        random_state=cfg.model.random_state,
        stratify=y,
    )

    benchmark = benchmark_model_candidates(X_train, y_train, X_test, y_test, config=cfg)
    selected = benchmark[0]
    selected_method = selected["calibration_method"]

    full_calibration_cv = calibration_cv_splits(y, cfg.model.calibration_cv)
    cv_metrics = evaluation_summary(
        build_model(calibration_method=selected_method, config=cfg, calibration_cv=full_calibration_cv),
        X,
        y,
        config=cfg,
    )

    final_model = build_model(calibration_method=selected_method, config=cfg, calibration_cv=full_calibration_cv)
    final_model.fit(X, y)
    final_model.feature_order_ = list(X.columns)

    benchmark_summary = [
        {
            "name": candidate["name"],
            "calibration_method": candidate["calibration_method"],
            "metrics": candidate["metrics"],
        }
        for candidate in benchmark
    ]

    return {
        "model": final_model,
        "model_kind": "classification",
        "features": list(X.columns),
        "descriptor_features": list(DESCRIPTOR_COLUMNS),
        "fingerprint_bits": int(len(features) - len(DESCRIPTOR_COLUMNS)),
        "training_sample_size": int(len(y)),
        "class_balance": {
            "positive": int((y == 1).sum()),
            "negative": int((y == 0).sum()),
            "unlabeled": 0,
        },
        "thresholds": asdict(
            ThresholdConfig(
                positive=cfg.pseudo_label.positive,
                negative=cfg.pseudo_label.negative,
                min_confidence_std=cfg.pseudo_label.min_confidence_std,
                min_confidence_span=cfg.pseudo_label.min_confidence_span,
            )
        ),
        "config": config_to_dict(cfg),
        "selected_model": {
            "name": selected["name"],
            "calibration_method": selected_method,
        },
        "benchmark": benchmark_summary,
        "metrics": {
            "cv": cv_metrics,
            "holdout": selected["metrics"],
        },
    }


def save_model_bundle(bundle, path=DEFAULT_MODEL_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)


def load_model_bundle(path=DEFAULT_MODEL_PATH):
    return joblib.load(path)


def model_features(bundle):
    model = bundle.get("model")
    if model is not None and hasattr(model, "feature_order_"):
        return list(model.feature_order_)
    return list(bundle.get("features", MODEL_FEATURES))


def extract_feature_importances(bundle):
    pipeline = bundle["model"]
    features = model_features(bundle)
    calibrated = pipeline.named_steps["clf"]
    estimators = []

    if hasattr(calibrated, "calibrated_classifiers_"):
        for calibrated_model in calibrated.calibrated_classifiers_:
            estimator = None
            for attr in ("estimator", "base_estimator", "classifier"):
                estimator = getattr(calibrated_model, attr, None)
                if estimator is not None:
                    break
            if estimator is not None and hasattr(estimator, "feature_importances_"):
                estimators.append(estimator.feature_importances_)

    if hasattr(calibrated, "feature_importances_"):
        estimators.append(calibrated.feature_importances_)

    if not estimators:
        raise ValueError("Feature importances are unavailable for the current model bundle.")

    averaged = np.mean(np.vstack(estimators), axis=0)
    return pd.Series(averaged, index=features)


def bundle_evaluation_summary(bundle):
    model_kind = str(bundle.get("model_kind") or "classification").strip().lower()
    selected_model = bundle.get("selected_model", {})
    holdout = (bundle.get("metrics") or {}).get("holdout", {})
    diagnostic_flags: list[str] = []
    warnings: list[str] = []
    if model_kind == "classification":
        if float(holdout.get("exact_confidence_rate_raw", 0.0) or 0.0) >= 0.5:
            diagnostic_flags.append("confidence_saturation")
            warnings.append("A large share of raw holdout probabilities saturated at exactly 0 or 1.")
        if float(holdout.get("balanced_accuracy", 0.0) or 0.0) < 0.6:
            warnings.append("Holdout balanced accuracy is currently below 0.60.")
    else:
        if float(holdout.get("r2", 0.0) or 0.0) < 0.0:
            warnings.append("Holdout R^2 is currently below 0, so regression generalization is weak.")
        if float(holdout.get("rmse", 0.0) or 0.0) <= 0.0:
            diagnostic_flags.append("degenerate_regression_error")

    payload = {
        "schema_version": "training_result.v1",
        "model_family": "random_forest",
        "model_type": model_kind,
        "calibration_method": selected_model.get("calibration_method") or "",
        "training_scope": bundle.get("training_scope") or "",
        "model_source": bundle.get("model_source") or "",
        "training_sample_size": int(bundle.get("training_sample_size", 0) or 0),
        "class_balance": bundle.get("class_balance") or {"positive": 0, "negative": 0, "unlabeled": 0},
        "evaluation_metrics": bundle.get("metrics", {}),
        "regression_metrics": bundle.get("regression_metrics", {}),
        "warnings": warnings,
        "diagnostic_flags": diagnostic_flags,
        "artifact_refs": bundle.get("artifact_refs", {}),
        "selected_model": bundle.get("selected_model", {}),
        "target_definition": bundle.get("target_definition", {}) or {},
        "contract_versions": bundle.get("contract_versions", {}) or {},
        "benchmark": bundle.get("benchmark", []),
        "metrics": bundle.get("metrics", {}),
        "thresholds": bundle.get("thresholds", {}),
        "config": bundle.get("config", {}),
    }
    return validate_training_result(payload)


__all__ = [
    "DEFAULT_EVALUATION_PATH",
    "DEFAULT_MODEL_PATH",
    "benchmark_model_candidates",
    "build_model",
    "bundle_evaluation_summary",
    "calibration_cv_splits",
    "clip_probabilities",
    "ensure_training_labels",
    "evaluation_summary",
    "extract_feature_importances",
    "holdout_metrics",
    "load_model_bundle",
    "log_distribution",
    "model_features",
    "per_class_probability_summary",
    "quantile_summary",
    "save_model_bundle",
    "summarize_series",
    "train_model",
]
