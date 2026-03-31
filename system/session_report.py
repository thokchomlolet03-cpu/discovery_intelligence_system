from __future__ import annotations

from dataclasses import replace
from typing import Any

import pandas as pd

from system_config import SystemConfig


def apply_scoring_mode(config: SystemConfig, scoring_mode: str | None) -> tuple[str, SystemConfig]:
    mode = (scoring_mode or "balanced").strip().lower()
    if mode == "conservative":
        return mode, replace(
            config,
            acquisition=replace(config.acquisition, w_conf=0.65, w_novelty=0.15, w_uncertainty=0.20),
            decision=replace(config.decision, w_uncertainty=0.25, w_novelty=0.20, w_low_confidence=0.10),
        )
    if mode == "exploratory":
        return mode, replace(
            config,
            acquisition=replace(config.acquisition, w_conf=0.25, w_novelty=0.35, w_uncertainty=0.40),
            decision=replace(config.decision, w_uncertainty=0.45, w_novelty=0.35, w_low_confidence=0.20),
        )
    return "balanced", config


def _normalized_priority_weights(intent: str, scoring_mode: str) -> dict[str, float]:
    weights = {
        "confidence": 0.30,
        "uncertainty": 0.20,
        "novelty": 0.15,
        "experiment_value": 0.35,
    }

    if scoring_mode == "conservative":
        weights.update({"confidence": 0.50, "uncertainty": 0.10, "novelty": 0.10, "experiment_value": 0.30})
    elif scoring_mode == "exploratory":
        weights.update({"confidence": 0.15, "uncertainty": 0.30, "novelty": 0.25, "experiment_value": 0.30})

    cleaned_intent = (intent or "rank_uploaded_molecules").strip().lower()
    if cleaned_intent == "predict_labels":
        weights["confidence"] += 0.25
        weights["uncertainty"] -= 0.05
        weights["novelty"] -= 0.05
        weights["experiment_value"] -= 0.15
    elif cleaned_intent == "generate_candidates":
        weights["novelty"] += 0.05
        weights["uncertainty"] += 0.05
        weights["experiment_value"] += 0.10
    elif cleaned_intent == "explore_uncertain":
        weights["uncertainty"] += 0.20
        weights["novelty"] += 0.10
        weights["confidence"] -= 0.10

    total = sum(max(value, 0.0) for value in weights.values()) or 1.0
    return {key: max(value, 0.0) / total for key, value in weights.items()}


def ranking_policy(intent: str, scoring_mode: str) -> dict[str, Any]:
    cleaned_intent = (intent or "rank_uploaded_molecules").strip().lower()
    weights = _normalized_priority_weights(cleaned_intent, scoring_mode)

    if cleaned_intent == "predict_labels":
        primary_score = "confidence"
        sort_order = ["confidence", "priority_score", "novelty"]
        summary = "Candidate order prioritizes model confidence first, then the weighted priority score and novelty."
    elif cleaned_intent == "explore_uncertain":
        primary_score = "uncertainty"
        sort_order = ["uncertainty", "novelty", "priority_score"]
        summary = "Candidate order prioritizes uncertainty first so the shortlist focuses on reducing model blind spots."
    else:
        primary_score = "priority_score"
        sort_order = ["priority_score", "experiment_value", "novelty"]
        summary = "Candidate order prioritizes the weighted priority score first, then experiment value and novelty."

    return {
        "primary_score": primary_score,
        "sort_order": sort_order,
        "weights": weights,
        "formula_label": "priority_score",
        "formula_summary": summary,
        "formula_text": "priority_score combines confidence, uncertainty, novelty, and experiment value using the current scoring mode and intent.",
    }


