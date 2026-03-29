from models.uncertainty import compute_uncertainty
from system.services.prediction_service import align_features
from system.services.runtime_config import resolve_system_config
from system.services.training_service import clip_probabilities


def predict(model, X, feature_contract, config=None):
    cfg = resolve_system_config(config)
    aligned = align_features(X, feature_contract)
    probs = clip_probabilities(model.predict_proba(aligned)[:, 1], cfg.model.probability_clip)
    uncertainty = compute_uncertainty(probs)
    return probs, uncertainty
