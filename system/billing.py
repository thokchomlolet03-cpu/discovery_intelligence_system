from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from system.contracts import WorkspacePlanStatus, WorkspacePlanTier, WorkspaceUsageEventType
from system.db.repositories import SessionRepository, WorkspaceRepository, WorkspaceUsageRepository


FEATURE_CANDIDATE_RANKING = "candidate_ranking"
FEATURE_CANDIDATE_GENERATION = "candidate_generation"
FEATURE_DECISION_EXPORT = "decision_export"
FEATURE_DASHBOARD_ACCESS = "dashboard_access"

LIMIT_MONTHLY_ANALYSIS_JOBS = "monthly_analysis_jobs"
LIMIT_MONTHLY_GENERATION_JOBS = "monthly_candidate_generation_jobs"
LIMIT_MAX_UPLOAD_ROWS = "max_upload_rows"
LIMIT_MAX_STORED_SESSIONS = "max_stored_sessions"


@dataclass(frozen=True)
class PlanDefinition:
    tier: str
    display_name: str
    features: dict[str, bool]
    limits: dict[str, int | None]


PLAN_DEFINITIONS: dict[str, PlanDefinition] = {
    WorkspacePlanTier.free.value: PlanDefinition(
        tier=WorkspacePlanTier.free.value,
        display_name="Free",
        features={
            FEATURE_CANDIDATE_RANKING: True,
            FEATURE_CANDIDATE_GENERATION: False,
            FEATURE_DECISION_EXPORT: False,
            FEATURE_DASHBOARD_ACCESS: True,
        },
        limits={
            LIMIT_MONTHLY_ANALYSIS_JOBS: 8,
            LIMIT_MONTHLY_GENERATION_JOBS: 0,
            LIMIT_MAX_UPLOAD_ROWS: 250,
            LIMIT_MAX_STORED_SESSIONS: 5,
        },
    ),
    WorkspacePlanTier.pro.value: PlanDefinition(
        tier=WorkspacePlanTier.pro.value,
        display_name="Pro",
        features={
            FEATURE_CANDIDATE_RANKING: True,
            FEATURE_CANDIDATE_GENERATION: True,
            FEATURE_DECISION_EXPORT: True,
            FEATURE_DASHBOARD_ACCESS: True,
        },
        limits={
            LIMIT_MONTHLY_ANALYSIS_JOBS: 250,
            LIMIT_MONTHLY_GENERATION_JOBS: 60,
            LIMIT_MAX_UPLOAD_ROWS: 5000,
            LIMIT_MAX_STORED_SESSIONS: 200,
        },
    ),
    WorkspacePlanTier.internal.value: PlanDefinition(
        tier=WorkspacePlanTier.internal.value,
        display_name="Internal",
        features={
            FEATURE_CANDIDATE_RANKING: True,
            FEATURE_CANDIDATE_GENERATION: True,
            FEATURE_DECISION_EXPORT: True,
            FEATURE_DASHBOARD_ACCESS: True,
        },
        limits={
            LIMIT_MONTHLY_ANALYSIS_JOBS: None,
            LIMIT_MONTHLY_GENERATION_JOBS: None,
            LIMIT_MAX_UPLOAD_ROWS: None,
            LIMIT_MAX_STORED_SESSIONS: None,
        },
    ),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def billing_period_start(now: datetime | None = None) -> datetime:
    current = now or _utc_now()
    target = current.astimezone(timezone.utc) if current.tzinfo else current.replace(tzinfo=timezone.utc)
    return target.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def billing_period_end(now: datetime | None = None) -> datetime:
    start = billing_period_start(now)
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)


class PlanEnforcementError(PermissionError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        plan_tier: str,
        effective_plan_tier: str,
        upgrade_required: bool = True,
        feature: str | None = None,
        limit: int | None = None,
        current: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.plan_tier = plan_tier
        self.effective_plan_tier = effective_plan_tier
        self.upgrade_required = upgrade_required
        self.feature = feature
        self.limit = limit
        self.current = current

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "code": self.code,
            "message": self.message,
            "plan_tier": self.plan_tier,
            "effective_plan_tier": self.effective_plan_tier,
            "upgrade_required": self.upgrade_required,
        }
        if self.feature:
            payload["feature"] = self.feature
        if self.limit is not None:
            payload["limit"] = self.limit
        if self.current is not None:
            payload["current"] = self.current
        return payload


