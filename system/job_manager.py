from __future__ import annotations

import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any, Callable

from system.contracts import ContractValidationError, JobStatus
from system.db.repositories import ArtifactRepository, JobRepository, SessionRepository
from system.run_pipeline import run_pipeline
from system.upload_parser import load_session_dataframe, load_session_metadata, session_dir, session_id_now


PipelineRunner = Callable[..., dict[str, Any]]
logger = logging.getLogger(__name__)
_PATH_RE = re.compile(r"(/[^\s]+|[A-Za-z]:\\[^\s]+)")


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
            progress_message="Queued for execution.",
        )
        self.session_repository.upsert_session(
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            source_name=source_name,
            input_type=str((analysis_options or {}).get("input_type") or ""),
            latest_job_id=job["job_id"],
            summary_metadata={"last_job_status": job["status"], "last_error": ""},
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

        self.store.update_job(
            job_id,
            status=JobStatus.running.value,
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
            summary_metadata={"last_job_status": JobStatus.running.value, "last_error": ""},
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
            self.store.update_job(job_id, progress_message="Running scientific analysis pipeline.")
            result = self.pipeline_runner(
                dataframe,
                persist_artifacts=True,
                update_discovery_snapshot=False,
                source_name=resolved_source_name,
                analysis_options=options,
            )
        except Exception as exc:
            logger.exception("Analysis job %s failed during pipeline execution", job_id)
            error_message = self._safe_job_error(exc)
            self.store.update_job(
                job_id,
                status=JobStatus.failed.value,
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
                summary_metadata={"last_job_status": JobStatus.failed.value, "last_error": error_message},
            )
            return None

        try:
            self.artifact_repository.register_artifacts(
                artifact_refs=result.get("artifacts") or {},
                session_id=session_id,
                job_id=job_id,
                workspace_id=workspace_id,
                created_by_user_id=job.get("created_by_user_id") or None,
            )
        except Exception as exc:
            logger.exception("Analysis job %s failed while registering artifacts", job_id)
            error_message = self._safe_job_error(exc)
            self.store.update_job(
                job_id,
                status=JobStatus.failed.value,
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
                summary_metadata={"last_job_status": JobStatus.failed.value, "last_error": error_message},
            )
            return None

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
                "mode": result.get("mode"),
                "summary": result.get("summary") or {},
                "warnings": result.get("warnings") or [],
                "analysis_report": result.get("analysis_report") or {},
                "upload_session_summary": result.get("upload_session_summary") or {},
            },
        )
        self.store.update_job(
            job_id,
            status=JobStatus.succeeded.value,
            progress_message=str(result.get("message") or "Analysis completed."),
            error="",
            artifact_refs=artifact_refs,
        )
        return result

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
