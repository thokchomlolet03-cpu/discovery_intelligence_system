from __future__ import annotations

import numpy as np
import pandas as pd

from system.services.runtime_config import resolve_system_config
from system.services.training_service import clip_probabilities, model_features


def align_features(df, features):
    aligned = df.reindex(columns=features).copy()
    missing = [feature for feature in features if feature not in df.columns]
    extra = [col for col in df.columns if str(col).startswith("fp_") and col not in features]
    aligned = aligned.fillna(0).astype(float)
    if missing:
        print(f"Feature alignment: filled {len(missing)} missing columns with 0")
    if extra:
        print(f"Feature alignment: ignored {len(extra)} extra fingerprint columns")
    return aligned


def _classification_ensemble_statistics(bundle, X):
    pipeline = bundle["model"]
    scaler = pipeline.named_steps["scaler"]
    calibrated = pipeline.named_steps["clf"]
    transformed = scaler.transform(X)
    prediction_sets = []

    if hasattr(calibrated, "calibrated_classifiers_"):
        for calibrated_model in calibrated.calibrated_classifiers_:
            estimator = None
            for attr in ("estimator", "base_estimator", "classifier"):
                estimator = getattr(calibrated_model, attr, None)
                if estimator is not None:
                    break
            if estimator is None:
                continue
            if hasattr(estimator, "predict_proba"):
                prediction_sets.append(estimator.predict_proba(transformed)[:, 1])
            elif hasattr(estimator, "predict"):
                prediction_sets.append(np.asarray(estimator.predict(transformed), dtype=float))

    if not prediction_sets and hasattr(calibrated, "predict_proba"):
        prediction_sets.append(calibrated.predict_proba(transformed)[:, 1])

    if not prediction_sets:
        zeros = np.zeros(len(X), dtype=float)
        return zeros, zeros, np.ones(len(X), dtype=float)

    stacked = np.vstack(prediction_sets)
    mean_prediction = stacked.mean(axis=0)
    dispersion = stacked.std(axis=0)
    agreement = 1.0 - np.clip(dispersion / 0.25, 0.0, 1.0)
    return mean_prediction, dispersion, agreement


def predict_with_model(bundle, df, config=None):
    if str(bundle.get("model_kind") or "").strip().lower() == "regression":
        from system.services.regression_service import predict_regression_with_model

        return predict_regression_with_model(
            bundle,
            df,
            optimization_direction=str((bundle.get("target_definition") or {}).get("optimization_direction") or "hit_range"),
        )

    cfg = resolve_system_config(config or bundle.get("config"))
    model = bundle["model"]
    features = model_features(bundle)
    scored = df.copy()
    X = align_features(scored, features)
    raw_probs = model.predict_proba(X)[:, 1]
    probs = clip_probabilities(raw_probs, cfg.model.probability_clip)
    ensemble_mean, ensemble_dispersion, ensemble_agreement = _classification_ensemble_statistics(bundle, X)
    margin_uncertainty = 1.0 - (abs(probs - 0.5) * 2.0)
    disagreement_uncertainty = np.clip(ensemble_dispersion / 0.20, 0.0, 1.0)

    scored["confidence"] = probs
    scored["uncertainty"] = np.clip((0.65 * margin_uncertainty) + (0.35 * disagreement_uncertainty), 0.0, 1.0)
    scored["margin_uncertainty"] = margin_uncertainty
    scored["ensemble_probability_mean"] = ensemble_mean
    scored["ensemble_probability_std"] = ensemble_dispersion
    scored["ensemble_agreement"] = ensemble_agreement
    scored["signal_support"] = np.clip((0.6 * (1.0 - scored["uncertainty"])) + (0.4 * ensemble_agreement), 0.0, 1.0)
    if "novelty" not in scored.columns:
        scored["novelty"] = pd.to_numeric(scored.get("novel_to_dataset", 0), errors="coerce").fillna(0)
    else:
        scored["novelty"] = pd.to_numeric(scored["novelty"], errors="coerce").fillna(0)
    scored["final_score"] = (
        cfg.acquisition.w_conf * scored["confidence"]
        + cfg.acquisition.w_novelty * scored["novelty"]
        + cfg.acquisition.w_uncertainty * scored["uncertainty"]
    )
    return scored


__all__ = ["align_features", "predict_with_model"]
