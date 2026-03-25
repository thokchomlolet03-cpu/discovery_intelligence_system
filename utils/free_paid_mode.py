from __future__ import annotations

import copy
import os
from typing import Any


MAX_FREE_ROWS = max(int(os.getenv("MAX_FREE_ROWS", "50")), 1)
FREE_TOP_CANDIDATES_LIMIT = max(int(os.getenv("FREE_TOP_CANDIDATES_LIMIT", "10")), 1)


def assess_free_tier(validation: dict[str, Any]) -> dict[str, Any]:
    total_rows = int(validation.get("total_rows", 0))
    within_limit = total_rows <= MAX_FREE_ROWS
    if within_limit:
        message = (
            f"This upload is within the free hosted limit of {MAX_FREE_ROWS} rows and "
            f"will return up to {FREE_TOP_CANDIDATES_LIMIT} prioritized suggestions."
        )
    else:
        message = (
            f"This upload contains {total_rows} rows, which exceeds the free hosted limit of {MAX_FREE_ROWS}. "
            "Use the Request Full Analysis workflow for larger or more serious studies."
        )

    return {
        "product_tier": "free",
        "total_rows": total_rows,
        "max_free_rows": MAX_FREE_ROWS,
        "free_top_candidates_limit": FREE_TOP_CANDIDATES_LIMIT,
        "within_limit": within_limit,
        "request_analysis_recommended": not within_limit,
        "message": message,
    }


def free_tier_error_payload(validation: dict[str, Any], request_analysis_url: str) -> dict[str, Any]:
    assessment = assess_free_tier(validation)
    return {
        "detail": assessment["message"],
        "free_tier": assessment,
        "request_analysis_url": request_analysis_url,
    }


def candidate_limit_for_tier(product_tier: str | None) -> int | None:
    return FREE_TOP_CANDIDATES_LIMIT if (product_tier or "").strip().lower() == "free" else None


def limit_decision_output(payload: dict[str, Any], limit: int | None) -> dict[str, Any]:
    if not limit or not isinstance(payload, dict):
        return payload

    limited = copy.deepcopy(payload)
    rows = list(limited.get("top_experiments") or [])
    hidden = max(0, len(rows) - limit)
    limited["top_experiments"] = rows[:limit]

    summary = limited.get("summary")
    if isinstance(summary, dict):
        summary["returned_candidates"] = int(len(limited["top_experiments"]))
        summary["hidden_candidates"] = int(hidden)
    return limited


def apply_free_tier_result_limits(result: dict[str, Any]) -> dict[str, Any]:
    limited = copy.deepcopy(result)
    limit = FREE_TOP_CANDIDATES_LIMIT

    top_candidates = list(limited.get("top_candidates") or [])
    hidden = max(0, len(top_candidates) - limit)
    limited["top_candidates"] = top_candidates[:limit]

    if isinstance(limited.get("suggested_candidates"), list):
        limited["suggested_candidates"] = limited["suggested_candidates"][:limit]

    if isinstance(limited.get("decision_output"), dict):
        limited["decision_output"] = limit_decision_output(limited["decision_output"], limit)

    limited["product_tier"] = "free"
    limited["free_tier"] = {
        "max_free_rows": MAX_FREE_ROWS,
        "top_candidates_limit": limit,
        "returned_candidates": int(len(limited["top_candidates"])),
        "hidden_candidate_count": int(hidden),
        "downloads_enabled": False,
    }
    return limited
