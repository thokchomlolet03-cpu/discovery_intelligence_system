import argparse
import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

from core.constants import DECISION_OUTPUT_PATH, KNOWLEDGE_PATH, LOGS_PATH
from core.config import default_system_config
from decision.decision_engine import build_decision_package, risk_level
from experiment.suggest import suggest_experiments
from experiment.value_function import compute_experiment_value
from features.rdkit_features import build_features
from filters.feasibility import annotate_feasibility
from generation.guided_generator import generate_candidate_artifacts
from models.predict import predict
from models.train_model import train_model as train_modular_model
from pipeline_utils import (
    DEFAULT_CANDIDATE_PATH,
    DEFAULT_DECISION_OUTPUT_PATH,
    DEFAULT_EVALUATION_PATH,
    DEFAULT_GENERATED_CANDIDATE_PATH,
    DEFAULT_ITERATION_HISTORY_PATH,
    DEFAULT_LABELED_CANDIDATE_PATH,
    DEFAULT_LOG_PATH,
    DEFAULT_MODEL_PATH,
    DEFAULT_PREDICTED_CANDIDATE_PATH,
    DEFAULT_PROCESSED_CANDIDATE_PATH,
    DEFAULT_RESULTS_PATH,
    DEFAULT_REVIEW_QUEUE_PATH,
    DEFAULT_RUN_CONFIG_PATH,
    append_feedback_to_dataset,
    labeled_subset,
    load_dataset,
    pseudo_label_candidates,
    save_model_bundle,
    selection_counts,
    write_dataframe,
    write_evaluation_summary,
    write_iteration_history,
    write_json_log,
    write_run_config,
)
from reasoning.explain import explain_prediction
from selection.scorer import score_candidates
from selection.selector import select_candidates
from utils.io import save_knowledge_entries


def parse_args():
    parser = argparse.ArgumentParser(description="Run the modular discovery intelligence evolution loop")
    parser.add_argument("--data-path", default="data.csv", help="Input dataset CSV path")
    parser.add_argument("--output-dir", default=".", help="Directory for generated artifacts")
    parser.add_argument("--iterations", type=int, default=None, help="Override number of loop iterations")
    parser.add_argument("--candidates-per-round", type=int, default=None, help="Override number of selected candidates")
    parser.add_argument("--feedback-per-class", type=int, default=None, help="Override confident additions per class")
    parser.add_argument("--seed", type=int, default=42, help="Base random seed")
    parser.add_argument("--dry-run", action="store_true", help="Produce artifacts without writing back to data.csv")
    return parser.parse_args()


def output_path(output_dir, relative_path):
    return Path(output_dir) / Path(relative_path)


def rejection_counts(df):
    if df.empty or "rejection_reason" not in df.columns:
        return {}
    rejected = df[df["rejection_reason"].fillna("") != ""]
    if rejected.empty:
        return {}
    return {str(key): int(value) for key, value in rejected["rejection_reason"].value_counts().items()}


def feasibility_rejections(df):
    if df.empty or "is_feasible" not in df.columns:
        return {}
    rejected = df[~df["is_feasible"].fillna(False)]
    if rejected.empty:
        return {}
    return {str(key): int(value) for key, value in rejected["feasibility_reason"].value_counts().items()}


def build_knowledge_entries(df, iteration):
    entries = []
    for _, row in df.iterrows():
        entries.append(
            {
                "smiles": row["smiles"],
                "prediction": int(float(row.get("confidence", 0.5)) >= 0.5),
                "confidence": float(row.get("confidence", 0.0)),
                "explanation": row.get("explanation", ""),
                "iteration": int(iteration),
            }
        )
    return entries


def empty_decision_package(iteration, top_k):
    return {
        "iteration": int(iteration),
        "summary": {
            "top_k": int(top_k),
            "candidate_count": 0,
            "risk_counts": {},
            "top_experiment_value": 0.0,
        },
        "top_experiments": [],
    }


