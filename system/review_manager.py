from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline_utils import write_dataframe, write_json_log
from utils.artifact_writer import DATA_DIR, uploaded_session_dir


REVIEWS_PATH = DATA_DIR / "reviews.json"
GLOBAL_REVIEW_QUEUE_PATH = DATA_DIR / "review_queue.json"
STATUS_ORDER = ("suggested", "under review", "approved", "rejected", "tested", "ingested")
ACTION_STATUS_MAP = {
    "approve": "approved",
    "reject": "rejected",
    "later": "under review",
    "under_review": "under review",
    "tested": "tested",
    "ingest": "ingested",
}


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


def candidate_key(session_id: str | None, candidate_id: str | None, smiles: str) -> str:
    return f"{review_session_key(session_id)}::{candidate_id or smiles}"


def load_reviews(path: Path = REVIEWS_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return payload if isinstance(payload, list) else []


def save_reviews(reviews: list[dict[str, Any]], path: Path = REVIEWS_PATH) -> None:
    write_json_log(path, reviews)


def record_review_action(
    session_id: str | None,
    candidate_id: str | None,
    smiles: str,
    action: str,
    status: str | None,
    note: str,
    reviewer: str | None,
) -> dict[str, Any]:
    record = {
        "session_id": review_session_key(session_id),
        "candidate_id": candidate_id or smiles,
        "smiles": smiles,
        "action": action,
        "status": normalize_status(status, action=action),
        "note": note.strip(),
        "timestamp": review_timestamp(),
        "reviewer": reviewer.strip() if reviewer else "unassigned",
    }
    reviews = load_reviews()
    reviews.append(record)
    save_reviews(reviews)
    return record


def latest_review_map(session_id: str | None) -> dict[str, dict[str, Any]]:
    session_key = review_session_key(session_id)
    latest: dict[str, dict[str, Any]] = {}
    for review in load_reviews():
        if review.get("session_id") != session_key:
            continue
        key = candidate_key(session_id, review.get("candidate_id"), review.get("smiles", ""))
        latest[key] = review
    return latest


def annotate_candidates_with_reviews(candidates: list[dict[str, Any]], session_id: str | None) -> list[dict[str, Any]]:
    annotated = []
    latest = latest_review_map(session_id)
    for candidate in candidates:
        row = dict(candidate)
        key = candidate_key(session_id, row.get("candidate_id") or row.get("molecule_id") or row.get("polymer"), row.get("smiles", ""))
        review = latest.get(key, {})
        row["status"] = review.get("status", row.get("status", "suggested"))
        row["review_note"] = review.get("note", row.get("review_note", ""))
        row["reviewer"] = review.get("reviewer", row.get("reviewer", ""))
        row["reviewed_at"] = review.get("timestamp", row.get("reviewed_at", ""))
        annotated.append(row)
    return annotated


def build_review_queue(candidates: list[dict[str, Any]], session_id: str | None) -> dict[str, Any]:
    annotated = annotate_candidates_with_reviews(candidates, session_id=session_id)
    counts = {status: 0 for status in STATUS_ORDER}
    groups = {status: [] for status in STATUS_ORDER}

    for candidate in annotated:
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
    return payload


def persist_review_queue(candidates: list[dict[str, Any]], session_id: str | None) -> dict[str, Any]:
    queue = build_review_queue(candidates, session_id=session_id)
    if session_id:
        target_dir = uploaded_session_dir(session_id, create=True)
        json_path = target_dir / "review_queue.json"
        csv_path = target_dir / "review_queue.csv"
    else:
        json_path = GLOBAL_REVIEW_QUEUE_PATH
        csv_path = DATA_DIR / "review_queue.csv"

    write_json_log(json_path, queue)
    flat_rows = [candidate for status in STATUS_ORDER for candidate in queue["groups"][status]]
    write_dataframe(csv_path, pd.DataFrame(flat_rows))
    return queue
