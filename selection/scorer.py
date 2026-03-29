from models.uncertainty import compute_uncertainty
from system.services.runtime_config import resolve_system_config


def score_candidates(df, config=None):
    cfg = resolve_system_config(config)
    scored = df.copy()
    if "uncertainty" not in scored.columns and "confidence" in scored.columns:
        scored["uncertainty"] = compute_uncertainty(scored["confidence"])
    if "novelty" not in scored.columns:
        scored["novelty"] = 0.0
    scored["score"] = (
        cfg.acquisition.w_conf * scored["confidence"]
        + cfg.acquisition.w_novelty * scored["novelty"]
        + cfg.acquisition.w_uncertainty * scored["uncertainty"]
    )
    scored["final_score"] = scored["score"]
    return scored
