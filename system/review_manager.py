from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from system.contracts import REVIEW_STATUS_VALUES, validate_review_event_record, validate_review_queue_artifact
from system.db.repositories import ArtifactRepository, ReviewRepository
from system.services.artifact_service import DATA_DIR, uploaded_session_dir, write_dataframe, write_review_queue_artifact


REVIEWS_PATH = DATA_DIR / "reviews.json"
GLOBAL_REVIEW_QUEUE_PATH = DATA_DIR / "review_queue.json"
GLOBAL_REVIEW_QUEUE_CSV_PATH = DATA_DIR / "review_queue.csv"
STATUS_ORDER = REVIEW_STATUS_VALUES
ACTION_STATUS_MAP = {
    "approve": "approved",
    "reject": "rejected",
    "later": "under review",
    "under_review": "under review",
    "review_later": "under review",
    "save_note": "under review",
    "tested": "tested",
    "ingest": "ingested",
}
ALLOWED_STATUS_TRANSITIONS = {
    "suggested": {"suggested", "under review", "approved", "rejected", "tested"},
    "under review": {"under review", "approved", "rejected", "tested"},
    "approved": {"approved", "under review", "rejected", "tested", "ingested"},
    "rejected": {"rejected", "under review"},
    "tested": {"tested", "approved", "ingested"},
    "ingested": {"ingested"},
}

review_repository = ReviewRepository()
artifact_repository = ArtifactRepository()


def review_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def review_session_key(session_id: str | None) -> str:
    return session_id or "public"


def normalize_status(status: str | None, action: str | None = None) -> str:
    if status:
        cleaned = str(status).strip().lower().replace("_", " ")
        if cleaned in STATUS_ORDER:
            return cleaned
    if action:
        cleaned_action = str(action).strip().lower().replace(" ", "_")
        return ACTION_STATUS_MAP.get(cleaned_action, "under review")
    return "under review"


def validate_review_transition(previous_status: str | None, next_status: str, action: str | None = None) -> str:
    normalized_next = normalize_status(next_status, action=action)
    normalized_previous = normalize_status(previous_status) if previous_status else ""
    if not normalized_previous:
        return normalized_next

    allowed = ALLOWED_STATUS_TRANSITIONS.get(normalized_previous, set(STATUS_ORDER))
    if normalized_next not in allowed:
        raise ValueError(
            f"Review status transition from '{normalized_previous}' to '{normalized_next}' is not allowed."
        )
    return normalized_next


def candidate_key(session_id: str | None, candidate_id: str | None, smiles: str) -> str:
    return f"{review_session_key(session_id)}::{candidate_id or smiles}"


def load_reviews(path: Path = REVIEWS_PATH, workspace_id: str | None = None) -> list[dict[str, Any]]:
    del path
    return review_repository.list_reviews(workspace_id=workspace_id)


def save_reviews(reviews: list[dict[str, Any]], path: Path = REVIEWS_PATH) -> None:
    del reviews, path


