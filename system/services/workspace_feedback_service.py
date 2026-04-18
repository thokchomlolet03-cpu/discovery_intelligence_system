from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from system.db.repositories import ReviewRepository
from system.db import ScientificStateRepository


review_repository = ReviewRepository()
scientific_state_repository = ScientificStateRepository()


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _normalize_token(value: Any) -> str:
    return _clean_text(value).lower()


def _to_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _humanize_timestamp(value: Any) -> str:
    parsed = _to_datetime(value)
    if parsed is None:
        return "Not available"
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _title_token(value: Any, default: str = "Not recorded") -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return default
    return cleaned.replace("_", " ").strip().title()


def _candidate_label(candidate: dict[str, Any]) -> str:
    candidate_id = _clean_text(
        candidate.get("candidate_id") or candidate.get("molecule_id") or candidate.get("polymer")
    )
    smiles = _clean_text(candidate.get("canonical_smiles") or candidate.get("smiles"))
    if candidate_id and smiles and candidate_id != smiles:
        return f"{candidate_id} ({smiles})"
    return candidate_id or smiles or "candidate"


def _candidate_tokens(candidate: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for field in ("canonical_smiles", "smiles"):
        token = _normalize_token(candidate.get(field))
        if token:
            tokens.add(token)
    return tokens


def _serialize_review_event(
    review: dict[str, Any],
    *,
    session_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    session_id = _clean_text(review.get("session_id"))
    label_map = session_labels if isinstance(session_labels, dict) else {}
    reviewed_at = _clean_text(review.get("reviewed_at") or review.get("timestamp"))
    smiles = _clean_text(review.get("smiles"))
    return {
        "session_id": session_id,
        "session_label": label_map.get(session_id, session_id or "Session"),
        "candidate_id": _clean_text(review.get("candidate_id")),
        "smiles": smiles,
        "match_token": _normalize_token(smiles),
        "action": _clean_text(review.get("action")),
        "action_label": _title_token(review.get("action")),
        "status": _clean_text(review.get("status")),
        "status_label": _title_token(review.get("status")),
        "note": _clean_text(review.get("note")),
        "reviewer": _clean_text(review.get("reviewer"), default="unassigned"),
        "reviewed_at": reviewed_at,
        "reviewed_at_label": _humanize_timestamp(reviewed_at),
        "upload_url": f"/upload?session_id={session_id}" if session_id else "",
        "discovery_url": f"/discovery?session_id={session_id}" if session_id else "",
        "dashboard_url": f"/dashboard?session_id={session_id}" if session_id else "",
    }


def _session_summary_from_annotated_candidates(
    candidates: list[dict[str, Any]],
    *,
    limit_matches: int,
) -> dict[str, Any]:
    matched = [candidate for candidate in candidates if int(candidate.get("workspace_memory_count") or 0) > 0]
    matched.sort(
        key=lambda candidate: (
            _to_datetime(((candidate.get("workspace_memory") or {}).get("last_reviewed_at"))) or datetime.min.replace(tzinfo=timezone.utc),
            _candidate_label(candidate),
        ),
        reverse=True,
    )

    unique_session_ids = {
        session_id
        for candidate in matched
        for session_id in list(((candidate.get("workspace_memory") or {}).get("session_ids")) or [])
        if session_id
    }
    total_events = sum(int(candidate.get("workspace_memory_count") or 0) for candidate in matched)
    status_counts = {
        "approved": 0,
        "rejected": 0,
        "tested": 0,
        "ingested": 0,
        "under_review": 0,
        "suggested": 0,
    }

    matches: list[dict[str, Any]] = []
    latest_reviewed_at = ""
    for candidate in matched[:limit_matches]:
        workspace_memory = candidate.get("workspace_memory") if isinstance(candidate.get("workspace_memory"), dict) else {}
        last_status = _clean_text(workspace_memory.get("last_status"))
        if last_status == "under review":
            status_counts["under_review"] += 1
        elif last_status in status_counts:
            status_counts[last_status] += 1
        else:
            status_counts["suggested"] += 1

        latest_reviewed_at = latest_reviewed_at or _clean_text(workspace_memory.get("last_reviewed_at"))
        matches.append(
            {
                "candidate_id": _clean_text(candidate.get("candidate_id")),
                "label": _candidate_label(candidate),
                "smiles": _clean_text(candidate.get("canonical_smiles") or candidate.get("smiles")),
                "last_status": last_status,
                "last_status_label": _title_token(last_status),
                "last_action": _clean_text(workspace_memory.get("last_action")),
                "last_action_label": _title_token(workspace_memory.get("last_action")),
                "last_note": _clean_text(workspace_memory.get("last_note")),
                "last_reviewer": _clean_text(workspace_memory.get("last_reviewer"), default="unassigned"),
                "last_reviewed_at": _clean_text(workspace_memory.get("last_reviewed_at")),
                "last_reviewed_at_label": _clean_text(
                    workspace_memory.get("last_reviewed_at_label"),
                    default=_humanize_timestamp(workspace_memory.get("last_reviewed_at")),
                ),
                "last_session_id": _clean_text(workspace_memory.get("last_session_id")),
                "last_session_label": _clean_text(
                    workspace_memory.get("last_session_label"),
                    default=_clean_text(workspace_memory.get("last_session_id"), default="Session"),
                ),
                "event_count": int(workspace_memory.get("event_count") or 0),
                "session_count": int(workspace_memory.get("session_count") or 0),
                "upload_url": _clean_text(workspace_memory.get("upload_url")),
                "discovery_url": _clean_text(workspace_memory.get("discovery_url")),
                "dashboard_url": _clean_text(workspace_memory.get("dashboard_url")),
            }
        )

    if matched:
        summary = (
            f"{len(matched)} shortlist candidate"
            f"{'' if len(matched) == 1 else 's'} already appeared in {len(unique_session_ids)} earlier workspace session"
            f"{'' if len(unique_session_ids) == 1 else 's'}."
        )
    else:
        summary = "No prior workspace feedback has been linked to this session shortlist yet."

    return {
        "matched_candidate_count": len(matched),
        "session_count": len(unique_session_ids),
        "event_count": total_events,
        "latest_reviewed_at": latest_reviewed_at,
        "latest_reviewed_at_label": _humanize_timestamp(latest_reviewed_at),
        "status_counts": status_counts,
        "matches": matches,
        "summary": summary,
    }


def annotate_candidates_with_workspace_memory(
    candidates: list[dict[str, Any]] | None,
    *,
    session_id: str | None,
    workspace_id: str | None,
    review_events: list[dict[str, Any]] | None = None,
    session_labels: dict[str, str] | None = None,
    include_current_session: bool = False,
    limit_history: int = 6,
) -> list[dict[str, Any]]:
    candidate_rows = candidates if isinstance(candidates, list) else []
    if not candidate_rows:
        return []

    carryover_records: list[dict[str, Any]] = []
    if workspace_id and session_id:
        try:
            carryover_records = scientific_state_repository.list_carryover_records(
                session_id=str(session_id),
                workspace_id=workspace_id,
            )
        except Exception:
            carryover_records = []

    if review_events is None:
        review_events = review_repository.list_reviews(workspace_id=workspace_id)
    label_map = session_labels if isinstance(session_labels, dict) else {}
    current_session_id = _clean_text(session_id)

    serialized_reviews = []
    for review in review_events:
        if not isinstance(review, dict):
            continue
        review_session_id = _clean_text(review.get("session_id"))
        if not include_current_session and current_session_id and review_session_id == current_session_id:
            continue
        serialized = _serialize_review_event(review, session_labels=label_map)
        if not serialized["match_token"]:
            continue
        serialized_reviews.append(serialized)

    history_by_token: dict[str, list[dict[str, Any]]] = {}
    for review in serialized_reviews:
        history_by_token.setdefault(review["match_token"], []).append(review)
    for item in carryover_records:
        canonical = _normalize_token(item.get("canonical_smiles") or item.get("smiles"))
        if not canonical:
            continue
        history_by_token.setdefault(canonical, []).append(
            {
                "session_id": _clean_text(item.get("source_session_id")),
                "session_label": label_map.get(_clean_text(item.get("source_session_id")), _clean_text(item.get("source_session_id"), default="Session")),
                "candidate_id": _clean_text(item.get("source_candidate_id")),
                "smiles": _clean_text(item.get("smiles")),
                "match_token": canonical,
                "action": _clean_text(item.get("source_action")),
                "action_label": _title_token(item.get("source_action")),
                "status": _clean_text(item.get("source_status")),
                "status_label": _title_token(item.get("source_status")),
                "note": _clean_text(item.get("source_note")),
                "reviewer": _clean_text(item.get("source_reviewer"), default="unassigned"),
                "reviewed_at": _clean_text(item.get("source_reviewed_at")),
                "reviewed_at_label": _humanize_timestamp(item.get("source_reviewed_at")),
                "upload_url": f"/upload?session_id={_clean_text(item.get('source_session_id'))}" if _clean_text(item.get("source_session_id")) else "",
                "discovery_url": f"/discovery?session_id={_clean_text(item.get('source_session_id'))}" if _clean_text(item.get("source_session_id")) else "",
                "dashboard_url": f"/dashboard?session_id={_clean_text(item.get('source_session_id'))}" if _clean_text(item.get("source_session_id")) else "",
            }
        )

    annotated: list[dict[str, Any]] = []
    for candidate in candidate_rows:
        if not isinstance(candidate, dict):
            continue
        row = dict(candidate)
        dedupe_keys: set[tuple[str, str, str, str, str]] = set()
        matched_history: list[dict[str, Any]] = []

        for token in _candidate_tokens(row):
            for review in history_by_token.get(token, []):
                dedupe_key = (
                    review["session_id"],
                    review["candidate_id"],
                    review["reviewed_at"],
                    review["status"],
                    review["action"],
                )
                if dedupe_key in dedupe_keys:
                    continue
                dedupe_keys.add(dedupe_key)
                matched_history.append(dict(review))

        matched_history.sort(key=lambda item: (_clean_text(item.get("reviewed_at")), _clean_text(item.get("status"))))
        latest = matched_history[-1] if matched_history else {}
        unique_session_ids = sorted(
            {
                _clean_text(item.get("session_id"))
                for item in matched_history
                if _clean_text(item.get("session_id"))
            }
        )

        row["workspace_memory_count"] = len(matched_history)
        row["workspace_memory_history"] = matched_history[-limit_history:]
        row["workspace_memory"] = {
            "event_count": len(matched_history),
            "session_count": len(unique_session_ids),
            "session_ids": unique_session_ids,
            "last_status": _clean_text(latest.get("status")),
            "last_status_label": _clean_text(latest.get("status_label")),
            "last_action": _clean_text(latest.get("action")),
            "last_action_label": _clean_text(latest.get("action_label")),
            "last_note": _clean_text(latest.get("note")),
            "last_reviewer": _clean_text(latest.get("reviewer"), default="unassigned"),
            "last_reviewed_at": _clean_text(latest.get("reviewed_at")),
            "last_reviewed_at_label": _clean_text(
                latest.get("reviewed_at_label"),
                default=_humanize_timestamp(latest.get("reviewed_at")),
            ),
            "last_session_id": _clean_text(latest.get("session_id")),
            "last_session_label": _clean_text(
                latest.get("session_label"),
                default=_clean_text(latest.get("session_id"), default="Session"),
            ),
            "upload_url": _clean_text(latest.get("upload_url")),
            "discovery_url": _clean_text(latest.get("discovery_url")),
            "dashboard_url": _clean_text(latest.get("dashboard_url")),
        }
        annotated.append(row)

    return annotated


def build_session_workspace_memory(
    candidates: list[dict[str, Any]] | None,
    *,
    session_id: str | None,
    workspace_id: str | None,
    review_events: list[dict[str, Any]] | None = None,
    session_labels: dict[str, str] | None = None,
    limit_matches: int = 5,
) -> dict[str, Any]:
    annotated = annotate_candidates_with_workspace_memory(
        candidates,
        session_id=session_id,
        workspace_id=workspace_id,
        review_events=review_events,
        session_labels=session_labels,
    )
    return _session_summary_from_annotated_candidates(annotated, limit_matches=limit_matches)


def build_workspace_feedback_summary(
    *,
    workspace_id: str | None,
    focus_session_id: str | None = None,
    focus_candidates: list[dict[str, Any]] | None = None,
    review_events: list[dict[str, Any]] | None = None,
    session_labels: dict[str, str] | None = None,
    limit_events: int = 6,
    limit_matches: int = 5,
) -> dict[str, Any]:
    if review_events is None:
        review_events = review_repository.list_reviews(workspace_id=workspace_id)
    label_map = session_labels if isinstance(session_labels, dict) else {}
    serialized_reviews = [
        _serialize_review_event(review, session_labels=label_map)
        for review in review_events
        if isinstance(review, dict)
    ]
    serialized_reviews = [item for item in serialized_reviews if item.get("match_token")]
    latest_events = list(reversed(serialized_reviews[-limit_events:]))
    focus_memory = build_session_workspace_memory(
        focus_candidates,
        session_id=focus_session_id,
        workspace_id=workspace_id,
        review_events=review_events,
        session_labels=label_map,
        limit_matches=limit_matches,
    )
    return {
        "event_count": len(serialized_reviews),
        "session_count": len({_clean_text(item.get("session_id")) for item in serialized_reviews if _clean_text(item.get("session_id"))}),
        "candidate_count": len({item["match_token"] for item in serialized_reviews if item.get("match_token")}),
        "latest_events": latest_events,
        "focus_memory": focus_memory,
    }


__all__ = [
    "annotate_candidates_with_workspace_memory",
    "build_session_workspace_memory",
    "build_workspace_feedback_summary",
]