class WorkspaceBillingService:
    def __init__(
        self,
        *,
        workspace_repository: WorkspaceRepository | None = None,
        session_repository: SessionRepository | None = None,
        usage_repository: WorkspaceUsageRepository | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository or WorkspaceRepository()
        self.session_repository = session_repository or SessionRepository()
        self.usage_repository = usage_repository or WorkspaceUsageRepository()

    def _resolve_workspace(self, workspace: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(workspace, dict):
            return dict(workspace)
        return self.workspace_repository.get_workspace(str(workspace))

    def effective_plan_tier(self, workspace: str | dict[str, Any]) -> str:
        record = self._resolve_workspace(workspace)
        requested_tier = str(record.get("plan_tier") or WorkspacePlanTier.free.value).strip().lower()
        status = str(record.get("plan_status") or WorkspacePlanStatus.active.value).strip().lower()
        if requested_tier == WorkspacePlanTier.internal.value:
            return WorkspacePlanTier.internal.value
        if status in {WorkspacePlanStatus.past_due.value, WorkspacePlanStatus.canceled.value}:
            return WorkspacePlanTier.free.value
        if requested_tier not in PLAN_DEFINITIONS:
            return WorkspacePlanTier.free.value
        return requested_tier

    def definition_for(self, workspace: str | dict[str, Any]) -> PlanDefinition:
        return PLAN_DEFINITIONS[self.effective_plan_tier(workspace)]

    def usage_snapshot(self, workspace_id: str, *, now: datetime | None = None) -> dict[str, Any]:
        period_start = billing_period_start(now)
        period_end = billing_period_end(now)
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "analysis_jobs_this_month": self.usage_repository.sum_quantity(
                workspace_id=workspace_id,
                event_type=WorkspaceUsageEventType.analysis_job_created.value,
                created_at_gte=period_start,
                created_at_lt=period_end,
            ),
            "candidate_generation_jobs_this_month": self.usage_repository.sum_quantity(
                workspace_id=workspace_id,
                event_type=WorkspaceUsageEventType.candidate_generation_requested.value,
                created_at_gte=period_start,
                created_at_lt=period_end,
            ),
            "uploads_this_month": self.usage_repository.sum_quantity(
                workspace_id=workspace_id,
                event_type=WorkspaceUsageEventType.upload_session_created.value,
                created_at_gte=period_start,
                created_at_lt=period_end,
            ),
            "uploaded_rows_this_month": self.usage_repository.sum_quantity(
                workspace_id=workspace_id,
                event_type=WorkspaceUsageEventType.upload_rows_uploaded.value,
                created_at_gte=period_start,
                created_at_lt=period_end,
            ),
            "exports_this_month": self.usage_repository.sum_quantity(
                workspace_id=workspace_id,
                event_type=WorkspaceUsageEventType.decision_exported.value,
                created_at_gte=period_start,
                created_at_lt=period_end,
            ),
            "stored_sessions": self.session_repository.count_sessions(workspace_id),
        }

    def plan_summary(self, workspace: str | dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
        record = self._resolve_workspace(workspace)
        definition = self.definition_for(record)
        return {
            "workspace_id": record["workspace_id"],
            "plan_tier": str(record.get("plan_tier") or WorkspacePlanTier.free.value),
            "effective_plan_tier": definition.tier,
            "plan_status": str(record.get("plan_status") or WorkspacePlanStatus.active.value),
            "external_billing_provider": str(record.get("external_billing_provider") or ""),
            "external_customer_ref": str(record.get("external_customer_ref") or ""),
            "external_subscription_ref": str(record.get("external_subscription_ref") or ""),
            "external_price_ref": str(record.get("external_price_ref") or ""),
            "provider_subscription_status": str(record.get("provider_subscription_status") or ""),
            "display_name": definition.display_name,
            "features": dict(definition.features),
            "limits": dict(definition.limits),
            "usage": self.usage_snapshot(record["workspace_id"], now=now),
            "trial_ends_at": record.get("trial_ends_at"),
            "current_period_ends_at": record.get("current_period_ends_at"),
            "billing_synced_at": record.get("billing_synced_at"),
            "billing_metadata": dict(record.get("billing_metadata") or {}),
        }

    def ensure_upload_allowed(
        self,
        workspace: str | dict[str, Any],
        *,
        upload_rows: int | None = None,
        creating_new_session: bool = True,
    ) -> dict[str, Any]:
        summary = self.plan_summary(workspace)
        if creating_new_session:
            limit = summary["limits"].get(LIMIT_MAX_STORED_SESSIONS)
            current = int(summary["usage"].get("stored_sessions", 0))
            if limit is not None and current >= limit:
                raise PlanEnforcementError(
                    code="session_limit_exceeded",
                    message=f"The {summary['display_name']} plan allows up to {limit} stored sessions. Upgrade to create additional upload sessions.",
                    status_code=403,
                    plan_tier=summary["plan_tier"],
                    effective_plan_tier=summary["effective_plan_tier"],
                    limit=limit,
                    current=current,
                )
        if upload_rows is not None:
            limit = summary["limits"].get(LIMIT_MAX_UPLOAD_ROWS)
            if limit is not None and int(upload_rows) > limit:
                raise PlanEnforcementError(
                    code="upload_too_large",
                    message=f"This workspace plan allows uploads up to {limit} rows. Upgrade to analyze larger datasets.",
                    status_code=413,
                    plan_tier=summary["plan_tier"],
                    effective_plan_tier=summary["effective_plan_tier"],
                    limit=limit,
                    current=int(upload_rows),
                )
        return summary

    def ensure_analysis_allowed(self, workspace: str | dict[str, Any], *, intent: str) -> dict[str, Any]:
        summary = self.plan_summary(workspace)
        normalized_intent = str(intent or "").strip().lower()
        if normalized_intent == "generate_candidates" and not summary["features"].get(FEATURE_CANDIDATE_GENERATION, False):
            raise PlanEnforcementError(
                code="feature_not_available",
                message="Candidate generation requires the Pro plan.",
                status_code=403,
                plan_tier=summary["plan_tier"],
                effective_plan_tier=summary["effective_plan_tier"],
                feature=FEATURE_CANDIDATE_GENERATION,
            )

        analysis_limit = summary["limits"].get(LIMIT_MONTHLY_ANALYSIS_JOBS)
        current_analyses = int(summary["usage"].get("analysis_jobs_this_month", 0))
        if analysis_limit is not None and current_analyses >= analysis_limit:
            raise PlanEnforcementError(
                code="monthly_analysis_limit_exceeded",
                message=f"The {summary['display_name']} plan allows {analysis_limit} analyses per month. Upgrade to continue running jobs this month.",
                status_code=429,
                plan_tier=summary["plan_tier"],
                effective_plan_tier=summary["effective_plan_tier"],
                limit=analysis_limit,
                current=current_analyses,
            )

        if normalized_intent == "generate_candidates":
            generation_limit = summary["limits"].get(LIMIT_MONTHLY_GENERATION_JOBS)
            current_generations = int(summary["usage"].get("candidate_generation_jobs_this_month", 0))
            if generation_limit is not None and current_generations >= generation_limit:
                raise PlanEnforcementError(
                    code="monthly_generation_limit_exceeded",
                    message=f"The {summary['display_name']} plan allows {generation_limit} candidate-generation runs per month. Upgrade to continue generating candidates.",
                    status_code=429,
                    plan_tier=summary["plan_tier"],
                    effective_plan_tier=summary["effective_plan_tier"],
                    limit=generation_limit,
                    current=current_generations,
                    feature=FEATURE_CANDIDATE_GENERATION,
                )
        return summary

    def ensure_export_allowed(self, workspace: str | dict[str, Any]) -> dict[str, Any]:
        summary = self.plan_summary(workspace)
        if not summary["features"].get(FEATURE_DECISION_EXPORT, False):
            raise PlanEnforcementError(
                code="feature_not_available",
                message="Decision-package export requires the Pro plan.",
                status_code=403,
                plan_tier=summary["plan_tier"],
                effective_plan_tier=summary["effective_plan_tier"],
                feature=FEATURE_DECISION_EXPORT,
            )
        return summary

    def record_upload_session(
        self,
        *,
        workspace_id: str,
        session_id: str,
        filename: str,
        input_type: str,
        row_count: int,
    ) -> None:
        self.usage_repository.record_event(
            workspace_id=workspace_id,
            event_type=WorkspaceUsageEventType.upload_session_created.value,
            quantity=1,
            session_id=session_id,
            metadata={"filename": filename, "input_type": input_type, "row_count": int(row_count)},
        )
        self.usage_repository.record_event(
            workspace_id=workspace_id,
            event_type=WorkspaceUsageEventType.upload_rows_uploaded.value,
            quantity=max(int(row_count), 0),
            session_id=session_id,
            metadata={"filename": filename, "input_type": input_type},
        )

    def record_analysis_job(
        self,
        *,
        workspace_id: str,
        session_id: str,
        job_id: str,
        intent: str,
        input_type: str,
    ) -> None:
        metadata = {"intent": intent, "input_type": input_type}
        self.usage_repository.record_event(
            workspace_id=workspace_id,
            event_type=WorkspaceUsageEventType.analysis_job_created.value,
            quantity=1,
            session_id=session_id,
            job_id=job_id,
            metadata=metadata,
        )
        if str(intent or "").strip().lower() == "generate_candidates":
            self.usage_repository.record_event(
                workspace_id=workspace_id,
                event_type=WorkspaceUsageEventType.candidate_generation_requested.value,
                quantity=1,
                session_id=session_id,
                job_id=job_id,
                metadata=metadata,
            )

    def record_export(self, *, workspace_id: str, session_id: str | None = None) -> None:
        self.usage_repository.record_event(
            workspace_id=workspace_id,
            event_type=WorkspaceUsageEventType.decision_exported.value,
            quantity=1,
            session_id=session_id,
            metadata={},
        )


billing_service = WorkspaceBillingService()


__all__ = [
    "FEATURE_CANDIDATE_GENERATION",
    "FEATURE_CANDIDATE_RANKING",
    "FEATURE_DASHBOARD_ACCESS",
    "FEATURE_DECISION_EXPORT",
    "LIMIT_MAX_STORED_SESSIONS",
    "LIMIT_MAX_UPLOAD_ROWS",
    "LIMIT_MONTHLY_ANALYSIS_JOBS",
    "LIMIT_MONTHLY_GENERATION_JOBS",
    "PLAN_DEFINITIONS",
    "PlanDefinition",
    "PlanEnforcementError",
    "WorkspaceBillingService",
    "billing_period_end",
    "billing_period_start",
    "billing_service",
]
