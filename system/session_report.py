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


def apply_priority_scores(df: pd.DataFrame, intent: str, scoring_mode: str) -> pd.DataFrame:
    prioritized = df.copy()
    for column in ("confidence", "uncertainty", "novelty", "experiment_value"):
        if column not in prioritized.columns:
            prioritized[column] = 0.0
        prioritized[column] = pd.to_numeric(prioritized[column], errors="coerce").fillna(0.0)

    weights = _normalized_priority_weights(intent, scoring_mode)
    prioritized["priority_score"] = (
        (prioritized["confidence"] * weights["confidence"])
        + (prioritized["uncertainty"] * weights["uncertainty"])
        + (prioritized["novelty"] * weights["novelty"])
        + (prioritized["experiment_value"] * weights["experiment_value"])
    )

    cleaned_intent = (intent or "rank_uploaded_molecules").strip().lower()
    if cleaned_intent == "predict_labels":
        return prioritized.sort_values(["confidence", "priority_score", "novelty"], ascending=[False, False, False])
    if cleaned_intent == "explore_uncertain":
        return prioritized.sort_values(["uncertainty", "novelty", "priority_score"], ascending=[False, False, False])
    return prioritized.sort_values(["priority_score", "experiment_value", "novelty"], ascending=[False, False, False])


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
        "warnings": warnings,
        "top_level_recommendation_summary": recommendation_summary(top_candidates, intent),
    }
