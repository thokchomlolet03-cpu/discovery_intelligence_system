from __future__ import annotations

import json

import numpy as np
import pandas as pd

from system.services.runtime_config import ThresholdConfig, resolve_system_config
from system.services.training_service import summarize_series


def selection_counts(df):
    if "accepted_for_feedback" not in df.columns:
        return {}
    selected = df[df["accepted_for_feedback"]]
    if selected.empty:
        return {}
    return {str(key): int(value) for key, value in selected["selection_bucket"].value_counts().items()}


def allocate_bucket_counts(total, config=None):
    cfg = resolve_system_config(config)
    fractions = {
        "exploit": cfg.acquisition.exploit_fraction,
        "learn": cfg.acquisition.uncertainty_fraction,
        "explore": cfg.acquisition.novelty_fraction,
    }
    raw_counts = {bucket: total * weight for bucket, weight in fractions.items()}
    base_counts = {bucket: int(np.floor(value)) for bucket, value in raw_counts.items()}
    remainder = total - sum(base_counts.values())
    if remainder > 0:
        ranked = sorted(
            fractions,
            key=lambda bucket: (raw_counts[bucket] - base_counts[bucket], fractions[bucket]),
            reverse=True,
        )
        for bucket in ranked[:remainder]:
            base_counts[bucket] += 1
    return base_counts


def rank_bucket_candidates(df, bucket):
    if bucket == "exploit":
        return df.sort_values(["final_score", "novelty", "uncertainty"], ascending=[False, False, False])
    if bucket == "learn":
        return df.sort_values(["uncertainty", "final_score", "novelty"], ascending=[False, False, False])
    if bucket == "explore":
        return df.sort_values(["novelty", "final_score", "uncertainty"], ascending=[False, False, False])
    return df.sort_values(["final_score", "uncertainty", "novelty"], ascending=[False, False, False])


def select_acquisition_portfolio(df, total_candidates=None, config=None):
    cfg = resolve_system_config(config)
    annotated = df.copy().reset_index(drop=True)
    if annotated.empty:
        annotated["accepted_for_feedback"] = False
        annotated["selection_bucket"] = ""
        annotated["selection_reason"] = ""
        return annotated

    if "passes_diversity_filter" in annotated.columns:
        candidate_pool = annotated[annotated["passes_diversity_filter"]].copy()
    else:
        candidate_pool = annotated.copy()

    total = min(
        len(candidate_pool),
        total_candidates if total_candidates is not None else cfg.loop.candidates_per_round,
    )
    quotas = allocate_bucket_counts(total, config=cfg)

    annotated["accepted_for_feedback"] = False
    annotated["selection_bucket"] = ""
    annotated["selection_reason"] = ""

    selected_indices = set()
    for bucket in ("exploit", "learn", "explore"):
        ranking = rank_bucket_candidates(candidate_pool, bucket)
        picked = 0
        for idx in ranking.index:
            if idx in selected_indices:
                continue
            selected_indices.add(idx)
            annotated.loc[idx, "accepted_for_feedback"] = True
            annotated.loc[idx, "selection_bucket"] = bucket
            annotated.loc[idx, "selection_reason"] = f"{bucket}_quota_rank"
            picked += 1
            if picked >= quotas[bucket]:
                break

    if len(selected_indices) < total:
        fallback = rank_bucket_candidates(candidate_pool.loc[~candidate_pool.index.isin(selected_indices)], "exploit")
        for idx in fallback.index:
            selected_indices.add(idx)
            annotated.loc[idx, "accepted_for_feedback"] = True
            annotated.loc[idx, "selection_bucket"] = "exploit"
            annotated.loc[idx, "selection_reason"] = "quota_backfill_by_final_score"
            if len(selected_indices) >= total:
                break

    return annotated


def confidence_series_for_labeling(df):
    if "accepted_for_feedback" in df.columns:
        selected = df[df["accepted_for_feedback"]]
        if not selected.empty:
            return selected["confidence"]
    return df["confidence"]


def is_confidence_collapse(confidence, threshold_cfg):
    summary = summarize_series(confidence)
    if summary["count"] == 0:
        return False, summary
    span = summary["max"] - summary["min"]
    collapsed = summary["std"] < threshold_cfg.min_confidence_std or span < threshold_cfg.min_confidence_span
    summary["span"] = float(span)
    return collapsed, summary