def apply_priority_scores(df: pd.DataFrame, intent: str, scoring_mode: str) -> pd.DataFrame:
    prioritized = df.copy()
    for column in ("confidence", "uncertainty", "novelty", "experiment_value"):
        if column not in prioritized.columns:
            prioritized[column] = 0.0
        prioritized[column] = pd.to_numeric(prioritized[column], errors="coerce").fillna(0.0)

    policy = ranking_policy(intent, scoring_mode)
    weights = policy["weights"]

    prioritized["priority_weight_confidence"] = weights["confidence"]
    prioritized["priority_weight_uncertainty"] = weights["uncertainty"]
    prioritized["priority_weight_novelty"] = weights["novelty"]
    prioritized["priority_weight_experiment_value"] = weights["experiment_value"]

    prioritized["priority_component_confidence"] = prioritized["confidence"] * weights["confidence"]
    prioritized["priority_component_uncertainty"] = prioritized["uncertainty"] * weights["uncertainty"]
    prioritized["priority_component_novelty"] = prioritized["novelty"] * weights["novelty"]
    prioritized["priority_component_experiment_value"] = prioritized["experiment_value"] * weights["experiment_value"]
    prioritized["priority_score"] = (
        prioritized["priority_component_confidence"]
        + prioritized["priority_component_uncertainty"]
        + prioritized["priority_component_novelty"]
        + prioritized["priority_component_experiment_value"]
    )

    sort_order = list(policy["sort_order"])
    return prioritized.sort_values(sort_order, ascending=[False] * len(sort_order))


def build_warnings(
    validation: dict[str, Any],
    scoring_mode: str,
    intent: str,
    out_of_domain_ratio: float | None = None,
    mean_uncertainty: float | None = None,
) -> list[str]:
    warnings: list[str] = []
    total_rows = max(int(validation.get("total_rows", 0)), 1)
    invalid_ratio = float(validation.get("invalid_smiles_count", 0)) / total_rows
    duplicate_ratio = float(validation.get("duplicate_count", 0)) / total_rows
    label_ratio = float(validation.get("rows_with_labels", 0)) / total_rows

    if invalid_ratio >= 0.15:
        warnings.append("A meaningful share of the uploaded rows could not be parsed as valid SMILES.")
    if duplicate_ratio >= 0.10:
        warnings.append("Duplicate molecules were detected; repeated rows can reduce the value of the run.")
    if label_ratio < 0.25 and intent in {"generate_candidates", "predict_labels"}:
        warnings.append("Low label coverage may reduce recommendation quality.")
    if out_of_domain_ratio is not None and out_of_domain_ratio >= 0.40:
        warnings.append("Many uploaded molecules are outside the current system's strongest chemistry range.")
    if mean_uncertainty is not None and mean_uncertainty >= 0.65:
        warnings.append("Many top-ranked outputs are high-uncertainty recommendations and should be reviewed cautiously.")
    if scoring_mode == "exploratory":
        warnings.append("This run is more exploratory than predictive.")
    return warnings


def recommendation_summary(candidates: list[dict[str, Any]], intent: str) -> str:
    if not candidates:
        return "No prioritized candidates were produced from this run."

    top = candidates[0]
    bucket = top.get("bucket") or top.get("selection_bucket") or "priority"
    risk = top.get("risk") or top.get("risk_level") or "unknown"
    if intent == "predict_labels":
        return f"Use the highest-confidence molecules as screening leads, but confirm them experimentally. Current lead bucket: {bucket}; risk: {risk}."
    if intent == "explore_uncertain":
        return f"Use the highest-uncertainty molecules to reduce model blind spots. Current lead bucket: {bucket}; risk: {risk}."
    return f"Start review with the highest-priority candidates and use bucket plus risk to separate testing now from later review. Current lead bucket: {bucket}; risk: {risk}."


def _measurement_summary(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "semantic_mode": str(validation.get("semantic_mode") or "").strip(),
        "file_type": str(validation.get("file_type") or "").strip(),
        "value_column": str(validation.get("value_column") or "").strip(),
        "rows_with_values": int(validation.get("rows_with_values", 0) or 0),
        "rows_without_values": int(validation.get("rows_without_values", 0) or 0),
        "rows_with_labels": int(validation.get("rows_with_labels", 0) or 0),
        "rows_without_labels": int(validation.get("rows_without_labels", 0) or 0),
        "label_source": str(validation.get("label_source") or "").strip(),
    }


def _bucket_counts(frame: pd.DataFrame | None) -> dict[str, int]:
    if frame is None or frame.empty:
        return {}
    source = "selection_bucket" if "selection_bucket" in frame.columns else "bucket" if "bucket" in frame.columns else ""
    if not source:
        return {}
    counts = (
        frame[source]
        .fillna("unassigned")
        .replace("", "unassigned")
        .astype(str)
        .value_counts()
        .to_dict()
    )
    return {str(key): int(value) for key, value in counts.items()}


