from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import default_system_config
from core.constants import DECISION_OUTPUT_PATH, preferred_data_path
from decision.decision_engine import build_decision_package, risk_level
from experiment.suggest import suggest_experiments
from experiment.value_function import compute_experiment_value
from features.rdkit_features import build_features
from filters.feasibility import annotate_feasibility
from generation.guided_generator import generate_candidate_artifacts
from models.predict import predict
from models.train_model import train_model as train_modular_model
from pipeline_utils import (
    DEFAULT_DECISION_OUTPUT_PATH,
    candidate_similarity_table,
    canonicalize_smiles,
    labeled_subset,
    load_model_bundle,
    predict_with_model,
    save_model_bundle,
    write_dataframe,
    write_evaluation_summary,
    write_json_log,
)
from selection.scorer import score_candidates
from selection.selector import select_candidates
from system.explanation_engine import add_candidate_explanations
from system.provenance import add_candidate_provenance
from system.review_manager import persist_review_queue
from system.session_report import (
    apply_priority_scores,
    apply_scoring_mode,
    build_analysis_report,
    build_upload_session_summary,
    build_warnings,
)
from system.upload_parser import apply_column_mapping, infer_column_mapping, validation_summary
from utils.artifact_writer import uploaded_session_dir, write_latest_result, write_session_report_copy
from utils.validation import raw_columns_only


USER_FEEDBACK_PATH = Path("data/user_feedback.csv")

DEFAULT_ANALYSIS_OPTIONS = {
    "session_id": None,
    "input_type": "molecules_to_screen_only",
    "intent": "rank_uploaded_molecules",
    "scoring_mode": "balanced",
    "consent_learning": False,
    "column_mapping": None,
}


def _reference_smiles() -> list[str]:
    path = preferred_data_path()
    if not path.exists():
        return []

    reference = pd.read_csv(path)
    if "smiles" not in reference.columns:
        return []
    return reference["smiles"].dropna().astype(str).tolist()


