from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.contracts import (
    ClaimStatus,
    ClaimType,
    EvidenceSupportLevel,
    validate_claim_record,
    validate_claim_reference,
    validate_claims_summary,
    validate_scientific_session_truth,
)
from system.db.repositories import ClaimRepository


claim_repository = ClaimRepository()
DEFAULT_CLAIM_LIMIT = 5


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)]


def _candidate_label(candidate: dict[str, Any]) -> str:
    candidate_id = _clean_text(
        candidate.get("candidate_id") or candidate.get("molecule_id") or candidate.get("polymer")
    )
    smiles = _clean_text(candidate.get("canonical_smiles") or candidate.get("smiles"))
    if candidate_id and smiles and candidate_id != smiles:
        return f"{candidate_id} ({smiles})"
    return candidate_id or smiles or "candidate"


def _support_level(candidate: dict[str, Any]) -> str:
    trust_label = _clean_text(
        candidate.get("trust_label")
        or ((candidate.get("rationale") or {}) if isinstance(candidate.get("rationale"), dict) else {}).get("trust_label")
    ).lower()
    if trust_label == "stronger trust":
        return EvidenceSupportLevel.strong.value
    if trust_label == "mixed trust":
        return EvidenceSupportLevel.moderate.value
    return EvidenceSupportLevel.limited.value


def _claim_text(candidate: dict[str, Any], target_definition: dict[str, Any], target_name: str) -> str:
    label = _candidate_label(candidate)
    target_kind = _clean_text(target_definition.get("target_kind"), default="classification").lower()
    optimization = _clean_text(target_definition.get("optimization_direction"), default="classify").lower()
    if target_kind == "regression":
        if optimization == "minimize":
            return f"Under the current session evidence, {label} is a plausible follow-up candidate to test for lower {target_name}."
        return f"Under the current session evidence, {label} is a plausible follow-up candidate to test for higher {target_name}."
    return f"Under the current session evidence, {label} is a plausible follow-up candidate to test against the current {target_name} objective."


def _bounded_scope(candidate: dict[str, Any], target_definition: dict[str, Any]) -> str:
    target_name = _clean_text(target_definition.get("target_name"), default="target objective")
    domain_status = _clean_text(candidate.get("domain_status"))
    scope = (
        f"This proposed claim is scoped to the current session, the recorded {target_name} target definition, and the current recommendation evidence. "
        "It is not experimental confirmation or causal proof."
    )
    if domain_status == "out_of_domain":
        return f"{scope} Chemistry support is weaker because this candidate sits outside stronger reference coverage."
    if domain_status == "near_boundary":
        return f"{scope} Chemistry support is mixed because this candidate sits near the current applicability boundary."
    return scope


def _evidence_basis_summary(candidate: dict[str, Any], scientific_truth: dict[str, Any]) -> str:
    evidence_loop = scientific_truth.get("evidence_loop") if isinstance(scientific_truth, dict) else {}
    evidence_loop = evidence_loop if isinstance(evidence_loop, dict) else {}
    modeling = _clean_list(evidence_loop.get("active_modeling_evidence"))
    ranking = _clean_list(evidence_loop.get("active_ranking_evidence"))
    parts: list[str] = []
    if modeling:
        parts.append(f"Modeling uses {', '.join(modeling[:2])}")
    if ranking:
        parts.append(f"ranking uses {', '.join(ranking[:2])}")
    primary_driver = _clean_text(
        candidate.get("rationale_primary_driver")
        or ((candidate.get("rationale") or {}) if isinstance(candidate.get("rationale"), dict) else {}).get("primary_driver")
    )
    if primary_driver:
        parts.append(primary_driver)
    if not parts:
        parts.append("Derived from the current session evidence, model output, and recommendation policy")
    return ". ".join(part.rstrip(".") for part in parts if part).strip() + "."


def build_claim_record(
    *,
    session_id: str,
    workspace_id: str,
    candidate: dict[str, Any],
    target_definition: dict[str, Any] | None,
    scientific_truth: dict[str, Any] | None,
    created_by_user_id: str | None = None,
    created_by: str = "system",
) -> dict[str, Any]:
    target_definition = target_definition if isinstance(target_definition, dict) else {}
    scientific_truth = scientific_truth if isinstance(scientific_truth, dict) else {}
    candidate_id = _clean_text(candidate.get("candidate_id") or candidate.get("molecule_id") or candidate.get("polymer"))
    target_name = _clean_text(target_definition.get("target_name"), default="target objective")
    timestamp = _utc_now()
    return validate_claim_record(
        {
            "claim_id": "",
            "workspace_id": workspace_id,
            "session_id": session_id,
            "candidate_id": candidate_id,
            "candidate_reference": {
                "candidate_id": candidate_id,
                "candidate_label": _candidate_label(candidate),
                "smiles": _clean_text(candidate.get("smiles")),
                "canonical_smiles": _clean_text(candidate.get("canonical_smiles") or candidate.get("smiles")),
                "rank": _safe_int(candidate.get("rank"), 0),
            },
            "target_definition_snapshot": target_definition,
            "claim_type": ClaimType.recommendation_assertion.value,
            "claim_text": _claim_text(candidate, target_definition, target_name),
            "bounded_scope": _bounded_scope(candidate, target_definition),
            "support_level": _support_level(candidate),
            "evidence_basis_summary": _evidence_basis_summary(candidate, scientific_truth),
            "source_recommendation_rank": _safe_int(candidate.get("rank"), 0),
            "status": ClaimStatus.proposed.value,
            "created_at": timestamp,
            "updated_at": timestamp,
            "created_by": _clean_text(created_by, default="system"),
            "created_by_user_id": _clean_text(created_by_user_id),
            "reviewed_at": None,
            "reviewed_by": "",
            "metadata": {
                "target_name": target_name,
                "support_driver": _clean_text(candidate.get("rationale_primary_driver")),
                "trust_label": _clean_text(candidate.get("trust_label")),
            },
        }
    )