def _ranking_diagnostics(frame: pd.DataFrame | None, *, intent: str, scoring_mode: str) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {}

    policy = ranking_policy(intent, scoring_mode)
    diagnostics: dict[str, Any] = {
        "scored_candidates": int(len(frame)),
        "bucket_counts": _bucket_counts(frame),
        "score_basis": str(policy["primary_score"]),
    }

    if "max_similarity" in frame.columns:
        similarity = pd.to_numeric(frame["max_similarity"], errors="coerce")
        if similarity.notna().any():
            diagnostics["mean_reference_similarity"] = float(similarity.dropna().mean())
            diagnostics["out_of_domain_rate"] = float((similarity.dropna() < 0.25).mean())

    if "novelty" in frame.columns:
        novelty = pd.to_numeric(frame["novelty"], errors="coerce")
        if novelty.notna().any():
            diagnostics["mean_novelty"] = float(novelty.dropna().mean())

    if "value" not in frame.columns:
        return diagnostics

    observed_value = pd.to_numeric(frame["value"], errors="coerce")
    valid = observed_value.notna()
    if int(valid.sum()) == 0:
        return diagnostics

    diagnostics["measurement_rows_evaluated"] = int(valid.sum())
    diagnostics["mean_observed_value"] = float(observed_value[valid].mean())

    score_column = ""
    for candidate in [str(policy["primary_score"])] + [item for item in ("priority_score", "experiment_value", "confidence") if item != policy["primary_score"]]:
        if candidate in frame.columns:
            score_column = candidate
            break
    if not score_column:
        return diagnostics

    modeled = pd.to_numeric(frame[score_column], errors="coerce")
    aligned = pd.DataFrame({"observed": observed_value, "modeled": modeled}).dropna()
    if aligned.empty:
        return diagnostics

    if len(aligned) >= 2:
        diagnostics["spearman_rank_correlation"] = float(aligned["observed"].rank().corr(aligned["modeled"].rank()))

    top_k = min(10, len(aligned))
    ranked = aligned.sort_values("modeled", ascending=False)
    diagnostics["top_k_measurement_mean"] = float(ranked.head(top_k)["observed"].mean())
    diagnostics["overall_measurement_mean"] = float(aligned["observed"].mean())
    diagnostics["top_k_measurement_lift"] = float(
        diagnostics["top_k_measurement_mean"] - diagnostics["overall_measurement_mean"]
    )
    return diagnostics


def build_upload_session_summary(
    session_id: str,
    source_name: str,
    input_type: str,
    column_mapping: dict[str, str | None],
    validation: dict[str, Any],
    intent: str,
    scoring_mode: str,
    consent_learning: bool,
    warnings: list[str],
    product_tier: str = "standard",
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "source_name": source_name,
        "product_tier": product_tier,
        "input_type": input_type,
        "column_mapping": column_mapping,
        "validation_summary": validation,
        "measurement_summary": _measurement_summary(validation),
        "intent_selected": intent,
        "mode_used": scoring_mode,
        "consent_learning": consent_learning,
        "warnings": warnings,
    }


def build_analysis_report(
    validation: dict[str, Any],
    scoring_mode: str,
    intent: str,
    consent_learning: bool,
    top_candidates: list[dict[str, Any]],
    warnings: list[str],
    product_tier: str = "standard",
    scored_frame: pd.DataFrame | None = None,
) -> dict[str, Any]:
    return {
        "product_tier": product_tier,
        "uploaded_rows": int(validation.get("total_rows", 0)),
        "valid_rows": int(validation.get("valid_smiles_count", 0)),
        "invalid_rows": int(validation.get("invalid_smiles_count", 0)),
        "duplicates": int(validation.get("duplicate_count", 0)),
        "mode_used": scoring_mode,
        "intent_selected": intent,
        "consent_learning": consent_learning,
        "top_candidates_returned": int(len(top_candidates)),
        "measurement_summary": _measurement_summary(validation),
        "ranking_diagnostics": _ranking_diagnostics(scored_frame, intent=intent, scoring_mode=scoring_mode),
        "ranking_policy": ranking_policy(intent, scoring_mode),
        "warnings": warnings,
        "top_level_recommendation_summary": recommendation_summary(top_candidates, intent),
    }
