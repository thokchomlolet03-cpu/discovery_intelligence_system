from __future__ import annotations

import pandas as pd

from decision.decision_engine import risk_level
from system.explanation_engine import add_candidate_explanations
from system.provenance import add_candidate_provenance
from system.services.applicability_service import assess_applicability
from system.services.scientific_output_service import (
    build_decision_policy,
    build_model_judgment,
    build_normalized_explanation,
    build_novelty_signal,
    build_scientific_recommendation,
    scientific_data_facts,
)
from system.session_report import apply_priority_scores


def bucketize_candidates(df: pd.DataFrame) -> pd.DataFrame:
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


def assign_candidate_identifiers(df: pd.DataFrame) -> pd.DataFrame:
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


def decorate_candidates(
    frame: pd.DataFrame,
    mode: str,
    source_name: str,
    bundle: dict[str, object] | None,
    intent: str,
    scoring_mode: str,
    target_definition: dict[str, object] | None = None,
) -> pd.DataFrame:
    decorated = assign_candidate_identifiers(bucketize_candidates(frame))
    decorated["risk_level"] = decorated.apply(lambda row: risk_level(row), axis=1)
    decorated["risk"] = decorated["risk_level"]
    decorated = apply_priority_scores(decorated, intent=intent, scoring_mode=scoring_mode)
    decorated = add_candidate_explanations(decorated, target_definition=target_definition)
    decorated = add_candidate_provenance(decorated, mode=mode, source_name=source_name, bundle=bundle)
    decorated["target_definition"] = [target_definition or {} for _ in range(len(decorated))]
    decorated["data_facts"] = decorated.apply(
        lambda row: scientific_data_facts(row, target_definition=target_definition, source_name=source_name),
        axis=1,
    )
    decorated["model_judgment"] = decorated.apply(
        lambda row: build_model_judgment(row, target_definition=target_definition),
        axis=1,
    )
    decorated["applicability_domain"] = decorated.apply(lambda row: assess_applicability(row.get("max_similarity")), axis=1)
    decorated["novelty_signal"] = decorated.apply(lambda row: build_novelty_signal(row), axis=1)
    decorated["decision_policy"] = decorated.apply(lambda row: build_decision_policy(row), axis=1)
    decorated["final_recommendation"] = decorated.apply(
        lambda row: build_scientific_recommendation(row, rationale=row.get("rationale")),
        axis=1,
    )
    decorated["normalized_explanation"] = decorated.apply(
        lambda row: build_normalized_explanation(
            row,
            rationale=row.get("rationale"),
            target_definition=target_definition,
            model_judgment=row.get("model_judgment"),
            decision_policy=row.get("decision_policy"),
        ),
        axis=1,
    )
    decorated["accepted_for_feedback"] = decorated.get("accepted_for_feedback", True)
    return decorated


__all__ = ["assign_candidate_identifiers", "bucketize_candidates", "decorate_candidates"]
