from __future__ import annotations

import pandas as pd

from decision.decision_engine import risk_level
from system.explanation_engine import add_candidate_explanations
from system.provenance import add_candidate_provenance
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
) -> pd.DataFrame:
    decorated = assign_candidate_identifiers(bucketize_candidates(frame))
    decorated["risk_level"] = decorated.apply(lambda row: risk_level(row), axis=1)
    decorated["risk"] = decorated["risk_level"]
    decorated = apply_priority_scores(decorated, intent=intent, scoring_mode=scoring_mode)
    decorated = add_candidate_explanations(decorated)
    decorated = add_candidate_provenance(decorated, mode=mode, source_name=source_name, bundle=bundle)
    decorated["accepted_for_feedback"] = decorated.get("accepted_for_feedback", True)
    return decorated


__all__ = ["assign_candidate_identifiers", "bucketize_candidates", "decorate_candidates"]

