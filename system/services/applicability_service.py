from __future__ import annotations

from typing import Any

from system.contracts import DomainStatus, validate_applicability_domain


OUT_OF_DOMAIN_THRESHOLD = 0.25
NEAR_BOUNDARY_THRESHOLD = 0.45


def assess_applicability(max_similarity: Any) -> dict[str, Any]:
    try:
        similarity = float(max_similarity)
    except (TypeError, ValueError):
        return validate_applicability_domain(
            {
                "status": DomainStatus.unknown.value,
                "max_reference_similarity": None,
                "support_band": "unknown",
                "summary": "Reference-similarity support was not available for this candidate.",
                "evidence": [],
            }
        )

    if similarity < OUT_OF_DOMAIN_THRESHOLD:
        status = DomainStatus.out_of_domain.value
        support_band = "weak_support"
        summary = "Reference similarity is low, so the model is operating outside stronger chemistry support."
    elif similarity < NEAR_BOUNDARY_THRESHOLD:
        status = DomainStatus.near_boundary.value
        support_band = "boundary_support"
        summary = "Reference similarity is moderate, so the model signal should be treated as boundary coverage."
    else:
        status = DomainStatus.in_domain.value
        support_band = "supported"
        summary = "Reference similarity is strong enough to treat this as within stronger chemistry support."

    return validate_applicability_domain(
        {
            "status": status,
            "max_reference_similarity": similarity,
            "support_band": support_band,
            "summary": summary,
            "evidence": [f"Maximum reference similarity: {similarity:.3f}."],
        }
    )


__all__ = ["NEAR_BOUNDARY_THRESHOLD", "OUT_OF_DOMAIN_THRESHOLD", "assess_applicability"]
