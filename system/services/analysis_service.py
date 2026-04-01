from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

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
from system.services.data_service import labeled_subset, reference_smiles_from_dataset, regression_subset
from system.services.decision_service import decorate_candidates
from system.services.prediction_service import predict_with_model
from system.services.regression_service import train_regression_model
from system.services.training_service import load_model_bundle


ProgressCallback = Callable[[str, str, int], None]


def _emit_progress(
    progress_callback: ProgressCallback | None,
    *,
    stage: str,
    message: str,
    percent: int,
) -> None:
    if progress_callback is None:
        return
    progress_callback(stage, message, percent)


def build_discovery_result(
    df: pd.DataFrame,
    summary: dict[str, Any],
    config,
    seed: int,
    session_id: str,
    source_name: str,
    intent: str,
    scoring_mode: str,
    target_definition: dict[str, Any] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    labeled_df = labeled_subset(df)
    _emit_progress(
        progress_callback,
        stage="scoring_candidates",
        message="Building features from labeled rows for session training.",
        percent=36,
    )
    X_train, clean_labeled = build_features(labeled_df)
    _emit_progress(
        progress_callback,
        stage="scoring_candidates",
        message="Training a session-specific model from labeled rows.",
        percent=44,
    )
    model, feature_contract, bundle = train_modular_model(
        X_train,
        clean_labeled["biodegradable"].astype(int),
        config=config,
        random_state=seed,
    )
    bundle["target_definition"] = dict(target_definition or {})
    bundle["training_scope"] = "session_trained"

    _emit_progress(
        progress_callback,
        stage="scoring_candidates",
        message="Generating candidate suggestions from the uploaded dataset.",
        percent=52,
    )
    generated, processed = generate_candidate_artifacts(df, n=config.loop.candidates_per_round, config=config, seed=seed)
    _emit_progress(
        progress_callback,
        stage="scoring_candidates",
        message="Checking feasibility of generated candidates.",
        percent=58,
    )
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

    _emit_progress(
        progress_callback,
        stage="scoring_candidates",
        message="Running model inference on feasible generated candidates.",
        percent=64,
    )
    candidate_features, feasible = build_features(feasible, feature_contract=feature_contract)
    confidence, uncertainty = predict(model, candidate_features, feature_contract, config=config)

    scored = feasible.copy()
    scored["confidence"] = confidence
    scored["uncertainty"] = uncertainty
    _emit_progress(
        progress_callback,
        stage="scoring_candidates",
        message="Ranking generated candidates for scientific review.",
        percent=72,
    )
    scored = score_candidates(scored, config=config)
    scored["experiment_value"] = scored.apply(lambda row: compute_experiment_value(row, config=config), axis=1)
    scored = select_candidates(scored, min(config.loop.candidates_per_round, len(scored)), config=config)
    scored.attrs["target_definition"] = dict(target_definition or {})
    scored = decorate_candidates(
        scored,
        mode="discovery",
        source_name=source_name,
        bundle=bundle,
        intent=intent,
        scoring_mode=scoring_mode,
        target_definition=target_definition,
    )

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
    target_definition: dict[str, Any] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any] | None]:
    bundle = None
    target_definition = dict(target_definition or {})
    target_kind = str(target_definition.get("target_kind") or "classification").strip().lower()
    _emit_progress(
        progress_callback,
        stage="scoring_candidates",
        message="Checking novelty and feasibility across uploaded molecules.",
        percent=36,
    )
    reference = reference_smiles_from_dataset()
    novelty_ready = candidate_similarity_table(
        df.copy(),
        reference_smiles=reference,
        config=config,
        enforce_batch_diversity=False,
    )
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

    if target_kind == "regression":
        measured_df = regression_subset(df)
        if measured_df.empty:
            raise ValueError("This session target is configured as a continuous measurement, but no measured target values were available for regression.")
        if not allow_session_training:
            raise ValueError(
                "This session target is configured as a continuous measurement, but the upload does not contain enough measured rows for a regression model."
            )
        _emit_progress(
            progress_callback,
            stage="scoring_candidates",
            message="Training a session-specific regression model from measured rows.",
            percent=54,
        )
        bundle = train_regression_model(df, random_state=seed, config=config)
        bundle["target_definition"] = target_definition
        bundle["training_scope"] = "session_trained"
        _emit_progress(
            progress_callback,
            stage="scoring_candidates",
            message="Running regression inference on uploaded molecules.",
            percent=64,
        )
        _, clean_features = build_features(feasible, feature_contract=bundle.get("features"))
        scored = predict_with_model(bundle, clean_features, config=bundle.get("config"))
    elif allow_session_training:
        labeled_df = labeled_subset(df)
        _emit_progress(
            progress_callback,
            stage="scoring_candidates",
            message="Building features from labeled rows for session training.",
            percent=46,
        )
        X_train, clean_labeled = build_features(labeled_df)
        _emit_progress(
            progress_callback,
            stage="scoring_candidates",
            message="Training a session-specific model.",
            percent=54,
        )
        model, feature_contract, bundle = train_modular_model(
            X_train,
            clean_labeled["biodegradable"].astype(int),
            config=config,
            random_state=seed,
        )
        bundle["target_definition"] = target_definition
        bundle["training_scope"] = "session_trained"
        _emit_progress(
            progress_callback,
            stage="scoring_candidates",
            message="Running model inference on uploaded molecules.",
            percent=62,
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
        _emit_progress(
            progress_callback,
            stage="scoring_candidates",
            message="Loading the baseline model bundle.",
            percent=48,
        )
        bundle = load_model_bundle(model_path)
        bundle["target_definition"] = target_definition
        bundle["training_scope"] = "baseline_bundle"
        bundle["model_source"] = str(model_path)
        _emit_progress(
            progress_callback,
            stage="scoring_candidates",
            message="Preparing features for baseline model inference.",
            percent=58,
        )
        _, clean_features = build_features(feasible, feature_contract=bundle.get("features"))
        _emit_progress(
            progress_callback,
            stage="scoring_candidates",
            message="Running baseline model inference on uploaded molecules.",
            percent=66,
        )
        scored = predict_with_model(bundle, clean_features, config=bundle.get("config"))

    _emit_progress(
        progress_callback,
        stage="scoring_candidates",
        message="Ranking uploaded molecules for scientific review.",
        percent=72,
    )
    scored = score_candidates(scored, config=config)
    scored["experiment_value"] = scored.apply(lambda row: compute_experiment_value(row, config=config), axis=1)
    scored.attrs["target_definition"] = target_definition
    scored = decorate_candidates(
        scored,
        mode="prediction",
        source_name=source_name,
        bundle=bundle,
        intent=intent,
        scoring_mode=scoring_mode,
        target_definition=target_definition,
    )
    decision = build_decision_package(scored, iteration=1, config=config, session_id=session_id)

    result = {
        "mode": "prediction",
        "message": (
            "Ranked uploaded molecules for review using a continuous-target regression workflow."
            if target_kind == "regression"
            else "Ranked uploaded molecules for review using the current scoring workflow."
        ),
        "summary": {
            **summary,
            "scored_candidates": int(len(scored)),
        },
        "top_candidates": decision.get("top_experiments", []),
        "decision_output": decision,
    }
    return result, scored, bundle


__all__ = ["build_discovery_result", "build_prediction_result"]