def record_review_action(
    session_id: str | None,
    workspace_id: str | None,
    candidate_id: str | None,
    smiles: str,
    action: str,
    status: str | None,
    note: str,
    reviewer: str | None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    reviewed_at = review_timestamp()
    latest = latest_review_map(session_id, workspace_id=workspace_id)
    latest_record = latest.get(candidate_key(session_id, candidate_id or smiles, smiles), {})
    normalized_status = validate_review_transition(latest_record.get("status"), status or "", action=action)
    record = validate_review_event_record(
        {
            "session_id": review_session_key(session_id),
            "workspace_id": workspace_id or "",
            "candidate_id": candidate_id or smiles,
            "smiles": smiles,
            "action": action,
            "previous_status": latest_record.get("status"),
            "status": normalized_status,
            "note": note.strip(),
            "timestamp": reviewed_at,
            "reviewed_at": reviewed_at,
            "actor": reviewer.strip() if reviewer else "unassigned",
            "reviewer": reviewer.strip() if reviewer else "unassigned",
            "actor_user_id": actor_user_id or "",
            "metadata": {},
        }
    )
    return review_repository.record_review(record)


def record_review_actions(
    items: list[dict[str, Any]],
    session_id: str | None = None,
    workspace_id: str | None = None,
    actor_user_id: str | None = None,
) -> list[dict[str, Any]]:
    created_payloads: list[dict[str, Any]] = []
    latest = latest_review_map(session_id, workspace_id=workspace_id)

    for item in items:
        smiles = str(item.get("smiles") or "").strip()
        if not smiles:
            continue
        reviewed_at = review_timestamp()
        candidate_id = item.get("candidate_id") or smiles
        target_session_id = item.get("session_id") or session_id
        if session_id is not None and target_session_id != session_id:
            raise ValueError("Bulk review items must match the requested session_id.")
        key = candidate_key(target_session_id, candidate_id, smiles)
        previous_status = (latest.get(key) or {}).get("status")
        normalized_status = validate_review_transition(previous_status, item.get("status") or "", action=item.get("action"))
        item_workspace_id = str(item.get("workspace_id") or workspace_id or "").strip()
        if workspace_id is not None and item_workspace_id and item_workspace_id != workspace_id:
            raise ValueError("Bulk review items must match the authorized workspace.")
        record = validate_review_event_record(
            {
                "session_id": review_session_key(target_session_id),
                "workspace_id": item_workspace_id,
                "candidate_id": candidate_id,
                "smiles": smiles,
                "action": str(item.get("action") or "later"),
                "previous_status": previous_status,
                "status": normalized_status,
                "note": str(item.get("note") or "").strip(),
                "timestamp": reviewed_at,
                "reviewed_at": reviewed_at,
                "actor": str(item.get("reviewer") or item.get("actor") or "unassigned").strip() or "unassigned",
                "reviewer": str(item.get("reviewer") or "unassigned").strip() or "unassigned",
                "actor_user_id": str(item.get("actor_user_id") or actor_user_id or "").strip(),
                "metadata": dict(item.get("metadata") or {}),
            }
        )
        created_payloads.append(record)
        latest[key] = record

    if not created_payloads:
        return []
    return review_repository.record_reviews(created_payloads)


def latest_review_map(session_id: str | None, workspace_id: str | None = None) -> dict[str, dict[str, Any]]:
    session_key = review_session_key(session_id)
    latest: dict[str, dict[str, Any]] = {}
    for review in review_repository.list_reviews(session_key, workspace_id=workspace_id):
        key = candidate_key(session_key, review.get("candidate_id"), review.get("smiles", ""))
        latest[key] = review
    return latest


def review_history_map(session_id: str | None, workspace_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
    session_key = review_session_key(session_id)
    history: dict[str, list[dict[str, Any]]] = {}
    for review in review_repository.list_reviews(session_key, workspace_id=workspace_id):
        key = candidate_key(session_key, review.get("candidate_id"), review.get("smiles", ""))
        history.setdefault(key, []).append(review)

    for key, items in history.items():
        history[key] = sorted(items, key=lambda item: str(item.get("reviewed_at") or item.get("timestamp") or ""))
    return history


def annotate_candidates_with_reviews(
    candidates: list[dict[str, Any]],
    session_id: str | None,
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    annotated = []
    latest = latest_review_map(session_id, workspace_id=workspace_id)
    history = review_history_map(session_id, workspace_id=workspace_id)
    for candidate in candidates:
        row = dict(candidate)
        key = candidate_key(session_id, row.get("candidate_id") or row.get("molecule_id") or row.get("polymer"), row.get("smiles", ""))
        review = latest.get(key, {})
        row["status"] = review.get("status", row.get("status", "suggested"))
        row["review_note"] = review.get("note", row.get("review_note", ""))
        row["reviewer"] = review.get("reviewer", row.get("reviewer", ""))
        row["reviewed_at"] = review.get("reviewed_at", review.get("timestamp", row.get("reviewed_at", "")))
        row["review_history"] = history.get(key, [])
        if row.get("review_note") or row.get("reviewed_at"):
            row["review_summary"] = {
                "status": row["status"],
                "note": row["review_note"],
                "reviewer": row["reviewer"] or "unassigned",
                "actor": row["reviewer"] or "unassigned",
                "reviewed_at": row["reviewed_at"],
            }
        annotated.append(row)
    return annotated


def build_review_queue(
    candidates: list[dict[str, Any]],
    session_id: str | None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    annotated = annotate_candidates_with_reviews(candidates, session_id=session_id, workspace_id=workspace_id)
    normalized_candidates: list[dict[str, Any]] = []
    session_key = review_session_key(session_id)
    generated_at = review_timestamp()
    for index, candidate in enumerate(annotated, start=1):
        row = dict(candidate)
        normalized_candidates.append(
            {
                "session_id": session_key,
                "rank": int(row.get("rank") or index),
                "candidate_id": row.get("candidate_id") or row.get("molecule_id") or row.get("polymer") or row.get("smiles") or f"candidate_{index}",
                "smiles": row.get("smiles") or "",
                "canonical_smiles": row.get("canonical_smiles") or row.get("smiles") or "",
                "confidence": float(row.get("confidence") or 0.0),
                "uncertainty": float(row.get("uncertainty") or 0.0),
                "novelty": float(row.get("novelty") or 0.0),
                "acquisition_score": float(row.get("acquisition_score") or row.get("final_score") or row.get("experiment_value") or 0.0),
                "experiment_value": float(row.get("experiment_value") or 0.0),
                "bucket": row.get("bucket") or row.get("selection_bucket") or "learn",
                "risk": row.get("risk") or row.get("risk_level") or "medium",
                "status": normalize_status(row.get("status") or "suggested"),
                "explanation": row.get("explanation") or [row.get("short_explanation") or "Recommendation details unavailable."],
                "provenance": row.get("provenance") if isinstance(row.get("provenance"), dict) else {"text": str(row.get("provenance") or "Scored from the current workflow.")},
                "feasibility": row.get("feasibility")
                or {
                    "is_feasible": row.get("is_feasible"),
                    "reason": row.get("feasibility_reason") or "",
                },
                "created_at": row.get("created_at") or row.get("timestamp") or generated_at,
                "model_metadata": row.get("model_metadata")
                or {
                    "version": str(row.get("model_version") or "unknown"),
                    "family": "",
                    "calibration_method": "",
                },
                "review_summary": row.get("review_summary"),
                "selection_reason": row.get("selection_reason") or "",
                "review_note": row.get("review_note") or "",
                "reviewer": row.get("reviewer") or "unassigned",
                "reviewed_at": row.get("reviewed_at") or None,
                "review_history": row.get("review_history") or [],
            }
        )
    counts = {status: 0 for status in STATUS_ORDER}
    groups = {status: [] for status in STATUS_ORDER}

    for candidate in normalized_candidates:
        status = normalize_status(candidate.get("status"))
        counts[status] += 1
        groups[status].append(candidate)

    payload = {
        "session_id": review_session_key(session_id),
        "generated_at": review_timestamp(),
        "summary": {
            "pending_review": int(counts["suggested"] + counts["under review"]),
            "approved": int(counts["approved"]),
            "rejected": int(counts["rejected"]),
            "tested": int(counts["tested"]),
            "ingested": int(counts["ingested"]),
            "counts": counts,
        },
        "groups": groups,
    }
    return validate_review_queue_artifact(payload)


def persist_review_queue(
    candidates: list[dict[str, Any]],
    session_id: str | None,
    workspace_id: str | None = None,
    created_by_user_id: str | None = None,
) -> dict[str, Any]:
    queue = build_review_queue(candidates, session_id=session_id, workspace_id=workspace_id)
    if session_id:
        target_dir = uploaded_session_dir(session_id, create=True)
        json_path = target_dir / "review_queue.json"
        csv_path = target_dir / "review_queue.csv"
    else:
        json_path = GLOBAL_REVIEW_QUEUE_PATH
        csv_path = GLOBAL_REVIEW_QUEUE_CSV_PATH

    write_review_queue_artifact(json_path, queue)
    flat_rows = [candidate for status in STATUS_ORDER for candidate in queue["groups"][status]]
    write_dataframe(csv_path, pd.DataFrame(flat_rows))

    if session_id:
        artifact_repository.register_artifact(
            artifact_type="review_queue_json",
            path=json_path,
            session_id=review_session_key(session_id),
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            metadata={"row_count": len(flat_rows)},
        )
        artifact_repository.register_artifact(
            artifact_type="review_queue_csv",
            path=csv_path,
            session_id=review_session_key(session_id),
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            metadata={"row_count": len(flat_rows)},
        )
    return queue