def _prepare_analysis_dataframe(
    df: pd.DataFrame,
    column_mapping: dict[str, str | None],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    mapped = apply_column_mapping(df, column_mapping)
    summary = validation_summary(df, column_mapping)

    prepared = mapped.copy()
    prepared["smiles"] = prepared["smiles"].apply(canonicalize_smiles)
    prepared = prepared[prepared["smiles"].notna()].reset_index(drop=True)
    prepared["biodegradable"] = pd.to_numeric(prepared["biodegradable"], errors="coerce").fillna(-1).astype(int)
    prepared["molecule_id"] = prepared["molecule_id"].fillna("").astype(str)
    prepared["source"] = prepared["source"].fillna("").astype(str)
    prepared["notes"] = prepared["notes"].fillna("").astype(str)

    before_dedup = len(prepared)
    prepared = prepared.drop_duplicates(subset=["smiles"], keep="first").reset_index(drop=True)
    if prepared.empty:
        raise ValueError("No valid SMILES remained after applying the selected column mapping.")
    summary["duplicate_count"] = max(int(summary.get("duplicate_count", 0)), int(before_dedup - len(prepared)))
    summary["analyzed_rows"] = int(len(prepared))
    return prepared, summary


def _queue_feedback_rows(df: pd.DataFrame, consent_learning: bool) -> dict[str, Any]:
    if not consent_learning:
        return {
            "consent_learning": False,
            "queued_rows": 0,
            "total_rows": 0,
            "path": str(USER_FEEDBACK_PATH),
            "message": "Uploaded data was kept private and was not added to the learning queue.",
        }

    feedback = raw_columns_only(df)
    feedback = feedback[feedback["biodegradable"].isin([0, 1])].copy()
    if feedback.empty:
        return {
            "consent_learning": True,
            "queued_rows": 0,
            "total_rows": 0,
            "path": str(USER_FEEDBACK_PATH),
            "message": "Learning consent was granted, but no usable labeled rows were available to queue.",
        }

    existing = pd.read_csv(USER_FEEDBACK_PATH) if USER_FEEDBACK_PATH.exists() else pd.DataFrame(columns=feedback.columns)
    combined = pd.concat([existing, feedback], ignore_index=True)
    combined = combined.drop_duplicates(subset=["smiles", "biodegradable"], keep="first")
    total_rows = int(len(combined))
    queued_rows = int(total_rows - len(existing))
    write_dataframe(USER_FEEDBACK_PATH, combined)
    return {
        "consent_learning": True,
        "queued_rows": queued_rows,
        "total_rows": total_rows,
        "path": str(USER_FEEDBACK_PATH),
        "message": "Labeled rows were added to the explicit learning queue.",
    }


def _bucketize_candidates(df: pd.DataFrame) -> pd.DataFrame:
    bucketed = df.copy()
    if "selection_bucket" not in bucketed.columns:
        bucketed["selection_bucket"] = ""

    missing = bucketed["selection_bucket"].fillna("").eq("")
    bucketed.loc[missing & (bucketed["uncertainty"] >= 0.65), "selection_bucket"] = "learn"
    bucketed.loc[missing & (bucketed["novelty"] >= 0.65), "selection_bucket"] = "explore"
    bucketed.loc[missing & (bucketed["confidence"] >= 0.75), "selection_bucket"] = "exploit"
    bucketed.loc[bucketed["selection_bucket"].fillna("").eq(""), "selection_bucket"] = "learn"
    bucketed["bucket"] = bucketed["selection_bucket"]
    return bucketed


def _assign_candidate_identifiers(df: pd.DataFrame) -> pd.DataFrame:
    assigned = df.copy()
    if "candidate_id" not in assigned.columns:
        assigned["candidate_id"] = ""
    if "molecule_id" in assigned.columns:
        assigned["candidate_id"] = assigned["candidate_id"].where(assigned["candidate_id"].astype(str).ne(""), assigned["molecule_id"])
    if "polymer" in assigned.columns:
        assigned["candidate_id"] = assigned["candidate_id"].where(assigned["candidate_id"].astype(str).ne(""), assigned["polymer"])
    assigned["candidate_id"] = assigned["candidate_id"].where(
        assigned["candidate_id"].astype(str).ne(""),
        pd.Series([f"candidate_{idx + 1}" for idx in range(len(assigned))]),
    )
    return assigned


def _out_of_domain_ratio(df: pd.DataFrame, config) -> float | None:
    reference = _reference_smiles()
    if not reference or df.empty:
        return None
    novelty_frame = candidate_similarity_table(df[["smiles"]].copy(), reference_smiles=reference, config=config)
    if "max_similarity" not in novelty_frame.columns or novelty_frame.empty:
        return None
    similarities = pd.to_numeric(novelty_frame["max_similarity"], errors="coerce").fillna(0.0)
    return float((similarities < 0.25).mean())


def _persist_artifacts(
    run_id: str,
    upload_df: pd.DataFrame,
    result: dict[str, Any],
    generated: pd.DataFrame | None = None,
    processed: pd.DataFrame | None = None,
    scored: pd.DataFrame | None = None,
    bundle: dict[str, Any] | None = None,
    expose_latest: bool = False,
) -> dict[str, str]:
    run_dir = uploaded_session_dir(run_id, create=True)

    artifact_paths = {
        "run_dir": str(run_dir),
        "upload_csv": str(run_dir / "uploaded_dataset.csv"),
        "result_json": str(run_dir / "result.json"),
    }

    write_dataframe(run_dir / "uploaded_dataset.csv", upload_df)
    write_json_log(run_dir / "result.json", result)

    if expose_latest:
        artifact_paths["latest_result_json"] = write_latest_result(result)

    if generated is not None:
        artifact_paths["generated_candidates_csv"] = str(run_dir / "generated_candidates.csv")
        write_dataframe(run_dir / "generated_candidates.csv", generated)

    if processed is not None:
        artifact_paths["processed_candidates_csv"] = str(run_dir / "processed_candidates.csv")
        write_dataframe(run_dir / "processed_candidates.csv", processed)

    if scored is not None:
        artifact_paths["scored_candidates_csv"] = str(run_dir / "scored_candidates.csv")
        write_dataframe(run_dir / "scored_candidates.csv", scored)

    if bundle is not None:
        artifact_paths["model_bundle"] = str(run_dir / "rf_model_v1.joblib")
        artifact_paths["evaluation_summary"] = str(run_dir / "evaluation_summary.json")
        save_model_bundle(bundle, run_dir / "rf_model_v1.joblib")
        write_evaluation_summary(run_dir / "evaluation_summary.json", bundle)

    if result.get("decision_output"):
        artifact_paths["decision_output_json"] = str(run_dir / "decision_output.json")
        write_json_log(run_dir / "decision_output.json", result["decision_output"])

    if result.get("upload_session_summary"):
        artifact_paths["upload_session_summary_json"] = str(run_dir / "upload_session_summary.json")
        write_json_log(run_dir / "upload_session_summary.json", result["upload_session_summary"])
        artifact_paths["upload_session_summary_report_json"] = write_session_report_copy(
            run_id,
            "upload_session_summary.json",
            result["upload_session_summary"],
        )

    if result.get("analysis_report"):
        artifact_paths["analysis_report_json"] = str(run_dir / "analysis_report.json")
        write_json_log(run_dir / "analysis_report.json", result["analysis_report"])
        artifact_paths["analysis_report_copy_json"] = write_session_report_copy(
            run_id,
            "analysis_report.json",
            result["analysis_report"],
        )

    return artifact_paths


def _decorate_candidates(
    frame: pd.DataFrame,
    mode: str,
    source_name: str,
    bundle: dict[str, Any] | None,
    intent: str,
    scoring_mode: str,
) -> pd.DataFrame:
    decorated = _assign_candidate_identifiers(_bucketize_candidates(frame))
    decorated["risk_level"] = decorated.apply(lambda row: risk_level(row), axis=1)
    decorated["risk"] = decorated["risk_level"]
    decorated = apply_priority_scores(decorated, intent=intent, scoring_mode=scoring_mode)
    decorated = add_candidate_explanations(decorated)
    decorated = add_candidate_provenance(decorated, mode=mode, source_name=source_name, bundle=bundle)
    decorated["accepted_for_feedback"] = decorated.get("accepted_for_feedback", True)
    return decorated


def _build_discovery_result(
    df: pd.DataFrame,
    summary: dict[str, Any],
    config,
    seed: int,
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
        result = {
            "mode": "discovery",
            "message": "No feasible candidate molecules were generated from this upload.",
            "summary": summary,
            "top_candidates": [],
            "decision_output": {
                "iteration": 1,
                "summary": {"top_k": 0, "candidate_count": 0, "risk_counts": {}, "top_experiment_value": 0.0},
                "top_experiments": [],
            },
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
    scored = _decorate_candidates(scored, mode="discovery", source_name=source_name, bundle=bundle, intent=intent, scoring_mode=scoring_mode)

    suggested = suggest_experiments(scored, top_k=min(config.decision.top_k, len(scored)), config=config)
    decision = build_decision_package(scored, iteration=1, config=config)

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


def _build_prediction_result(
    df: pd.DataFrame,
    summary: dict[str, Any],
    config,
    seed: int,
    source_name: str,
    intent: str,
    scoring_mode: str,
    allow_session_training: bool,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any] | None]:
    bundle = None
    reference = _reference_smiles()
    novelty_ready = candidate_similarity_table(df.copy(), reference_smiles=reference, config=config)
    novelty_ready = annotate_feasibility(novelty_ready, config=config)
    feasible = novelty_ready[novelty_ready["is_feasible"]].copy()

    if feasible.empty:
        result = {
            "mode": "prediction",
            "message": "No feasible molecules were available to score from this upload.",
            "summary": summary,
            "top_candidates": [],
            "decision_output": {
                "iteration": 1,
                "summary": {"top_k": 0, "candidate_count": 0, "risk_counts": {}, "top_experiment_value": 0.0},
                "top_experiments": [],
            },
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
    scored = _decorate_candidates(scored, mode="prediction", source_name=source_name, bundle=bundle, intent=intent, scoring_mode=scoring_mode)
    decision = build_decision_package(scored, iteration=1, config=config)

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


def run_pipeline(
    df: pd.DataFrame,
    persist_artifacts: bool = False,
    update_discovery_snapshot: bool = False,
    seed: int = 42,
    source_name: str | None = None,
    analysis_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options = {**DEFAULT_ANALYSIS_OPTIONS, **(analysis_options or {})}
    source_name = source_name or "uploaded_dataset.csv"
    column_mapping = options.get("column_mapping") or infer_column_mapping(list(df.columns))
    prepared, summary = _prepare_analysis_dataframe(df, column_mapping)

    scoring_mode, config = apply_scoring_mode(default_system_config(seed=seed), options.get("scoring_mode"))
    session_id = options.get("session_id") or options.get("run_id") or options.get("session") or prepared.attrs.get("session_id")
    if not session_id:
        session_id = options.get("session_id") or options.get("run_id") or options.get("session") or options.get("source_session")
    if not session_id:
        session_id = options.get("source_name_override") or prepared.attrs.get("generated_session_id")
    if not session_id:
        from system.upload_parser import session_id_now

        session_id = session_id_now()

    input_type = str(options.get("input_type") or "molecules_to_screen_only")
    intent = str(options.get("intent") or "rank_uploaded_molecules")
    consent_learning = bool(options.get("consent_learning"))
    product_tier = str(options.get("product_tier") or "standard")

    out_of_domain_ratio = _out_of_domain_ratio(prepared, config=config)
    labeled = labeled_subset(prepared)
    class_count = int(labeled["biodegradable"].nunique()) if not labeled.empty else 0
    min_class_count = int(labeled["biodegradable"].value_counts().min()) if not labeled.empty else 0
    session_training_available = class_count >= 2 and min_class_count >= 2

    if intent == "generate_candidates" and session_training_available:
        result, generated, processed, scored, bundle = _build_discovery_result(
            prepared,
            summary,
            config,
            seed,
            source_name,
            intent,
            scoring_mode,
        )
    else:
        result, scored, bundle = _build_prediction_result(
            prepared,
            summary,
            config,
            seed,
            source_name,
            intent,
            scoring_mode,
            allow_session_training=session_training_available,
        )
        generated = None
        processed = None

    mean_uncertainty = None
    if not scored.empty and "uncertainty" in scored.columns:
        mean_uncertainty = float(pd.to_numeric(scored["uncertainty"], errors="coerce").fillna(0.0).head(10).mean())

    warnings = build_warnings(
        summary,
        scoring_mode=scoring_mode,
        intent=intent,
        out_of_domain_ratio=out_of_domain_ratio,
        mean_uncertainty=mean_uncertainty,
    )
    if intent == "generate_candidates" and not session_training_available:
        warnings.append("The upload did not contain enough labeled examples per class for session-trained candidate generation, so the run fell back to ranking uploaded molecules.")
    session_summary = build_upload_session_summary(
        session_id=session_id,
        source_name=source_name,
        input_type=input_type,
        column_mapping=column_mapping,
        validation=summary,
        intent=intent,
        scoring_mode=scoring_mode,
        consent_learning=consent_learning,
        warnings=warnings,
        product_tier=product_tier,
    )
    analysis_report = build_analysis_report(
        validation=summary,
        scoring_mode=scoring_mode,
        intent=intent,
        consent_learning=consent_learning,
        top_candidates=result.get("top_candidates", []),
        warnings=warnings,
        product_tier=product_tier,
    )

    result["run_id"] = session_id
    result["session_id"] = session_id
    result["product_tier"] = product_tier
    result["source_name"] = source_name
    result["input_type"] = input_type
    result["intent"] = intent
    result["scoring_mode"] = scoring_mode
    result["warnings"] = warnings
    result["upload_session_summary"] = session_summary
    result["analysis_report"] = analysis_report
    result["discovery_url"] = f"/discovery?session_id={session_id}"
    result["dashboard_url"] = f"/dashboard?session_id={session_id}"

    feedback_store = _queue_feedback_rows(prepared, consent_learning=consent_learning)
    result["feedback_store"] = feedback_store

    if result.get("decision_output"):
        result["decision_output"]["input_type"] = input_type
        result["decision_output"]["intent"] = intent
        result["decision_output"]["mode_used"] = scoring_mode
        result["decision_output"]["product_tier"] = product_tier
        result["decision_output"]["warnings"] = warnings

    review_queue = persist_review_queue(result.get("top_candidates", []), session_id=session_id)
    result["review_queue"] = review_queue

    artifacts = (
        _persist_artifacts(
            session_id,
            prepared,
            result,
            generated=generated,
            processed=processed,
            scored=scored,
            bundle=bundle,
            expose_latest=consent_learning,
        )
        if persist_artifacts
        else {}
    )
    result["artifacts"] = artifacts

    if persist_artifacts:
        write_json_log(Path(artifacts["result_json"]), result)
        if artifacts.get("latest_result_json"):
            write_json_log(Path(artifacts["latest_result_json"]), result)

    if update_discovery_snapshot and result.get("decision_output") and consent_learning:
        write_json_log(DEFAULT_DECISION_OUTPUT_PATH, result["decision_output"])
        write_json_log(DECISION_OUTPUT_PATH, result["decision_output"])

    return result
