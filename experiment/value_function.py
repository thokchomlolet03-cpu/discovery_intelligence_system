from system.services.runtime_config import resolve_system_config


def compute_experiment_value(row, config=None):
    cfg = resolve_system_config(config)
    uncertainty = float(row.get("uncertainty", 0.0))
    novelty = float(row.get("novelty", 0.0))
    confidence = float(row.get("confidence", 0.0))

    return (
        cfg.decision.w_uncertainty * uncertainty
        + cfg.decision.w_novelty * novelty
        + cfg.decision.w_low_confidence * (1.0 - confidence)
    )
