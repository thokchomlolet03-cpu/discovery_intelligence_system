from __future__ import annotations

from pathlib import Path
from typing import Iterable

from system.db.repositories import ArtifactRepository


FILENAME_ARTIFACT_TYPES = {
    "raw_upload.csv": ("raw_upload_csv",),
    "uploaded_dataset.csv": ("upload_csv", "raw_upload_csv"),
    "inspect_summary.json": ("upload_inspection_json",),
    "decision_output.json": ("decision_output_json",),
    "analysis_report.json": ("analysis_report_json", "analysis_report_copy_json", "latest_result_json"),
    "evaluation_summary.json": ("evaluation_summary",),
    "review_queue.json": ("review_queue_json",),
    "review_queue.csv": ("review_queue_csv",),
    "result.json": ("result_json",),
    "generated_candidates.csv": ("generated_candidates_csv",),
    "processed_candidates.csv": ("processed_candidates_csv",),
    "scored_candidates.csv": ("scored_candidates_csv",),
    "rf_model_v1.joblib": ("model_bundle",),
}


def _existing_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    return path if path.exists() else None


def resolve_artifact_path(
    *,
    artifact_types: Iterable[str],
    session_id: str | None = None,
    job_id: str | None = None,
    workspace_id: str | None = None,
    fallback_paths: Iterable[Path] = (),
) -> Path | None:
    repository = ArtifactRepository()
    for artifact_type in artifact_types:
        path = repository.get_latest_artifact_path(
            artifact_type=artifact_type,
            session_id=session_id,
            job_id=job_id,
            workspace_id=workspace_id,
        )
        existing = _existing_path(path)
        if existing is not None:
            return existing
    for fallback in fallback_paths:
        existing = _existing_path(fallback)
        if existing is not None:
            return existing
    return None


def resolve_session_artifact_path(
    session_id: str | None,
    filename: str,
    fallback_path: Path | None = None,
    workspace_id: str | None = None,
) -> Path | None:
    artifact_types = FILENAME_ARTIFACT_TYPES.get(filename, ())
    fallback_paths = [fallback_path] if fallback_path is not None else []
    return resolve_artifact_path(
        artifact_types=artifact_types,
        session_id=session_id,
        workspace_id=workspace_id,
        fallback_paths=fallback_paths,
    )