def create_session_claims(
    *,
    session_id: str,
    workspace_id: str,
    decision_payload: dict[str, Any] | None,
    scientific_truth: dict[str, Any] | None,
    created_by_user_id: str | None = None,
    created_by: str = "system",
    limit: int = DEFAULT_CLAIM_LIMIT,
) -> list[dict[str, Any]]:
    decision_payload = decision_payload if isinstance(decision_payload, dict) else {}
    scientific_truth = scientific_truth if isinstance(scientific_truth, dict) else {}
    target_definition = (
        scientific_truth.get("target_definition") if isinstance(scientific_truth.get("target_definition"), dict) else {}
    ) or (decision_payload.get("target_definition") if isinstance(decision_payload.get("target_definition"), dict) else {})
    rows = decision_payload.get("top_experiments") if isinstance(decision_payload.get("top_experiments"), list) else []
    created: list[dict[str, Any]] = []
    for candidate in rows[: max(0, int(limit))]:
        if not isinstance(candidate, dict):
            continue
        candidate_id = _clean_text(candidate.get("candidate_id") or candidate.get("molecule_id") or candidate.get("polymer"))
        if not candidate_id:
            continue
        payload = build_claim_record(
            session_id=session_id,
            workspace_id=workspace_id,
            candidate=candidate,
            target_definition=target_definition,
            scientific_truth=scientific_truth,
            created_by_user_id=created_by_user_id,
            created_by=created_by,
        )
        created.append(claim_repository.upsert_claim(payload))
    return created


def list_session_claims(session_id: str, *, workspace_id: str | None = None) -> list[dict[str, Any]]:
    return claim_repository.list_claims(session_id=session_id, workspace_id=workspace_id)


def claim_refs_from_records(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        candidate_reference = claim.get("candidate_reference") if isinstance(claim.get("candidate_reference"), dict) else {}
        refs.append(
            validate_claim_reference(
                {
                    "claim_id": claim.get("claim_id"),
                    "candidate_id": claim.get("candidate_id"),
                    "candidate_label": candidate_reference.get("candidate_label") or claim.get("candidate_id"),
                    "claim_type": claim.get("claim_type"),
                    "claim_text": claim.get("claim_text"),
                    "support_level": claim.get("support_level"),
                    "status": claim.get("status"),
                    "source_recommendation_rank": claim.get("source_recommendation_rank"),
                    "created_at": claim.get("created_at"),
                }
            )
        )
    return refs


def claims_summary_from_records(claims: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(claims)
    proposed = sum(1 for claim in claims if _clean_text(claim.get("status")).lower() == ClaimStatus.proposed.value)
    accepted = sum(1 for claim in claims if _clean_text(claim.get("status")).lower() == ClaimStatus.accepted.value)
    rejected = sum(1 for claim in claims if _clean_text(claim.get("status")).lower() == ClaimStatus.rejected.value)
    superseded = sum(1 for claim in claims if _clean_text(claim.get("status")).lower() == ClaimStatus.superseded.value)
    if total:
        summary_text = (
            f"{total} proposed claim{'' if total == 1 else 's'} were derived from the current shortlist. "
            "Claims remain bounded recommendation-derived assertions, not experimental confirmation."
        )
    else:
        summary_text = "No session claims have been recorded."
    return validate_claims_summary(
        {
            "claim_count": total,
            "proposed_count": proposed,
            "accepted_count": accepted,
            "rejected_count": rejected,
            "superseded_count": superseded,
            "summary_text": summary_text,
            "top_claims": claim_refs_from_records(claims[:3]),
        }
    )


def attach_claims_to_scientific_session_truth(
    scientific_truth: dict[str, Any],
    claims: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(scientific_truth, dict):
        return scientific_truth
    updated = dict(scientific_truth)
    updated["claim_refs"] = claim_refs_from_records(claims)
    updated["claims_summary"] = claims_summary_from_records(claims)
    return validate_scientific_session_truth(updated)


__all__ = [
    "attach_claims_to_scientific_session_truth",
    "build_claim_record",
    "claim_refs_from_records",
    "claims_summary_from_records",
    "create_session_claims",
    "list_session_claims",
]
