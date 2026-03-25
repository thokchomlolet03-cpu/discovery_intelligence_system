from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from pipeline_utils import write_dataframe, write_json_log


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
UPLOADED_SESSIONS_DIR = DATA_DIR / "uploaded_sessions"
LEGACY_UPLOADED_SESSIONS_DIR = DATA_DIR / "uploads"
PAID_REQUESTS_DIR = DATA_DIR / "paid_requests"
REPORTS_DIR = DATA_DIR / "reports"

LATEST_RESULT_NAME = "latest_result.json"


def ensure_artifact_directories() -> None:
    for directory in (DATA_DIR, UPLOADED_SESSIONS_DIR, PAID_REQUESTS_DIR, REPORTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def uploaded_session_dir(session_id: str, create: bool = False) -> Path:
    ensure_artifact_directories()
    canonical = UPLOADED_SESSIONS_DIR / session_id
    legacy = LEGACY_UPLOADED_SESSIONS_DIR / session_id
    if create:
        canonical.mkdir(parents=True, exist_ok=True)
        return canonical
    if canonical.exists():
        return canonical
    if legacy.exists():
        return legacy
    return canonical


def paid_request_dir(request_id: str, create: bool = False) -> Path:
    ensure_artifact_directories()
    target = PAID_REQUESTS_DIR / request_id
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target


def report_path(name: str) -> Path:
    ensure_artifact_directories()
    return REPORTS_DIR / name


def latest_result_path() -> Path:
    return report_path(LATEST_RESULT_NAME)


def write_json_artifact(path: Path, payload: Any) -> str:
    write_json_log(path, payload)
    return str(path)


def write_csv_artifact(path: Path, dataframe: pd.DataFrame) -> str:
    write_dataframe(path, dataframe)
    return str(path)


def write_session_report_copy(session_id: str, filename: str, payload: Any) -> str:
    target = report_path(f"{session_id}_{filename}")
    return write_json_artifact(target, payload)


def write_latest_result(payload: Any) -> str:
    return write_json_artifact(latest_result_path(), payload)


def write_paid_request_artifacts(
    request_id: str,
    metadata: dict[str, Any],
    file_bytes: bytes,
    filename: str,
) -> dict[str, str]:
    target_dir = paid_request_dir(request_id, create=True)
    dataset_path = target_dir / filename
    metadata_path = target_dir / "paid_request_metadata.json"
    report_copy_path = report_path(f"paid_request_{request_id}.json")

    artifact_paths = {
        "request_dir": str(target_dir),
        "dataset_path": str(dataset_path),
        "metadata_path": str(metadata_path),
        "report_copy_path": str(report_copy_path),
    }

    dataset_path.write_bytes(file_bytes)
    payload = {**metadata, "artifacts": artifact_paths}
    write_json_log(metadata_path, payload)
    write_json_log(report_copy_path, payload)

    return artifact_paths
