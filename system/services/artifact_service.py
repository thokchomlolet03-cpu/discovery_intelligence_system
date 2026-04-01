from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from system.contracts import (
    validate_decision_artifact,
    validate_review_queue_artifact,
    validate_training_result,
    validate_upload_inspection_result,
)
from system.services.runtime_config import config_to_dict, resolve_system_config
from utils.validation import raw_columns_only


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
UPLOADED_SESSIONS_DIR = DATA_DIR / "uploaded_sessions"
LEGACY_UPLOADED_SESSIONS_DIR = DATA_DIR / "uploads"
PAID_REQUESTS_DIR = DATA_DIR / "paid_requests"
REPORTS_DIR = DATA_DIR / "reports"
ALLOWED_ARTIFACT_ROOTS_ENV = "DISCOVERY_ALLOWED_ARTIFACT_ROOTS"

DEFAULT_CANDIDATE_PATH = Path("candidates.csv")
DEFAULT_GENERATED_CANDIDATE_PATH = Path("generated_candidates.csv")
DEFAULT_PROCESSED_CANDIDATE_PATH = Path("candidates_processed.csv")
DEFAULT_PREDICTED_CANDIDATE_PATH = Path("predicted_candidates.csv")
DEFAULT_LABELED_CANDIDATE_PATH = Path("labeled_candidates.csv")
DEFAULT_RESULTS_PATH = Path("candidates_results.csv")
DEFAULT_REVIEW_QUEUE_PATH = Path("review_queue.csv")
DEFAULT_LOG_PATH = Path("logs.json")
DEFAULT_ITERATION_HISTORY_PATH = Path("iteration_history.csv")
DEFAULT_RUN_CONFIG_PATH = Path("run_config.json")
DEFAULT_DECISION_OUTPUT_PATH = Path("decision_output.json")
DEFAULT_EVALUATION_PATH = Path("evaluation_summary.json")
DEFAULT_MODEL_PATH = Path("rf_model_v1.joblib")
LATEST_RESULT_NAME = "latest_result.json"
USER_FEEDBACK_PATH = Path("data/user_feedback.csv")
LEGACY_REPO_ROOT_ARTIFACT_NAMES = {
    DEFAULT_CANDIDATE_PATH.name,
    DEFAULT_GENERATED_CANDIDATE_PATH.name,
    DEFAULT_PROCESSED_CANDIDATE_PATH.name,
    DEFAULT_PREDICTED_CANDIDATE_PATH.name,
    DEFAULT_LABELED_CANDIDATE_PATH.name,
    DEFAULT_RESULTS_PATH.name,
    DEFAULT_REVIEW_QUEUE_PATH.name,
    DEFAULT_LOG_PATH.name,
    DEFAULT_ITERATION_HISTORY_PATH.name,
    DEFAULT_RUN_CONFIG_PATH.name,
    DEFAULT_DECISION_OUTPUT_PATH.name,
}


