from __future__ import annotations

import pandas as pd


def candidate_short_explanation(row) -> str:
    bucket = str(row.get("selection_bucket") or row.get("bucket") or "").strip().lower()
    confidence = float(row.get("confidence", 0.0))
    uncertainty = float(row.get("uncertainty", 0.0))
    novelty = float(row.get("novelty", 0.0))

    if bucket == "learn" or uncertainty >= 0.7:
        primary = "Selected for learning because uncertainty is high."
    elif bucket == "explore" or novelty >= 0.65:
        primary = "Selected for exploration because novelty is high."
    elif bucket == "exploit" or confidence >= 0.75:
        primary = "Selected for exploitation because confidence is high."
    else:
        primary = "Moderate confidence and high novelty make this a useful experiment candidate."

    secondary = ""
    if confidence >= 0.8 and uncertainty <= 0.25:
        secondary = "The model is relatively consistent on this molecule compared with the current pool."
    elif uncertainty >= 0.75 and novelty >= 0.5:
        secondary = "Treat this as a learning-oriented recommendation rather than a near-certain prediction."
    elif 0.4 <= confidence <= 0.7 and novelty >= 0.55:
        secondary = "Moderate confidence with meaningful novelty makes it helpful for prioritizing review."
    elif confidence <= 0.3:
        secondary = "Low confidence means this should be treated as exploratory, not definitive."

    return " ".join(part for part in (primary, secondary) if part)


def add_candidate_explanations(df: pd.DataFrame) -> pd.DataFrame:
    explained = df.copy()
    explained["short_explanation"] = explained.apply(candidate_short_explanation, axis=1)
    return explained
