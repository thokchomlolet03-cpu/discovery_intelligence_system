from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from decision.decision_engine import build_decision_package
from experiment.suggest import suggest_experiments
from experiment.value_function import compute_experiment_value
from features.rdkit_features import build_features
from filters.feasibility import annotate_feasibility
from generation.guided_generator import generate_candidate_artifacts
from models.predict import predict
from models.train_model import train_model as train_modular_model
from selection.scorer import score_candidates
from selection.selector import select_candidates
from system.services.candidate_service import candidate_similarity_table
from system.services.data_service import labeled_subset, reference_smiles_from_dataset
from system.services.decision_service import decorate_candidates
from system.services.prediction_service import predict_with_model
from system.services.training_service import load_model_bundle


def build_discovery_result(
    df: pd.DataFrame,
    summary: dict[str, Any],
    config,
    seed: int,
    session_id: str,
    source_name: str,
    intent: str,
    scoring_mode: str,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    labeled_df = labeled_subset(df)
    X_train, clean_labeled = build_features(labeled_df)
    model, feature_contract, bundle = train_modular_model(
        X_train,
        clean_labeled["biodegradable"].astype(int),
        config=config,
        random_state=seed,
    )

    generated, processed = generate_candidate_artifacts(df, n=config.loop.candidates_per_round, config=config, seed=seed)
    processed = annotate_feasibility(processed, config=config)
    feasible = processed[processed["is_feasible"]].copy()

    if feasible.empty:
        decision = build_decision_package(feasible, iteration=1, config=config, session_id=session_id)
        result = {
            "mode": "discovery",
            "message": "No feasible candidate molecules were generated from this upload.",
            "summary": summary,
            "top_candidates": [],
            "decision_output": decision,
        }
        return result, generated, processed, feasible, bundle

    candidate_features, feasible = build_features(feasible, feature_contract=feature_contract)
    confidence, uncertainty = predict(model, candidate_features, feature_contract, config=config)

    scored = feasible.copy()
    scored["confidence"] = confidence
    scored["uncertainty"] = uncertainty
    scored = score_candidates(scored, config=config)
    scored["experiment_value"] = scored.apply(lambda row: compute_experiment_value(row, config=config), axis=1)
    scored = select_candidates(scored, min(config.loop.candidates_per_round, len(scored)), config=config)
    scored = decorate_candidates(scored, mode="discovery", source_name=source_name, bundle=bundle, intent=intent, scoring_mode=scoring_mode)

    suggested = suggest_experiments(scored, top_k=min(config.decision.top_k, len(scored)), config=config)
    decision = build_decision_package(scored, iteration=1, config=config, session_id=session_id)

    result = {
        "mode": "discovery",
        "message": "Generated new candidate suggestions from the uploaded labeled dataset.",
        "summary": {
            **summary,
            "generated_candidates": int(len(generated)),
            "processed_candidates": int(len(processed)),
            "feasible_candidates": int(len(scored)),
        },
        "top_candidates": decision.get("top_experiments", []),
        "decision_output": decision,
        "suggested_candidates": suggested[
            ["candidate_id", "smiles", "confidence", "uncertainty", "novelty", "experiment_value", "priority_score"]
        ].head(config.decision.top_k).to_dict("records"),
    }
    return result, generated, processed, scored, bundle


def build_prediction_result(
    df: pd.DataFrame,
    summary: dict[str, Any],
    config,
    seed: int,
    session_id: str,
    source_name: str,
    intent: str,
    scoring_mode: str,
    allow_session_training: bool,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any] | None]:
    bundle = None
    reference = reference_smiles_from_dataset()
    novelty_ready = candidate_similarity_table(df.copy(), reference_smiles=reference, config=config)
    novelty_ready = annotate_feasibility(novelty_ready, config=config)
    feasible = novelty_ready[novelty_ready["is_feasible"]].copy()

    if feasible.empty:
        decision = build_decision_package(feasible, iteration=1, config=config, session_id=session_id)
        result = {
            "mode": "prediction",
            "message": "No feasible molecules were available to score from this upload.",
            "summary": summary,
            "top_candidates": [],
            "decision_output": decision,
        }
        return result, feasible, bundle

    if allow_session_training:
        labeled_df = labeled_subset(df)
        X_train, clean_labeled = build_features(labeled_df)
        model, feature_contract, bundle = train_modular_model(
            X_train,
            clean_labeled["biodegradable"].astype(int),
            config=config,
            random_state=seed,
        )
        candidate_features, feasible = build_features(feasible, feature_contract=feature_contract)
        confidence, uncertainty = predict(model, candidate_features, feature_contract, config=config)
        scored = feasible.copy()
        scored["confidence"] = confidence
        scored["uncertainty"] = uncertainty
    else:
        model_path = Path("rf_model_v1.joblib")
        if not model_path.exists():
            raise ValueError(
                "Upload contains no usable labels for session training, and no trained model bundle was found at rf_model_v1.joblib."
            )
        bundle = load_model_bundle(model_path)
        _, clean_features = build_features(feasible, feature_contract=bundle.get("features"))
        scored = predict_with_model(bundle, clean_features, config=bundle.get("config"))

    scored = score_candidates(scored, config=config)
    scored["experiment_value"] = scored.apply(lambda row: compute_experiment_value(row, config=config), axis=1)
    scored = decorate_candidates(scored, mode="prediction", source_name=source_name, bundle=bundle, intent=intent, scoring_mode=scoring_mode)
    decision = build_decision_package(scored, iteration=1, config=config, session_id=session_id)

    result = {
        "mode": "prediction",
        "message": "Ranked uploaded molecules for review using the current scoring workflow.",
        "summary": {
            **summary,
            "scored_candidates": int(len(scored)),
        },
        "top_candidates": decision.get("top_experiments", []),
        "decision_output": decision,
    }
    return result, scored, bundle


__all__ = ["build_discovery_result", "build_prediction_result"]