def pseudo_label_candidates(df, thresholds=None, config=None):
    cfg = resolve_system_config(config)
    threshold_cfg = (
        ThresholdConfig(**thresholds)
        if thresholds is not None
        else ThresholdConfig(
            positive=cfg.pseudo_label.positive,
            negative=cfg.pseudo_label.negative,
            min_confidence_std=cfg.pseudo_label.min_confidence_std,
            min_confidence_span=cfg.pseudo_label.min_confidence_span,
        )
    )

    labeled = df.copy()
    if "accepted_for_feedback" not in labeled.columns:
        labeled["accepted_for_feedback"] = True

    labeled["pseudo_label"] = -1
    labeled["selected_for_feedback"] = False
    labeled["review_candidate"] = False

    collapse_confidence = confidence_series_for_labeling(labeled)
    collapsed, summary = is_confidence_collapse(collapse_confidence, threshold_cfg)
    print(
        "Confidence distribution:",
        json.dumps(
            {
                key: round(value, 4) if isinstance(value, float) else value
                for key, value in summary.items()
            }
        ),
    )

    accepted_mask = labeled["accepted_for_feedback"].fillna(False)
    if collapsed:
        print("Confidence collapse detected; rejecting pseudo-label assignment for this batch")
        labeled.loc[accepted_mask, "review_candidate"] = True
        return labeled

    positive_mask = accepted_mask & (labeled["confidence"] > threshold_cfg.positive)
    negative_mask = accepted_mask & (labeled["confidence"] < threshold_cfg.negative)

    labeled.loc[positive_mask, "pseudo_label"] = 1
    labeled.loc[negative_mask, "pseudo_label"] = 0
    labeled.loc[accepted_mask & (labeled["pseudo_label"] != -1), "selected_for_feedback"] = True
    labeled.loc[accepted_mask & (labeled["pseudo_label"] == -1), "review_candidate"] = True

    accepted = int(labeled["selected_for_feedback"].sum())
    rejected = int((accepted_mask & (labeled["pseudo_label"] == -1)).sum())
    print(f"Pseudo-label acceptance: accepted={accepted} rejected={rejected}")
    return labeled


def select_feedback_batch(df, per_class=5):
    eligible = df.copy()
    if "selected_for_feedback" in eligible.columns:
        eligible = eligible[eligible["selected_for_feedback"]]

    pos = eligible[eligible["pseudo_label"] == 1].sort_values(
        ["confidence", "novelty"], ascending=[False, False]
    )
    neg = eligible[eligible["pseudo_label"] == 0].sort_values(
        ["confidence", "novelty"], ascending=[True, False]
    )
    n = min(len(pos), len(neg), per_class)

    if n == 0:
        print("Skipping iteration due to imbalance")
        return df.iloc[0:0].copy()

    selected = pd.concat([pos.head(n), neg.head(n)], ignore_index=True)
    print(f"Balanced feedback selection: positive={n} negative={n}")
    return selected


def append_feedback_to_dataset(dataset_df, selected_df):
    from system.services.data_service import featurize_dataframe, infer_fingerprint_columns

    if selected_df.empty:
        print("No feedback rows added to dataset")
        return dataset_df.copy()

    pos = selected_df[selected_df["pseudo_label"] == 1]
    neg = selected_df[selected_df["pseudo_label"] == 0]
    n = min(len(pos), len(neg))
    if n == 0:
        print("Skipping dataset update due to unbalanced feedback")
        return dataset_df.copy()

    feedback = pd.concat([pos.head(n), neg.head(n)], ignore_index=True).copy()
    feedback["biodegradable"] = feedback["pseudo_label"]
    feedback = feedback.drop(
        columns=[
            "pseudo_label",
            "selected_for_feedback",
            "review_candidate",
            "accepted_for_feedback",
            "confidence",
            "uncertainty",
            "final_score",
            "passes_reference_filter",
            "passes_batch_filter",
            "passes_diversity_filter",
            "batch_max_similarity",
            "max_similarity",
            "novelty",
            "selection_bucket",
            "selection_reason",
            "candidate_status",
            "acceptance_reason",
            "rejection_reason",
            "generation_strategy",
            "generation_attempts",
            "is_feasible",
            "feasibility_reason",
            "experiment_value",
            "risk_level",
        ],
        errors="ignore",
    )

    combined = pd.concat([dataset_df, feedback], ignore_index=True)
    combined = combined.drop_duplicates(subset=["smiles", "biodegradable"], keep="first")
    featurized = featurize_dataframe(
        combined,
        fingerprint_columns=infer_fingerprint_columns(dataset_df),
    )
    print(f"Dataset update: added={len(feedback)} total={len(featurized)}")
    return featurized

__all__ = [
    "allocate_bucket_counts",
    "append_feedback_to_dataset",
    "confidence_series_for_labeling",
    "is_confidence_collapse",
    "pseudo_label_candidates",
    "rank_bucket_candidates",
    "select_acquisition_portfolio",
    "select_feedback_batch",
    "selection_counts",
]
