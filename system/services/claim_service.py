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


def build_claim_evidence_links(
    *,
    claims: list[dict[str, Any]],
    evidence_records: list[dict[str, Any]],
    model_outputs: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for item in evidence_records:
        candidate_id = str(item.get("candidate_id") or "").strip()
        canonical_smiles = str(item.get("canonical_smiles") or item.get("smiles") or "").strip()
        key = candidate_id or canonical_smiles
        if key:
            evidence_by_candidate.setdefault(key, []).append(item)

    model_by_candidate: dict[str, dict[str, Any]] = {}
    recommendation_by_candidate: dict[str, dict[str, Any]] = {}
    for item in model_outputs:
        candidate_id = str(item.get("candidate_id") or "").strip()
        canonical_smiles = str(item.get("canonical_smiles") or item.get("smiles") or "").strip()
        key = candidate_id or canonical_smiles
        if key:
            model_by_candidate[key] = item
    for item in recommendations:
        candidate_id = str(item.get("candidate_id") or "").strip()
        canonical_smiles = str(item.get("canonical_smiles") or item.get("smiles") or "").strip()
        key = candidate_id or canonical_smiles
        if key:
            recommendation_by_candidate[key] = item

    links: list[dict[str, Any]] = []
    for claim in claims:
        if str(claim.get("claim_scope") or "").strip() != "candidate":
            continue
        claim_id = str(claim.get("claim_id") or "").strip()
        if not claim_id:
            continue
        created_by_user_id = str(claim.get("created_by_user_id") or "").strip() or None
        candidate_id = str(claim.get("candidate_id") or "").strip()
        canonical_smiles = str(claim.get("canonical_smiles") or "").strip()
        key = candidate_id or canonical_smiles
        if not key:
            continue

        recommendation = recommendation_by_candidate.get(key)
        if recommendation and recommendation.get("record_id") is not None:
            rank = int((recommendation.get("rank") or 0) or 0)
            links.append(
                {
                    "link_id": _make_id("claim_link"),
                    "session_id": str(claim.get("session_id") or ""),
                    "workspace_id": str(claim.get("workspace_id") or ""),
                    "created_by_user_id": created_by_user_id or "",
                    "claim_id": claim_id,
                    "linked_object_type": "recommendation",
                    "linked_object_id": str(recommendation.get("record_id")),
                    "relation_type": "derived_from",
                    "summary": f"Derived from the persisted recommendation record for rank {rank}.",
                    "provenance_markers": {"materialization_rule": "candidate_claim_to_recommendation"},
                }
            )

        model_output = model_by_candidate.get(key)
        if model_output and model_output.get("record_id") is not None:
            confidence = model_output.get("confidence")
            uncertainty = model_output.get("uncertainty")
            links.append(
                {
                    "link_id": _make_id("claim_link"),
                    "session_id": str(claim.get("session_id") or ""),
                    "workspace_id": str(claim.get("workspace_id") or ""),
                    "created_by_user_id": created_by_user_id or "",
                    "claim_id": claim_id,
                    "linked_object_type": "model_output",
                    "linked_object_id": str(model_output.get("record_id")),
                    "relation_type": "context_only",
                    "summary": f"Model context recorded with confidence {confidence} and uncertainty {uncertainty}.",
                    "provenance_markers": {"materialization_rule": "candidate_claim_to_model_output"},
                }
            )

        for evidence in evidence_by_candidate.get(key, []):
            if evidence.get("record_id") is None:
                continue
            evidence_type = str(evidence.get("evidence_type") or "").strip()
            if evidence_type == "observed_measurement":
                summary = (
                    f"Observed measurement context from row {evidence.get('source_row_index')} "
                    f"via {evidence.get('source_column') or 'value column'}."
                )
            elif evidence_type == "observed_label":
                summary = (
                    f"Observed label context from row {evidence.get('source_row_index')} "
                    f"via {evidence.get('source_column') or 'label column'}."
                )
            else:
                summary = "Uploaded structure evidence linked as claim context."
            links.append(
                {
                    "link_id": _make_id("claim_link"),
                    "session_id": str(claim.get("session_id") or ""),
                    "workspace_id": str(claim.get("workspace_id") or ""),
                    "created_by_user_id": created_by_user_id or "",
                    "claim_id": claim_id,
                    "linked_object_type": "evidence",
                    "linked_object_id": str(evidence.get("record_id")),
                    "relation_type": "context_only",
                    "summary": summary,
                    "provenance_markers": {
                        "materialization_rule": "candidate_claim_to_evidence",
                        "evidence_type": evidence_type,
                    },
                }
            )
    return links
