from __future__ import annotations

import pandas as pd


def candidate_explanation_lines(row) -> list[str]:
    bucket = str(row.get("selection_bucket") or row.get("bucket") or "").strip().lower()
    confidence = float(row.get("confidence", 0.0))
    uncertainty = float(row.get("uncertainty", 0.0))
    novelty = float(row.get("novelty", 0.0))
    max_similarity = row.get("max_similarity")
    try:
        max_similarity = float(max_similarity)
    except (TypeError, ValueError):
        max_similarity = None
    measurement_value = row.get("value")
    try:
        measurement_value = float(measurement_value)
    except (TypeError, ValueError):
        measurement_value = None
    assay = str(row.get("assay") or "").strip()
    target = str(row.get("target") or "").strip()
    lines: list[str] = []

    if bucket == "learn" or uncertainty >= 0.7:
        lines.append("Selected for learning because uncertainty is high.")
    elif bucket == "explore" or novelty >= 0.65:
        lines.append("Selected for exploration because novelty is high.")
    elif bucket == "exploit" or confidence >= 0.75:
        lines.append("Selected for exploitation because confidence is high.")
    else:
        lines.append("Moderate confidence and high novelty make this a useful experiment candidate.")

    if confidence >= 0.8 and uncertainty <= 0.25:
        lines.append("The model is relatively consistent on this molecule compared with the current pool.")
    elif uncertainty >= 0.75 and novelty >= 0.5:
        lines.append("Treat this as a learning-oriented recommendation rather than a near-certain prediction.")
    elif 0.4 <= confidence <= 0.7 and novelty >= 0.55:
        lines.append("Moderate confidence with meaningful novelty makes it helpful for prioritizing review.")
    elif confidence <= 0.3:
        lines.append("Low confidence means this should be treated as exploratory, not definitive.")

    if max_similarity is not None:
        if max_similarity < 0.25:
            lines.append("This molecule sits far from the current reference chemistry and should be treated as out-of-domain.")
        elif max_similarity > 0.75:
            lines.append("This molecule remains close to known chemistry, which supports near-term exploitation.")

    if measurement_value is not None:
        lines.append(f"An observed uploaded measurement of {measurement_value:.3f} is available for cross-checking the ranking.")

    if assay or target:
        context_bits = [part for part in (assay, target) if part]
        lines.append(f"Scientific context is available from the upload: {', '.join(context_bits)}.")

    return lines


def candidate_short_explanation(row) -> str:
    lines = candidate_explanation_lines(row)
    return lines[0] if lines else "Recommendation details unavailable."


def add_candidate_explanations(df: pd.DataFrame) -> pd.DataFrame:
    explained = df.copy()
    explained["explanation"] = explained.apply(candidate_explanation_lines, axis=1)
    explained["short_explanation"] = explained["explanation"].apply(
        lambda lines: lines[0] if isinstance(lines, list) and lines else "Recommendation details unavailable."
    )
    return explained