def main(
    iterations=3,
    candidates_per_round=30,
    feedback_per_class=5,
    data_path="data.csv",
    output_dir=".",
    seed=42,
    dry_run=False,
):
    print("Starting modular discovery system")
    output_dir = Path(output_dir)
    config = default_system_config(seed=seed)
    config = replace(
        config,
        loop=replace(
            config.loop,
            iterations=iterations,
            candidates_per_round=candidates_per_round,
            feedback_per_class=feedback_per_class,
            dry_run=dry_run,
        ),
    )

    dataset = load_dataset(data_path)
    run_log = []
    review_frames = []

    write_run_config(output_path(output_dir, DEFAULT_RUN_CONFIG_PATH), config)

    for iteration in range(1, config.loop.iterations + 1):
        print(f"\nIteration {iteration}")
        print("Current labels:")
        print(dataset["biodegradable"].value_counts(dropna=False))

        labeled_dataset = labeled_subset(dataset)
        if labeled_dataset["biodegradable"].nunique() < 2:
            print("Skipping iteration because both classes are not available for training")
            continue

        iteration_seed = config.loop.seed + iteration - 1
        X_train, clean_labeled = build_features(labeled_dataset)
        model, feature_contract, bundle = train_modular_model(
            X_train,
            clean_labeled["biodegradable"].astype(int),
            config=config,
            random_state=iteration_seed,
        )

        save_model_bundle(bundle, output_path(output_dir, DEFAULT_MODEL_PATH))
        write_evaluation_summary(output_path(output_dir, DEFAULT_EVALUATION_PATH), bundle)

        generated, processed = generate_candidate_artifacts(
            dataset,
            config.loop.candidates_per_round,
            config=config,
            seed=iteration_seed,
        )
        processed = annotate_feasibility(processed, config=config)
        feasible_processed = processed[processed["is_feasible"]].copy()
        infeasible_count = int((~processed["is_feasible"]).sum()) if "is_feasible" in processed.columns else 0
        feasible_count = int(feasible_processed["is_feasible"].sum()) if "is_feasible" in feasible_processed.columns else int(len(feasible_processed))

        if feasible_processed.empty:
            scored = feasible_processed.copy()
            scored["confidence"] = pd.Series(dtype=float)
            scored["uncertainty"] = pd.Series(dtype=float)
            scored["experiment_value"] = pd.Series(dtype=float)
            scored["risk_level"] = pd.Series(dtype="object")
            scored["accepted_for_feedback"] = pd.Series(dtype=bool)
            scored["selection_bucket"] = pd.Series(dtype="object")
            scored["selection_reason"] = pd.Series(dtype="object")
            scored["explanation"] = pd.Series(dtype="object")
            labeled = pseudo_label_candidates(scored, thresholds=bundle.get("thresholds"), config=config)
            decision = empty_decision_package(iteration, config.decision.top_k)
            suggested = scored.copy()
        else:
            candidate_features, feasible_processed = build_features(feasible_processed, feature_contract=feature_contract)
            confidence, uncertainty = predict(model, candidate_features, feature_contract, config=config)

            scored = feasible_processed.copy()
            scored["confidence"] = confidence
            scored["uncertainty"] = uncertainty
            scored = score_candidates(scored, config=config)
            scored["experiment_value"] = scored.apply(lambda row: compute_experiment_value(row, config=config), axis=1)
            scored["risk_level"] = scored.apply(lambda row: risk_level(row, config=config), axis=1)
            scored = select_candidates(scored, config.loop.candidates_per_round, config=config)
            scored["explanation"] = scored.apply(explain_prediction, axis=1)

            decision = build_decision_package(scored, iteration=iteration, config=config)
            labeled = pseudo_label_candidates(scored, thresholds=bundle.get("thresholds"), config=config)
            suggested = suggest_experiments(
                scored,
                top_k=min(config.decision.top_k, len(scored)),
                config=config,
            )

        review_queue = labeled[labeled["review_candidate"]].copy()
        review_queue["iteration"] = iteration
        feedback = labeled[labeled["selected_for_feedback"]].copy()
        feedback = feedback.sort_values(["confidence", "novelty"], ascending=[False, False])
        feedback = pd.concat(
            [
                feedback[feedback["pseudo_label"] == 1].head(config.loop.feedback_per_class),
                feedback[feedback["pseudo_label"] == 0].head(config.loop.feedback_per_class),
            ],
            ignore_index=True,
        )

        write_dataframe(output_path(output_dir, DEFAULT_GENERATED_CANDIDATE_PATH), generated)
        write_dataframe(output_path(output_dir, DEFAULT_CANDIDATE_PATH), processed)
        write_dataframe(output_path(output_dir, DEFAULT_PROCESSED_CANDIDATE_PATH), processed)
        write_dataframe(output_path(output_dir, DEFAULT_PREDICTED_CANDIDATE_PATH), scored)
        write_dataframe(output_path(output_dir, DEFAULT_LABELED_CANDIDATE_PATH), labeled)
        write_dataframe(output_path(output_dir, DEFAULT_RESULTS_PATH), feedback)
        write_json_log(output_path(output_dir, DEFAULT_DECISION_OUTPUT_PATH), decision)
        write_json_log(output_path(output_dir, DECISION_OUTPUT_PATH), decision)

        review_frames.append(review_queue)
        combined_review = pd.concat(review_frames, ignore_index=True) if review_frames else review_queue.iloc[0:0].copy()
        write_dataframe(output_path(output_dir, DEFAULT_REVIEW_QUEUE_PATH), combined_review)

        save_knowledge_entries(
            build_knowledge_entries(scored[scored["accepted_for_feedback"]], iteration),
            path=output_path(output_dir, KNOWLEDGE_PATH),
        )

        if not scored.empty:
            print("Confidence distribution:")
            print(scored["confidence"].describe().round(4))
            print("Uncertainty distribution:")
            print(scored["uncertainty"].describe().round(4))
        print("Feasibility summary:")
        print({"feasible": feasible_count, "infeasible": infeasible_count})
        print("Selection breakdown:")
        print(selection_counts(scored))
        print("Candidate acceptance summary:")
        print(
            {
                "generated": int(len(generated)),
                "processed": int(len(processed)),
                "feasible": feasible_count,
                "infeasible": infeasible_count,
                "selected": int(scored["accepted_for_feedback"].sum()) if "accepted_for_feedback" in scored.columns else 0,
                "review_queue": int(len(review_queue)),
                "feedback_rows": int(len(feedback)),
            }
        )
        rejections = rejection_counts(generated)
        if rejections:
            print("Candidate rejections:")
            print(rejections)
        feasibility_failures = feasibility_rejections(processed)
        if feasibility_failures:
            print("Feasibility rejections:")
            print(feasibility_failures)
        if decision["top_experiments"]:
            print("Top decision candidates:")
            for item in decision["top_experiments"][:5]:
                print(
                    {
                        "smiles": item["smiles"],
                        "risk": item["risk"],
                        "experiment_value": round(item["experiment_value"], 4),
                    }
                )
        elif not suggested.empty:
            print("Suggested experiments:")
            print(suggested[["polymer", "smiles", "confidence", "uncertainty", "novelty", "experiment_value"]].head(10))

        dataset_before = len(dataset)
        if dry_run:
            print("Dry run enabled; skipping dataset write-back")
            appended_feedback = 0
        else:
            dataset = append_feedback_to_dataset(dataset, feedback)
            dataset.to_csv(data_path, index=False)
            appended_feedback = max(0, len(dataset) - dataset_before)

        holdout = bundle["metrics"]["holdout"]
        record = {
            "iteration": iteration,
            "dataset_size": int(len(dataset)),
            "label_counts": {
                str(key): int(value)
                for key, value in dataset["biodegradable"].value_counts(dropna=False).items()
            },
            "selected_model": bundle["selected_model"],
            "holdout": holdout,
            "generated_candidates": int(len(generated)),
            "processed_candidates": int(len(processed)),
            "portfolio_selected": int(scored["accepted_for_feedback"].sum()) if "accepted_for_feedback" in scored.columns else 0,
            "selected_feedback": int(len(feedback)),
            "review_queue": int(len(review_queue)),
            "selection_counts": selection_counts(scored),
            "candidate_rejections": rejection_counts(generated),
            "feasibility_rejections": feasibility_failures,
            "feasible_candidates": feasible_count,
            "infeasible_candidates": infeasible_count,
            "decision_risk_counts": decision["summary"]["risk_counts"],
            "top_experiment_value": decision["summary"]["top_experiment_value"],
            "appended_feedback": int(appended_feedback),
            "dry_run": bool(dry_run),
        }
        run_log.append(record)
        write_json_log(output_path(output_dir, DEFAULT_LOG_PATH), run_log)
        write_json_log(output_path(output_dir, LOGS_PATH), run_log)
        write_iteration_history(output_path(output_dir, DEFAULT_ITERATION_HISTORY_PATH), run_log)

        print(
            "Holdout metrics:",
            json.dumps(
                {
                    "accuracy": round(holdout["accuracy"], 4),
                    "balanced_accuracy": round(holdout["balanced_accuracy"], 4),
                    "f1_macro": round(holdout["f1_macro"], 4),
                    "brier_score": round(holdout["brier_score"], 4),
                    "log_loss": round(holdout["log_loss"], 4),
                }
            ),
        )

    print("\nDone")


if __name__ == "__main__":
    args = parse_args()
    main(
        iterations=args.iterations if args.iterations is not None else 3,
        candidates_per_round=args.candidates_per_round if args.candidates_per_round is not None else 30,
        feedback_per_class=args.feedback_per_class if args.feedback_per_class is not None else 5,
        data_path=args.data_path,
        output_dir=args.output_dir,
        seed=args.seed,
        dry_run=args.dry_run,
    )
