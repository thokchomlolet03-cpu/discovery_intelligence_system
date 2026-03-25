from models.uncertainty import compute_uncertainty
from experiment.value_function import compute_experiment_value


def suggest_experiments(df, top_k=10, config=None):
    ranked = df.copy()
    if "uncertainty" not in ranked.columns and "confidence" in ranked.columns:
        ranked["uncertainty"] = compute_uncertainty(ranked["confidence"])
    if "novelty" not in ranked.columns:
        ranked["novelty"] = 0.0
    if "experiment_value" not in ranked.columns:
        ranked["experiment_value"] = ranked.apply(lambda row: compute_experiment_value(row, config=config), axis=1)
    return ranked.sort_values(
        ["experiment_value", "uncertainty", "novelty"],
        ascending=[False, False, False],
    ).head(top_k)
