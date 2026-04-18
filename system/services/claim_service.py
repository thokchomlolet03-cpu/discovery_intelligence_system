from __future__ import annotations

from typing import Any
from uuid import uuid4

from system.db import ScientificStateRepository


scientific_state_repository = ScientificStateRepository()


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def materialize_session_claims(
    *,
    session_id: str,
    workspace_id: str,
    created_by_user_id: str | None,
    run_metadata: dict[str, Any],
    candidate_states: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []

    top_candidates = sorted(
        [item for item in candidate_states if int(item.get("rank") or 0) > 0],
        key=lambda item: int(item.get("rank") or 0),
    )[:3]
    for item in top_candidates:
        recommendation = item.get("recommendation_summary") if isinstance(item.get("recommendation_summary"), dict) else {}
        trust = item.get("trust_summary") if isinstance(item.get("trust_summary"), dict) else {}
        candidate_id = str(item.get("candidate_id") or "").strip()
        canonical_smiles = str(item.get("canonical_smiles") or "").strip()
        rank = int(item.get("rank") or 0)
        target_name = str(((item.get("identity_context") or {}).get("target_name")) or "the session target").strip()
        claim_text = (
            f"Candidate {candidate_id or canonical_smiles or 'candidate'} is a priority experimental candidate "
            f"for {target_name} at rank {rank}."
        )
        claims.append(
            {
                "claim_id": _make_id("claim"),
                "session_id": session_id,
                "workspace_id": workspace_id,
                "created_by_user_id": created_by_user_id or "",
                "candidate_id": candidate_id,
                "canonical_smiles": canonical_smiles,
                "run_metadata_session_id": session_id,
                "claim_scope": "candidate",
                "claim_type": "candidate_experiment_priority",
                "claim_text": claim_text,
                "claim_summary": {
                    "rank": rank,
                    "bucket": str(recommendation.get("bucket") or "").strip(),
                    "risk": str(recommendation.get("risk") or "").strip(),
                    "trust_label": str(trust.get("trust_label") or "").strip(),
                },
                "source_basis": "recommended",
                "support_links": {
                    "candidate_state_candidate_id": candidate_id,
                    "run_metadata_session_id": session_id,
                },
                "status": "active",
                "provenance_markers": {
                    "materialization_rule": "top_ranked_candidate_priority_claim",
                    "candidate_state_source": "canonical_candidate_state",
                },
            }
        )

    trust_summary = run_metadata.get("trust_summary") if isinstance(run_metadata.get("trust_summary"), dict) else {}
    bridge_summary = str(trust_summary.get("bridge_state_summary") or "").strip()
    if bridge_summary:
        claims.append(
            {
                "claim_id": _make_id("claim"),
                "session_id": session_id,
                "workspace_id": workspace_id,
                "created_by_user_id": created_by_user_id or "",
                "candidate_id": "",
                "canonical_smiles": "",
                "run_metadata_session_id": session_id,
                "claim_scope": "run",
                "claim_type": "run_interpretation_caution",
                "claim_text": bridge_summary,
                "claim_summary": {
                    "comparison_ready": bool((run_metadata.get("comparison_anchors") or {}).get("comparison_ready")),
                    "bridge_state_active": bool(trust_summary.get("baseline_fallback_visible")),
                },
                "source_basis": "derived",
                "support_links": {"run_metadata_session_id": session_id},
                "status": "active",
                "provenance_markers": {
                    "materialization_rule": "run_bridge_state_caution_claim",
                    "run_metadata_source": "canonical_run_metadata",
                },
            }
        )
    return claims
