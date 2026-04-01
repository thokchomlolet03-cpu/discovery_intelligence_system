from __future__ import annotations

import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any, Callable

from system.contracts import ContractValidationError, JobStatus
from system.db.repositories import ArtifactRepository, JobRepository, SessionRepository
from system.run_pipeline import run_pipeline
from system.services.status_semantics_service import persisted_status_snapshot
from system.upload_parser import load_session_dataframe, load_session_metadata, session_dir, session_id_now


PipelineRunner = Callable[..., dict[str, Any]]
logger = logging.getLogger(__name__)
_PATH_RE = re.compile(r"(/[^\s]+|[A-Za-z]:\\[^\s]+)")
DEFAULT_JOB_STAGE = "queued"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobNotFoundError(FileNotFoundError):
    """Raised when job metadata cannot be found in the current store."""


class DatabaseJobStore:
    """Repository-backed job store that persists canonical JobState records in the DB."""

    def __init__(self, repository: JobRepository | None = None) -> None:
        self.repository = repository or JobRepository()

    def create_job(
        self,
        *,
        session_id: str,
        workspace_id: str | None = None,
        created_by_user_id: str | None = None,
        job_type: str = "analysis",
        progress_stage: str = DEFAULT_JOB_STAGE,
        progress_percent: int = 0,
        progress_message: str = "Queued for execution.",
        artifact_refs: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        timestamp = _utc_now()
        job_id = f"job_{session_id_now()}"
        return self.repository.create_job(
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            job_id=job_id,
            status=JobStatus.queued.value,
            created_at=timestamp,
            updated_at=timestamp,
            job_type=job_type,
            progress_stage=progress_stage,
            progress_percent=progress_percent,
            progress_message=progress_message,
            error="",
            artifact_refs=artifact_refs or {},
        )

    def get_job(self, job_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        try:
            return self.repository.get_job(job_id, workspace_id=workspace_id)
        except FileNotFoundError as exc:
            raise JobNotFoundError(str(exc)) from exc

    def update_job(self, job_id: str, **changes: Any) -> dict[str, Any]:
        try:
            return self.repository.update_job(job_id, **changes)
        except FileNotFoundError as exc:
            raise JobNotFoundError(str(exc)) from exc


class JobManager:
    """Coordinates job lifecycle, DB persistence, and background execution."""

    def __init__(
        self,
        store: DatabaseJobStore | None = None,
        pipeline_runner: PipelineRunner | None = None,
        session_repository: SessionRepository | None = None,
        artifact_repository: ArtifactRepository | None = None,
    ) -> None:
        self.store = store or DatabaseJobStore()
        self.pipeline_runner = pipeline_runner or run_pipeline
        self.session_repository = session_repository or SessionRepository()
        self.artifact_repository = artifact_repository or ArtifactRepository(session_repository=self.session_repository)

    def _artifact_metadata_by_type(self, result: dict[str, Any], options: dict[str, Any]) -> dict[str, dict[str, Any]]:
        summary = result.get("summary") or {}
        analysis_report = result.get("analysis_report") or {}
        decision_output = result.get("decision_output") or {}
        review_queue = result.get("review_queue") or {}
        upload_summary = result.get("upload_session_summary") or {}
        evaluation_summary = result.get("evaluation_summary") or {}
        return {
            "result_json": {
                "mode": result.get("mode") or "",
                "intent": options.get("intent") or "",
                "input_type": options.get("input_type") or "",
            },
            "decision_output_json": {
                "candidate_count": int((decision_output.get("summary") or {}).get("candidate_count", summary.get("scored_candidates", 0)) or 0),
                "top_experiment_value": float((decision_output.get("summary") or {}).get("top_experiment_value", 0.0) or 0.0),
                "intent": options.get("intent") or "",
                "input_type": options.get("input_type") or "",
            },
            "analysis_report_json": {
                "warnings_count": len(analysis_report.get("warnings") or []),
                "top_candidates_returned": int(analysis_report.get("top_candidates_returned", 0) or 0),
            },
            "analysis_report_copy_json": {
                "warnings_count": len(analysis_report.get("warnings") or []),
            },
            "upload_session_summary_json": {
                "semantic_mode": ((upload_summary.get("measurement_summary") or {}).get("semantic_mode") or ""),
            },
            "upload_session_summary_report_json": {
                "semantic_mode": ((upload_summary.get("measurement_summary") or {}).get("semantic_mode") or ""),
            },
            "review_queue_json": {
                "pending_review": int((review_queue.get("summary") or {}).get("pending_review", 0) or 0),
            },
            "review_queue_csv": {
                "pending_review": int((review_queue.get("summary") or {}).get("pending_review", 0) or 0),
            },
            "evaluation_summary": {
                "selected_model": ((evaluation_summary.get("selected_model") or {}).get("name") or ""),
            },
            "scored_candidates_csv": {
                "scored_candidates": int(summary.get("scored_candidates", 0) or 0),
            },
        }

    def get_job(self, job_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        return self.store.get_job(job_id, workspace_id=workspace_id)

    def start_analysis_job(
        self,
        *,
        session_id: str,
        workspace_id: str | None = None,
        created_by_user_id: str | None = None,
        source_name: str,
        analysis_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        options = {
            **(analysis_options or {}),
            "workspace_id": workspace_id,
            "created_by_user_id": created_by_user_id,
        }
        job = self.store.create_job(
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            job_type="analysis",
            progress_stage=DEFAULT_JOB_STAGE,
            progress_percent=0,
            progress_message="Queued for execution.",
        )
        self.session_repository.upsert_session(
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            source_name=source_name,
            input_type=str((analysis_options or {}).get("input_type") or ""),
            latest_job_id=job["job_id"],
            summary_metadata={
                "last_job_status": job["status"],
                "last_error": "",
                "status_semantics": persisted_status_snapshot(
                    status=job["status"],
                    progress_stage=DEFAULT_JOB_STAGE,
                    error="",
                    viewable_artifacts=False,
                ),
            },
        )
        thread = threading.Thread(
            target=self.run_analysis_job,
            kwargs={
                "job_id": job["job_id"],
                "source_name": source_name,
                "analysis_options": options,
            },
            daemon=True,
            name=f"analysis-job-{job['job_id']}",
        )
        thread.start()
        return job

    def run_analysis_job(
        self,
        *,
        job_id: str,
        source_name: str | None = None,
        analysis_options: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        job = self.store.get_job(job_id)
        session_id = job["session_id"]
        workspace_id = job.get("workspace_id") or None
        options = {
            **(analysis_options or {}),
            "session_id": session_id,
            "workspace_id": workspace_id,
            "created_by_user_id": job.get("created_by_user_id") or None,
        }

        self._update_job_progress(
            job_id,
            status=JobStatus.running.value,
            progress_stage="loading_session",
            progress_percent=4,
            progress_message="Loading upload session data.",
            error="",
        )
        self.session_repository.upsert_session(
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=job.get("created_by_user_id") or None,
            source_name=source_name or "",
            input_type=str(options.get("input_type") or ""),
            latest_job_id=job_id,
            summary_metadata={
                "last_job_status": JobStatus.running.value,
                "last_error": "",
                "status_semantics": persisted_status_snapshot(
                    status=JobStatus.running.value,
                    progress_stage="loading_session",
                    error="",
                    viewable_artifacts=False,
                ),
            },
        )

        try:
            metadata = load_session_metadata(session_id, workspace_id=workspace_id)
        except FileNotFoundError:
            metadata = {}

        resolved_source_name = source_name or str(
            metadata.get("filename") or (session_dir(session_id) / "raw_upload.csv").name
        )

        try:
            dataframe = load_session_dataframe(session_id, workspace_id=workspace_id)
            self._update_job_progress(
                job_id,
                progress_stage="preparing_dataset",
                progress_percent=8,
                progress_message="Upload session data loaded. Preparing analysis pipeline.",
            )
            result = self.pipeline_runner(
                dataframe,
                persist_artifacts=True,
                update_discovery_snapshot=False,
                source_name=resolved_source_name,
                analysis_options=options,
                progress_callback=self._build_progress_callback(job_id),
            )
        except Exception as exc:
            logger.exception("Analysis job %s failed during pipeline execution", job_id)
            error_message = self._safe_job_error(exc)
            current_job = self.store.get_job(job_id)
            self._update_job_progress(
                job_id,
                status=JobStatus.failed.value,
                progress_stage=current_job.get("progress_stage") or "preparing_dataset",
                progress_percent=int(current_job.get("progress_percent") or 0),
                progress_message="Analysis failed.",
                error=error_message,
                artifact_refs={},
            )
            self.session_repository.upsert_session(
                session_id=session_id,
                workspace_id=workspace_id,
                created_by_user_id=job.get("created_by_user_id") or None,
                source_name=resolved_source_name,
                input_type=str(options.get("input_type") or ""),
                latest_job_id=job_id,
                summary_metadata={
                    "last_job_status": JobStatus.failed.value,
                    "last_error": error_message,
                    "status_semantics": persisted_status_snapshot(
                        status=JobStatus.failed.value,
                        progress_stage=current_job.get("progress_stage") or "preparing_dataset",
                        error=error_message,
                        viewable_artifacts=False,
                    ),
                },
            )
            return None

        try:
            self._update_job_progress(
                job_id,
                progress_stage="finalizing_artifacts",
                progress_percent=98,
                progress_message="Registering generated artifacts with the control plane.",
            )
            saved_artifacts = self.artifact_repository.register_artifacts(
                artifact_refs=result.get("artifacts") or {},
                session_id=session_id,
                job_id=job_id,
                workspace_id=workspace_id,
                created_by_user_id=job.get("created_by_user_id") or None,
                metadata_by_type=self._artifact_metadata_by_type(result, options),
            )
        except Exception as exc:
            logger.exception("Analysis job %s failed while registering artifacts", job_id)
            error_message = self._safe_job_error(exc)
            self._update_job_progress(
                job_id,
                status=JobStatus.failed.value,
                progress_stage="finalizing_artifacts",
                progress_percent=98,
                progress_message="Analysis failed while finalizing artifacts.",
                error=error_message,
                artifact_refs={},
            )
            self.session_repository.upsert_session(
                session_id=session_id,
                workspace_id=workspace_id,
                created_by_user_id=job.get("created_by_user_id") or None,
                source_name=resolved_source_name,
                input_type=str(options.get("input_type") or ""),
                latest_job_id=job_id,
                summary_metadata={
                    "last_job_status": JobStatus.failed.value,
                    "last_error": error_message,
                    "status_semantics": persisted_status_snapshot(
                        status=JobStatus.failed.value,
                        progress_stage="finalizing_artifacts",
                        error=error_message,
                        viewable_artifacts=False,
                    ),
                },
            )
            return None

        artifact_index = {
            item["artifact_type"]: {
                "path": item["path"],
                "updated_at": item["updated_at"],
                "metadata": item.get("metadata", {}),
            }
            for item in saved_artifacts
        }
        artifact_refs = {
            **(result.get("artifacts") or {}),
            "discovery_url": str(result.get("discovery_url") or f"/discovery?session_id={session_id}"),
            "dashboard_url": str(result.get("dashboard_url") or f"/dashboard?session_id={session_id}"),
        }
        self.session_repository.upsert_session(
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=job.get("created_by_user_id") or None,
            source_name=resolved_source_name,
            input_type=str(options.get("input_type") or ""),
            latest_job_id=job_id,
            summary_metadata={
                "last_job_status": JobStatus.succeeded.value,
                "last_error": "",
                "status_semantics": persisted_status_snapshot(
                    status=JobStatus.succeeded.value,
                    progress_stage="completed",
                    error="",
                    viewable_artifacts=True,
                ),
                "mode": result.get("mode"),
                "summary": result.get("summary") or {},
                "warnings": result.get("warnings") or [],
                "target_definition": result.get("target_definition") or {},
                "decision_intent": result.get("decision_intent") or "",
                "modeling_mode": result.get("modeling_mode") or "",
                "contract_versions": result.get("contract_versions") or {},
                "run_contract": result.get("run_contract") or {},
                "comparison_anchors": result.get("comparison_anchors") or {},
                "analysis_report": result.get("analysis_report") or {},
                "upload_session_summary": result.get("upload_session_summary") or {},
                "artifact_index": artifact_index,
            },
        )
        self.store.update_job(
            job_id,
            status=JobStatus.succeeded.value,
            progress_stage="completed",
            progress_percent=100,
            progress_message=str(result.get("message") or "Analysis completed."),
            error="",
            artifact_refs=artifact_refs,
        )
        return result

    def _build_progress_callback(self, job_id: str) -> Callable[[str, str, int], None]:
        def _progress_callback(stage: str, message: str, percent: int) -> None:
            self._update_job_progress(
                job_id,
                progress_stage=stage,
                progress_percent=percent,
                progress_message=message,
            )

        return _progress_callback

    def _update_job_progress(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress_stage: str | None = None,
        progress_percent: int | None = None,
        progress_message: str | None = None,
        error: str | None = None,
        artifact_refs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        changes: dict[str, Any] = {}
        if status is not None:
            changes["status"] = status
        if progress_stage is not None:
            changes["progress_stage"] = progress_stage
        if progress_percent is not None:
            changes["progress_percent"] = max(0, min(100, int(progress_percent)))
        if progress_message is not None:
            changes["progress_message"] = progress_message
        if error is not None:
            changes["error"] = error
        if artifact_refs is not None:
            changes["artifact_refs"] = artifact_refs
        return self.store.update_job(job_id, **changes)

    @staticmethod
    def _safe_job_error(exc: Exception) -> str:
        if isinstance(exc, ContractValidationError):
            message = "Pipeline contract validation failed."
        elif isinstance(exc, FileNotFoundError):
            message = "A required pipeline input or artifact is missing."
        else:
            raw = " ".join(str(exc).split())
            raw = _PATH_RE.sub("[path]", raw)
            if any(marker in raw.lower() for marker in ("traceback", "sqlalchemy", "sqlite", "psycopg")):
                raw = ""
            message = raw or "Analysis failed during pipeline execution."
        return f"{type(exc).__name__}: {message[:240]}"
