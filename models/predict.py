from models.uncertainty import compute_uncertainty
from pipeline_utils import align_features, clip_probabilities, resolve_system_config


def predict(model, X, feature_contract, config=None):
    cfg = resolve_system_config(config)
    aligned = align_features(X, feature_contract)
    probs = clip_probabilities(model.predict_proba(aligned)[:, 1], cfg.model.probability_clip)
    uncertainty = compute_uncertainty(probs)
    return probs, uncertainty

