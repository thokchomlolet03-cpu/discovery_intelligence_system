from __future__ import annotations

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


def predict_with_model(bundle, df, config=None):
    cfg = resolve_system_config(config or bundle.get("config"))
    model = bundle["model"]
    features = model_features(bundle)
    scored = df.copy()
    X = align_features(scored, features)
    raw_probs = model.predict_proba(X)[:, 1]
    probs = clip_probabilities(raw_probs, cfg.model.probability_clip)

    scored["confidence"] = probs
    scored["uncertainty"] = 1.0 - (abs(probs - 0.5) * 2.0)
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