def ensure_artifact_directories() -> None:
    for directory in (DATA_DIR, UPLOADED_SESSIONS_DIR, PAID_REQUESTS_DIR, REPORTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def _resolve_artifact_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve()


def artifact_storage_roots() -> tuple[Path, ...]:
    ensure_artifact_directories()
    roots = {
        DATA_DIR.resolve(),
        UPLOADED_SESSIONS_DIR.resolve(),
        LEGACY_UPLOADED_SESSIONS_DIR.resolve(),
        PAID_REQUESTS_DIR.resolve(),
        REPORTS_DIR.resolve(),
    }
    configured = os.getenv(ALLOWED_ARTIFACT_ROOTS_ENV, "").strip()
    if configured:
        for item in configured.split(os.pathsep):
            text = item.strip()
            if text:
                roots.add(Path(text).expanduser().resolve())
    return tuple(sorted(roots, key=str))


def register_artifact_root(path: str | Path) -> Path:
    resolved = _resolve_artifact_path(path)
    configured = os.getenv(ALLOWED_ARTIFACT_ROOTS_ENV, "").strip()
    roots = [item for item in configured.split(os.pathsep) if item.strip()] if configured else []
    if str(resolved) not in roots:
        roots.append(str(resolved))
        os.environ[ALLOWED_ARTIFACT_ROOTS_ENV] = os.pathsep.join(roots)
    return resolved


def ensure_safe_artifact_path(path: str | Path, *, require_exists: bool = False) -> Path:
    resolved = _resolve_artifact_path(path)
    is_allowed_root = any(resolved.is_relative_to(root) for root in artifact_storage_roots())
    is_legacy_repo_root_artifact = resolved.parent == REPO_ROOT.resolve() and resolved.name in LEGACY_REPO_ROOT_ARTIFACT_NAMES
    if not is_allowed_root and not is_legacy_repo_root_artifact:
        raise ValueError("Artifact path must remain within configured artifact storage roots.")
    if require_exists:
        if not resolved.exists():
            raise FileNotFoundError("Artifact file is missing.")
        if not resolved.is_file():
            raise ValueError("Artifact path must point to a file.")
    return resolved


def artifact_display_path(path: str | Path) -> str:
    resolved = _resolve_artifact_path(path)
    for root in (DATA_DIR.resolve(), REPO_ROOT.resolve()):
        if resolved.is_relative_to(root):
            return str(resolved.relative_to(root))
    return resolved.name


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


def write_json_log(path, payload):
    path = ensure_safe_artifact_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def write_dataframe(path, df):
    path = ensure_safe_artifact_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_json_artifact(path: Path, payload: Any) -> str:
    write_json_log(path, payload)
    return str(path)


def write_validated_json_artifact(path: Path, payload: Any, validator) -> str:
    validated = validator(payload)
    write_json_log(path, validated)
    return str(path)


def write_csv_artifact(path: Path, dataframe: pd.DataFrame) -> str:
    write_dataframe(path, dataframe)
    return str(path)


def write_upload_inspection_artifact(path: Path, payload: Any) -> str:
    return write_validated_json_artifact(path, payload, validate_upload_inspection_result)


def write_training_summary_artifact(path: Path, payload: Any) -> str:
    return write_validated_json_artifact(path, payload, validate_training_result)


def write_decision_artifact(path: Path, payload: Any) -> str:
    return write_validated_json_artifact(path, payload, validate_decision_artifact)


def write_review_queue_artifact(path: Path, payload: Any) -> str:
    return write_validated_json_artifact(path, payload, validate_review_queue_artifact)


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


def write_run_config(path, config):
    write_json_log(path, config_to_dict(resolve_system_config(config)))


def write_evaluation_summary(path, bundle):
    from system.services.training_service import bundle_evaluation_summary

    write_json_log(path, bundle_evaluation_summary(bundle))


def flatten_iteration_record(record):
    flat = {
        "iteration": record["iteration"],
        "dataset_size": record["dataset_size"],
        "selected_feedback": record["selected_feedback"],
        "review_queue": record["review_queue"],
        "processed_candidates": record["processed_candidates"],
        "generated_candidates": record["generated_candidates"],
        "portfolio_selected": record["portfolio_selected"],
        "appended_feedback": record["appended_feedback"],
        "dry_run": record["dry_run"],
        "selected_model": record["selected_model"]["name"],
        "calibration_method": record["selected_model"]["calibration_method"],
        "holdout_accuracy": record["holdout"]["accuracy"],
        "holdout_balanced_accuracy": record["holdout"]["balanced_accuracy"],
        "holdout_f1_macro": record["holdout"]["f1_macro"],
        "holdout_brier_score": record["holdout"]["brier_score"],
        "holdout_log_loss": record["holdout"]["log_loss"],
        "holdout_exact_confidence_rate_raw": record["holdout"]["exact_confidence_rate_raw"],
        "feasible_candidates": record.get("feasible_candidates", 0),
        "infeasible_candidates": record.get("infeasible_candidates", 0),
        "decision_high_risk": record.get("decision_risk_counts", {}).get("high", 0),
        "decision_medium_risk": record.get("decision_risk_counts", {}).get("medium", 0),
        "decision_low_risk": record.get("decision_risk_counts", {}).get("low", 0),
        "top_experiment_value": record.get("top_experiment_value", 0.0),
    }
    for label, value in record["label_counts"].items():
        flat[f"label_{label}"] = value
    for bucket, value in record["selection_counts"].items():
        flat[f"selection_{bucket}"] = value
    for reason, value in record["candidate_rejections"].items():
        flat[f"rejected_{reason}"] = value
    for reason, value in record.get("feasibility_rejections", {}).items():
        flat[f"infeasible_{reason}"] = value
    return flat


def write_iteration_history(path, records):
    rows = [flatten_iteration_record(record) for record in records]
    frame = pd.DataFrame(rows)
    write_dataframe(path, frame)


def queue_feedback_rows(df: pd.DataFrame, consent_learning: bool) -> dict[str, Any]:
    if not consent_learning:
        return {
            "consent_learning": False,
            "queued_rows": 0,
            "total_rows": 0,
            "path": str(USER_FEEDBACK_PATH),
            "message": "Uploaded data was kept private and was not added to the learning queue.",
        }

    feedback = raw_columns_only(df)
    feedback = feedback[feedback["biodegradable"].isin([0, 1])].copy()
    if feedback.empty:
        return {
            "consent_learning": True,
            "queued_rows": 0,
            "total_rows": 0,
            "path": str(USER_FEEDBACK_PATH),
            "message": "Learning consent was granted, but no usable labeled rows were available to queue.",
        }

    existing = pd.read_csv(USER_FEEDBACK_PATH) if USER_FEEDBACK_PATH.exists() else pd.DataFrame(columns=feedback.columns)
    combined = pd.concat([existing, feedback], ignore_index=True)
    combined = combined.drop_duplicates(subset=["smiles", "biodegradable"], keep="first")
    total_rows = int(len(combined))
    queued_rows = int(total_rows - len(existing))
    write_dataframe(USER_FEEDBACK_PATH, combined)
    return {
        "consent_learning": True,
        "queued_rows": queued_rows,
        "total_rows": total_rows,
        "path": str(USER_FEEDBACK_PATH),
        "message": "Labeled rows were added to the explicit learning queue.",
    }


def persist_pipeline_artifacts(
    run_id: str,
    upload_df: pd.DataFrame,
    result: dict[str, Any],
    generated: pd.DataFrame | None = None,
    processed: pd.DataFrame | None = None,
    scored: pd.DataFrame | None = None,
    bundle: dict[str, Any] | None = None,
    expose_latest: bool = False,
) -> dict[str, str]:
    run_dir = uploaded_session_dir(run_id, create=True)

    artifact_paths = {
        "run_dir": str(run_dir),
        "upload_csv": str(run_dir / "uploaded_dataset.csv"),
        "result_json": str(run_dir / "result.json"),
    }

    write_dataframe(run_dir / "uploaded_dataset.csv", upload_df)
    write_json_log(run_dir / "result.json", result)

    if expose_latest:
        artifact_paths["latest_result_json"] = write_latest_result(result)

    if generated is not None:
        artifact_paths["generated_candidates_csv"] = str(run_dir / "generated_candidates.csv")
        write_dataframe(run_dir / "generated_candidates.csv", generated)

    if processed is not None:
        artifact_paths["processed_candidates_csv"] = str(run_dir / "processed_candidates.csv")
        write_dataframe(run_dir / "processed_candidates.csv", processed)

    if scored is not None:
        artifact_paths["scored_candidates_csv"] = str(run_dir / "scored_candidates.csv")
        write_dataframe(run_dir / "scored_candidates.csv", scored)

    if bundle is not None:
        bundle_name = "rf_regression_model_v1.joblib" if str(bundle.get("model_kind") or "").strip().lower() == "regression" else "rf_model_v1.joblib"
        artifact_paths["model_bundle"] = str(run_dir / bundle_name)
        artifact_paths["evaluation_summary"] = str(run_dir / "evaluation_summary.json")
        from system.services.training_service import save_model_bundle

        save_model_bundle(bundle, run_dir / bundle_name)
        bundle["artifact_refs"] = {
            "model_bundle": artifact_paths["model_bundle"],
            "evaluation_summary": artifact_paths["evaluation_summary"],
        }
        write_evaluation_summary(run_dir / "evaluation_summary.json", bundle)

    if result.get("decision_output"):
        artifact_paths["decision_output_json"] = str(run_dir / "decision_output.json")
        write_decision_artifact(run_dir / "decision_output.json", result["decision_output"])

    if result.get("upload_session_summary"):
        artifact_paths["upload_session_summary_json"] = str(run_dir / "upload_session_summary.json")
        write_json_log(run_dir / "upload_session_summary.json", result["upload_session_summary"])
        artifact_paths["upload_session_summary_report_json"] = write_session_report_copy(
            run_id,
            "upload_session_summary.json",
            result["upload_session_summary"],
        )

    if result.get("analysis_report"):
        artifact_paths["analysis_report_json"] = str(run_dir / "analysis_report.json")
        write_json_log(run_dir / "analysis_report.json", result["analysis_report"])
        artifact_paths["analysis_report_copy_json"] = write_session_report_copy(
            run_id,
            "analysis_report.json",
            result["analysis_report"],
        )

    return artifact_paths


__all__ = [
    "ALLOWED_ARTIFACT_ROOTS_ENV",
    "DATA_DIR",
    "DEFAULT_CANDIDATE_PATH",
    "DEFAULT_DECISION_OUTPUT_PATH",
    "DEFAULT_EVALUATION_PATH",
    "DEFAULT_GENERATED_CANDIDATE_PATH",
    "DEFAULT_ITERATION_HISTORY_PATH",
    "DEFAULT_LABELED_CANDIDATE_PATH",
    "DEFAULT_LOG_PATH",
    "DEFAULT_MODEL_PATH",
    "DEFAULT_PREDICTED_CANDIDATE_PATH",
    "DEFAULT_PROCESSED_CANDIDATE_PATH",
    "DEFAULT_RESULTS_PATH",
    "DEFAULT_REVIEW_QUEUE_PATH",
    "DEFAULT_RUN_CONFIG_PATH",
    "LATEST_RESULT_NAME",
    "LEGACY_UPLOADED_SESSIONS_DIR",
    "PAID_REQUESTS_DIR",
    "REPO_ROOT",
    "REPORTS_DIR",
    "UPLOADED_SESSIONS_DIR",
    "USER_FEEDBACK_PATH",
    "artifact_display_path",
    "register_artifact_root",
    "artifact_storage_roots",
    "ensure_safe_artifact_path",
    "ensure_artifact_directories",
    "flatten_iteration_record",
    "latest_result_path",
    "paid_request_dir",
    "persist_pipeline_artifacts",
    "queue_feedback_rows",
    "report_path",
    "uploaded_session_dir",
    "write_csv_artifact",
    "write_dataframe",
    "write_decision_artifact",
    "write_evaluation_summary",
    "write_iteration_history",
    "write_json_artifact",
    "write_json_log",
    "write_latest_result",
    "write_paid_request_artifacts",
    "write_review_queue_artifact",
    "write_run_config",
    "write_session_report_copy",
    "write_training_summary_artifact",
    "write_upload_inspection_artifact",
    "write_validated_json_artifact",
]
