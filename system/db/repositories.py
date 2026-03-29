from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError

from system.contracts import (
    validate_artifact_pointer,
    validate_job_state,
    validate_review_event_record,
    validate_session_metadata,
    validate_user_record,
    validate_workspace_membership_record,
    validate_workspace_record,
    validate_workspace_usage_event_record,
)
from system.db.models import (
    ArtifactRecordModel,
    BillingWebhookEventModel,
    JobModel,
    ReviewEventModel,
    SessionModel,
    UserModel,
    WorkspaceMembershipModel,
    WorkspaceModel,
    WorkspaceUsageEventModel,
)
from system.db.session import session_scope


LEGACY_WORKSPACE_ID = "legacy_workspace"
DEFAULT_WORKSPACE_ROLE = "member"
_UNSET = object()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _merge_dicts(existing: dict[str, Any] | None, incoming: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(existing or {})
    if incoming:
        merged.update(dict(incoming))
    return merged


def _normalize_path(value: str | Path) -> str:
    from system.services.artifact_service import ensure_safe_artifact_path

    return str(ensure_safe_artifact_path(value, require_exists=True))


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _user_payload(record: UserModel) -> dict[str, Any]:
    return validate_user_record(
        {
            "user_id": record.user_id,
            "email": record.email,
            "display_name": record.display_name,
            "is_active": record.is_active,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def _workspace_payload(record: WorkspaceModel) -> dict[str, Any]:
    return validate_workspace_record(
        {
            "workspace_id": record.workspace_id,
            "name": record.name,
            "owner_user_id": record.owner_user_id or "",
            "plan_tier": record.plan_tier,
            "plan_status": record.plan_status,
            "trial_ends_at": record.trial_ends_at,
            "current_period_ends_at": record.current_period_ends_at,
            "external_billing_provider": record.external_billing_provider or "",
            "external_customer_ref": record.external_customer_ref or "",
            "external_subscription_ref": record.external_subscription_ref or "",
            "external_price_ref": record.external_price_ref or "",
            "provider_subscription_status": record.provider_subscription_status or "",
            "billing_synced_at": record.billing_synced_at,
            "billing_metadata": record.billing_metadata or {},
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def _membership_payload(record: WorkspaceMembershipModel) -> dict[str, Any]:
    return validate_workspace_membership_record(
        {
            "workspace_id": record.workspace_id,
            "user_id": record.user_id,
            "role": record.role,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def _session_payload(record: SessionModel) -> dict[str, Any]:
    return validate_session_metadata(
        {
            "session_id": record.session_id,
            "workspace_id": record.workspace_id,
            "created_by_user_id": record.created_by_user_id or "",
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "source_name": record.source_name,
            "input_type": record.input_type,
            "latest_job_id": record.latest_job_id or "",
            "upload_metadata": record.upload_metadata or {},
            "summary_metadata": record.summary_metadata or {},
        }
    )


def _job_payload(record: JobModel) -> dict[str, Any]:
    return validate_job_state(
        {
            "job_id": record.job_id,
            "session_id": record.session_id,
            "workspace_id": record.workspace_id,
            "created_by_user_id": record.created_by_user_id or "",
            "status": record.status,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "job_type": record.job_type,
            "progress_message": record.progress_message,
            "error": record.error,
            "artifact_refs": record.artifact_refs or {},
        }
    )


def _review_payload(record: ReviewEventModel) -> dict[str, Any]:
    return validate_review_event_record(
        {
            "session_id": record.session_id,
            "workspace_id": record.workspace_id,
            "candidate_id": record.candidate_id,
            "smiles": record.smiles,
            "action": record.action,
            "previous_status": record.previous_status,
            "status": record.status,
            "note": record.note,
            "timestamp": record.timestamp,
            "reviewed_at": record.reviewed_at,
            "actor": record.actor,
            "reviewer": record.reviewer,
            "actor_user_id": record.actor_user_id or "",
            "metadata": record.metadata_json or {},
        }
    )


def _artifact_payload(record: ArtifactRecordModel) -> dict[str, Any]:
    return validate_artifact_pointer(
        {
            "session_id": record.session_id or "",
            "job_id": record.job_id or "",
            "workspace_id": record.workspace_id,
            "created_by_user_id": record.created_by_user_id or "",
            "artifact_type": record.artifact_type,
            "path": record.path,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "metadata": record.metadata_json or {},
        }
    )


def _workspace_usage_payload(record: WorkspaceUsageEventModel) -> dict[str, Any]:
    return validate_workspace_usage_event_record(
        {
            "workspace_id": record.workspace_id,
            "event_type": record.event_type,
            "quantity": record.quantity,
            "created_at": record.created_at,
            "session_id": record.session_id or "",
            "job_id": record.job_id or "",
            "metadata": record.metadata_json or {},
        }
    )


class UserRepository:
    def count_users(self) -> int:
        with session_scope() as db:
            return int(db.execute(select(func.count()).select_from(UserModel)).scalar_one())

    def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str = "",
        is_active: bool = True,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        with session_scope() as db:
            record = UserModel(
                user_id=user_id or _make_id("user"),
                email=str(email).strip().lower(),
                display_name=str(display_name).strip(),
                password_hash=password_hash,
                is_active=bool(is_active),
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _user_payload(record)

    def get_user(self, user_id: str) -> dict[str, Any]:
        with session_scope() as db:
            record = db.get(UserModel, user_id)
            if record is None:
                raise FileNotFoundError(f"No persisted user found for '{user_id}'.")
            return _user_payload(record)

    def get_user_credentials_by_email(self, email: str) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(UserModel).where(UserModel.email == str(email).strip().lower())
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No persisted user found for '{email}'.")
            return {
                **_user_payload(record),
                "password_hash": record.password_hash,
            }

    def set_user_active(self, user_id: str, *, is_active: bool) -> dict[str, Any]:
        with session_scope() as db:
            record = db.get(UserModel, user_id)
            if record is None:
                raise FileNotFoundError(f"No persisted user found for '{user_id}'.")
            record.is_active = bool(is_active)
            record.updated_at = _utc_now()
            db.add(record)
            db.flush()
            db.refresh(record)
            return _user_payload(record)


class WorkspaceRepository:
    def create_workspace(
        self,
        *,
        name: str,
        owner_user_id: str | None = None,
        plan_tier: str = "free",
        plan_status: str = "active",
        trial_ends_at: datetime | None = None,
        current_period_ends_at: datetime | None = None,
        external_billing_provider: str | None = None,
        external_customer_ref: str | None = None,
        external_subscription_ref: str | None = None,
        external_price_ref: str | None = None,
        provider_subscription_status: str | None = None,
        billing_synced_at: datetime | None = None,
        billing_metadata: dict[str, Any] | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        with session_scope() as db:
            record = WorkspaceModel(
                workspace_id=workspace_id or _make_id("ws"),
                name=str(name).strip(),
                owner_user_id=owner_user_id or None,
                plan_tier=str(plan_tier).strip().lower() or "free",
                plan_status=str(plan_status).strip().lower() or "active",
                trial_ends_at=trial_ends_at,
                current_period_ends_at=current_period_ends_at,
                external_billing_provider=str(external_billing_provider or "").strip().lower() or None,
                external_customer_ref=str(external_customer_ref or "").strip() or None,
                external_subscription_ref=str(external_subscription_ref or "").strip() or None,
                external_price_ref=str(external_price_ref or "").strip() or None,
                provider_subscription_status=str(provider_subscription_status or "").strip().lower() or None,
                billing_synced_at=billing_synced_at,
                billing_metadata=dict(billing_metadata or {}),
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _workspace_payload(record)

    def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        with session_scope() as db:
            record = db.get(WorkspaceModel, workspace_id)
            if record is None:
                raise FileNotFoundError(f"No persisted workspace found for '{workspace_id}'.")
            return _workspace_payload(record)

    def update_workspace_plan(
        self,
        workspace_id: str,
        *,
        plan_tier: str | None = None,
        plan_status: str | None = None,
        trial_ends_at: datetime | None | object = _UNSET,
        current_period_ends_at: datetime | None | object = _UNSET,
        external_billing_provider: str | None | object = _UNSET,
        external_customer_ref: str | None | object = _UNSET,
        external_subscription_ref: str | None | object = _UNSET,
        external_price_ref: str | None | object = _UNSET,
        provider_subscription_status: str | None | object = _UNSET,
        billing_synced_at: datetime | None | object = _UNSET,
        billing_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with session_scope() as db:
            record = db.get(WorkspaceModel, workspace_id)
            if record is None:
                raise FileNotFoundError(f"No persisted workspace found for '{workspace_id}'.")
            if plan_tier is not None:
                record.plan_tier = str(plan_tier).strip().lower() or "free"
            if plan_status is not None:
                record.plan_status = str(plan_status).strip().lower() or "active"
            if trial_ends_at is not _UNSET:
                record.trial_ends_at = trial_ends_at
            if current_period_ends_at is not _UNSET:
                record.current_period_ends_at = current_period_ends_at
            if external_billing_provider is not _UNSET:
                record.external_billing_provider = str(external_billing_provider or "").strip().lower() or None
            if external_customer_ref is not _UNSET:
                record.external_customer_ref = str(external_customer_ref or "").strip() or None
            if external_subscription_ref is not _UNSET:
                record.external_subscription_ref = str(external_subscription_ref or "").strip() or None
            if external_price_ref is not _UNSET:
                record.external_price_ref = str(external_price_ref or "").strip() or None
            if provider_subscription_status is not _UNSET:
                record.provider_subscription_status = str(provider_subscription_status or "").strip().lower() or None
            if billing_synced_at is not _UNSET:
                record.billing_synced_at = billing_synced_at
            if billing_metadata is not None:
                record.billing_metadata = _merge_dicts(record.billing_metadata, billing_metadata)
            record.updated_at = _utc_now()
            db.add(record)
            db.flush()
            db.refresh(record)
            return _workspace_payload(record)

    def get_workspace_by_external_subscription_ref(
        self,
        external_subscription_ref: str,
        *,
        provider: str | None = None,
    ) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(WorkspaceModel).where(
                WorkspaceModel.external_subscription_ref == str(external_subscription_ref).strip()
            )
            if provider is not None:
                statement = statement.where(WorkspaceModel.external_billing_provider == str(provider).strip().lower())
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(
                    f"No persisted workspace found for subscription '{external_subscription_ref}'."
                )
            return _workspace_payload(record)

    def get_workspace_by_external_customer_ref(
        self,
        external_customer_ref: str,
        *,
        provider: str | None = None,
    ) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(WorkspaceModel).where(
                WorkspaceModel.external_customer_ref == str(external_customer_ref).strip()
            )
            if provider is not None:
                statement = statement.where(WorkspaceModel.external_billing_provider == str(provider).strip().lower())
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(
                    f"No persisted workspace found for customer '{external_customer_ref}'."
                )
            return _workspace_payload(record)

    def add_membership(self, *, workspace_id: str, user_id: str, role: str = DEFAULT_WORKSPACE_ROLE) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(WorkspaceMembershipModel).where(
                WorkspaceMembershipModel.workspace_id == workspace_id,
                WorkspaceMembershipModel.user_id == user_id,
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                record = WorkspaceMembershipModel(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    role=str(role).strip().lower(),
                    created_at=_utc_now(),
                    updated_at=_utc_now(),
                )
            else:
                record.role = str(role).strip().lower()
                record.updated_at = _utc_now()
            db.add(record)
            db.flush()
            db.refresh(record)
            return _membership_payload(record)

    def get_membership(self, *, workspace_id: str, user_id: str) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(WorkspaceMembershipModel).where(
                WorkspaceMembershipModel.workspace_id == workspace_id,
                WorkspaceMembershipModel.user_id == user_id,
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"User '{user_id}' is not a member of workspace '{workspace_id}'.")
            return _membership_payload(record)

    def remove_membership(self, *, workspace_id: str, user_id: str) -> None:
        with session_scope() as db:
            statement = select(WorkspaceMembershipModel).where(
                WorkspaceMembershipModel.workspace_id == workspace_id,
                WorkspaceMembershipModel.user_id == user_id,
            )
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"User '{user_id}' is not a member of workspace '{workspace_id}'.")
            db.delete(record)

    def list_user_workspaces(self, user_id: str) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = (
                select(WorkspaceMembershipModel, WorkspaceModel)
                .join(WorkspaceModel, WorkspaceMembershipModel.workspace_id == WorkspaceModel.workspace_id)
                .where(WorkspaceMembershipModel.user_id == user_id)
                .order_by(WorkspaceModel.created_at.asc())
            )
            rows = db.execute(statement).all()
            return [
                {
                    "workspace": _workspace_payload(workspace),
                    "membership": _membership_payload(membership),
                }
                for membership, workspace in rows
            ]

    def user_has_workspace(self, *, workspace_id: str, user_id: str) -> bool:
        try:
            self.get_membership(workspace_id=workspace_id, user_id=user_id)
        except FileNotFoundError:
            return False
        return True

    def get_user_workspace(self, *, user_id: str, workspace_id: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        if workspace_id:
            membership = self.get_membership(workspace_id=workspace_id, user_id=user_id)
            workspace = self.get_workspace(workspace_id)
            return workspace, membership

        options = self.list_user_workspaces(user_id)
        if not options:
            raise FileNotFoundError(f"User '{user_id}' is not a member of any workspace.")
        first = options[0]
        return first["workspace"], first["membership"]

    def count_members(self, workspace_id: str) -> int:
        with session_scope() as db:
            statement = select(func.count()).select_from(WorkspaceMembershipModel).where(
                WorkspaceMembershipModel.workspace_id == workspace_id
            )
            return int(db.execute(statement).scalar_one())


class SessionRepository:
    def upsert_session(
        self,
        *,
        session_id: str,
        workspace_id: str | None = None,
        created_by_user_id: str | None = None,
        source_name: str | None = None,
        input_type: str | None = None,
        latest_job_id: str | None = None,
        upload_metadata: dict[str, Any] | None = None,
        summary_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        effective_workspace_id = workspace_id or LEGACY_WORKSPACE_ID
        with session_scope() as db:
            record = db.get(SessionModel, session_id)
            if record is None:
                record = SessionModel(
                    session_id=session_id,
                    workspace_id=effective_workspace_id,
                    created_by_user_id=created_by_user_id or None,
                    created_at=_utc_now(),
                    updated_at=_utc_now(),
                    source_name="",
                    input_type="",
                    latest_job_id=None,
                    upload_metadata={},
                    summary_metadata={},
                )
            elif workspace_id is not None and record.workspace_id != effective_workspace_id:
                raise ValueError(
                    f"Session '{session_id}' already belongs to workspace '{record.workspace_id}' and cannot be reassigned."
                )
            if workspace_id is not None:
                record.workspace_id = effective_workspace_id
            if created_by_user_id is not None:
                record.created_by_user_id = str(created_by_user_id) or None
            if source_name is not None:
                record.source_name = str(source_name)
            if input_type is not None:
                record.input_type = str(input_type)
            if latest_job_id is not None:
                record.latest_job_id = str(latest_job_id) or None
            if upload_metadata is not None:
                record.upload_metadata = _merge_dicts(record.upload_metadata, upload_metadata)
            if summary_metadata is not None:
                record.summary_metadata = _merge_dicts(record.summary_metadata, summary_metadata)
            record.updated_at = _utc_now()
            db.add(record)
            db.flush()
            db.refresh(record)
            return _session_payload(record)

    def get_session(self, session_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(SessionModel).where(SessionModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(SessionModel.workspace_id == workspace_id)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No persisted session metadata found for '{session_id}'.")
            return _session_payload(record)

    def count_sessions(self, workspace_id: str) -> int:
        with session_scope() as db:
            statement = select(func.count()).select_from(SessionModel).where(SessionModel.workspace_id == workspace_id)
            return int(db.execute(statement).scalar_one())


class JobRepository:
    def __init__(self, session_repository: SessionRepository | None = None) -> None:
        self.session_repository = session_repository or SessionRepository()

    def create_job(
        self,
        *,
        session_id: str,
        workspace_id: str | None = None,
        created_by_user_id: str | None = None,
        job_id: str,
        status: str,
        created_at: datetime,
        updated_at: datetime,
        job_type: str = "analysis",
        progress_message: str = "",
        error: str = "",
        artifact_refs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if workspace_id is None:
            try:
                workspace_id = self.session_repository.get_session(session_id)["workspace_id"]
            except FileNotFoundError:
                workspace_id = LEGACY_WORKSPACE_ID
        self.session_repository.upsert_session(
            session_id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            latest_job_id=job_id,
        )
        payload = validate_job_state(
            {
                "job_id": job_id,
                "session_id": session_id,
                "workspace_id": workspace_id,
                "created_by_user_id": created_by_user_id or "",
                "status": status,
                "created_at": created_at,
                "updated_at": updated_at,
                "job_type": job_type,
                "progress_message": progress_message,
                "error": error,
                "artifact_refs": artifact_refs or {},
            }
        )
        with session_scope() as db:
            record = JobModel(
                job_id=payload["job_id"],
                session_id=payload["session_id"],
                workspace_id=payload["workspace_id"] or LEGACY_WORKSPACE_ID,
                created_by_user_id=payload.get("created_by_user_id") or None,
                status=payload["status"],
                created_at=_to_datetime(payload["created_at"]),
                updated_at=_to_datetime(payload["updated_at"]),
                job_type=payload.get("job_type", ""),
                progress_message=payload.get("progress_message", ""),
                error=payload.get("error", ""),
                artifact_refs=payload.get("artifact_refs", {}),
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _job_payload(record)

    def get_job(self, job_id: str, workspace_id: str | None = None) -> dict[str, Any]:
        with session_scope() as db:
            statement = select(JobModel).where(JobModel.job_id == job_id)
            if workspace_id is not None:
                statement = statement.where(JobModel.workspace_id == workspace_id)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                raise FileNotFoundError(f"No persisted job metadata found for '{job_id}'.")
            return _job_payload(record)

    def update_job(self, job_id: str, **changes: Any) -> dict[str, Any]:
        with session_scope() as db:
            record = db.get(JobModel, job_id)
            if record is None:
                raise FileNotFoundError(f"No persisted job metadata found for '{job_id}'.")
            current = _job_payload(record)
            if "workspace_id" in changes and str(changes["workspace_id"] or "") != str(current.get("workspace_id") or ""):
                raise ValueError("Job workspace ownership is immutable.")
            if "created_by_user_id" in changes and str(changes["created_by_user_id"] or "") != str(current.get("created_by_user_id") or ""):
                raise ValueError("Job creator attribution is immutable.")
            payload = validate_job_state(
                {
                    **current,
                    **changes,
                    "job_id": current["job_id"],
                    "session_id": current["session_id"],
                    "workspace_id": changes.get("workspace_id", current.get("workspace_id", LEGACY_WORKSPACE_ID)),
                    "created_by_user_id": changes.get("created_by_user_id", current.get("created_by_user_id", "")),
                    "updated_at": _utc_now(),
                    "artifact_refs": changes.get("artifact_refs", current.get("artifact_refs", {})),
                }
            )
            record.workspace_id = payload.get("workspace_id") or LEGACY_WORKSPACE_ID
            record.created_by_user_id = payload.get("created_by_user_id") or None
            record.status = payload["status"]
            record.updated_at = _to_datetime(payload["updated_at"])
            record.job_type = payload.get("job_type", "")
            record.progress_message = payload.get("progress_message", "")
            record.error = payload.get("error", "")
            record.artifact_refs = payload.get("artifact_refs", {})
            db.add(record)
            db.flush()
            db.refresh(record)
            return _job_payload(record)


class ReviewRepository:
    def __init__(self, session_repository: SessionRepository | None = None) -> None:
        self.session_repository = session_repository or SessionRepository()

    def record_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_payload = validate_review_event_record(payload)
        if not record_payload.get("workspace_id"):
            try:
                record_payload["workspace_id"] = self.session_repository.get_session(record_payload["session_id"])["workspace_id"]
            except FileNotFoundError:
                record_payload["workspace_id"] = LEGACY_WORKSPACE_ID
        self.session_repository.upsert_session(
            session_id=record_payload["session_id"],
            workspace_id=record_payload["workspace_id"],
        )
        with session_scope() as db:
            record = ReviewEventModel(
                session_id=record_payload["session_id"],
                workspace_id=record_payload["workspace_id"] or LEGACY_WORKSPACE_ID,
                candidate_id=record_payload["candidate_id"],
                smiles=record_payload["smiles"],
                action=record_payload["action"],
                previous_status=record_payload.get("previous_status"),
                status=record_payload["status"],
                note=record_payload.get("note", ""),
                timestamp=_to_datetime(record_payload["timestamp"]),
                reviewed_at=_to_datetime(record_payload["reviewed_at"]),
                actor=record_payload.get("actor", "unassigned"),
                reviewer=record_payload.get("reviewer", "unassigned"),
                actor_user_id=record_payload.get("actor_user_id") or None,
                metadata_json=record_payload.get("metadata", {}),
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _review_payload(record)

    def record_reviews(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        for payload in payloads:
            created.append(self.record_review(payload))
        return created

    def list_reviews(self, session_id: str | None = None, workspace_id: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(ReviewEventModel).order_by(ReviewEventModel.reviewed_at.asc(), ReviewEventModel.id.asc())
            if session_id is not None:
                statement = statement.where(ReviewEventModel.session_id == session_id)
            if workspace_id is not None:
                statement = statement.where(ReviewEventModel.workspace_id == workspace_id)
            rows = db.execute(statement).scalars().all()
            return [_review_payload(row) for row in rows]


class WorkspaceUsageRepository:
    def record_event(
        self,
        *,
        workspace_id: str,
        event_type: str,
        quantity: int = 1,
        session_id: str | None = None,
        job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        payload = validate_workspace_usage_event_record(
            {
                "workspace_id": workspace_id,
                "event_type": event_type,
                "quantity": quantity,
                "created_at": created_at or _utc_now(),
                "session_id": session_id or "",
                "job_id": job_id or "",
                "metadata": metadata or {},
            }
        )
        with session_scope() as db:
            record = WorkspaceUsageEventModel(
                workspace_id=payload["workspace_id"],
                event_type=payload["event_type"],
                quantity=int(payload.get("quantity", 1)),
                created_at=_to_datetime(payload["created_at"]),
                session_id=payload.get("session_id") or None,
                job_id=payload.get("job_id") or None,
                metadata_json=payload.get("metadata", {}),
            )
            db.add(record)
            db.flush()
            db.refresh(record)
            return _workspace_usage_payload(record)

    def sum_quantity(
        self,
        *,
        workspace_id: str,
        event_type: str,
        created_at_gte: datetime | None = None,
        created_at_lt: datetime | None = None,
    ) -> int:
        with session_scope() as db:
            statement = select(func.coalesce(func.sum(WorkspaceUsageEventModel.quantity), 0)).where(
                WorkspaceUsageEventModel.workspace_id == workspace_id,
                WorkspaceUsageEventModel.event_type == str(event_type).strip().lower(),
            )
            if created_at_gte is not None:
                statement = statement.where(WorkspaceUsageEventModel.created_at >= created_at_gte)
            if created_at_lt is not None:
                statement = statement.where(WorkspaceUsageEventModel.created_at < created_at_lt)
            return int(db.execute(statement).scalar_one())

    def count_events(
        self,
        *,
        workspace_id: str,
        event_type: str,
        created_at_gte: datetime | None = None,
        created_at_lt: datetime | None = None,
    ) -> int:
        with session_scope() as db:
            statement = select(func.count()).select_from(WorkspaceUsageEventModel).where(
                WorkspaceUsageEventModel.workspace_id == workspace_id,
                WorkspaceUsageEventModel.event_type == str(event_type).strip().lower(),
            )
            if created_at_gte is not None:
                statement = statement.where(WorkspaceUsageEventModel.created_at >= created_at_gte)
            if created_at_lt is not None:
                statement = statement.where(WorkspaceUsageEventModel.created_at < created_at_lt)
            return int(db.execute(statement).scalar_one())

    def list_events(
        self,
        *,
        workspace_id: str,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(WorkspaceUsageEventModel).where(
                WorkspaceUsageEventModel.workspace_id == workspace_id
            ).order_by(WorkspaceUsageEventModel.created_at.asc(), WorkspaceUsageEventModel.id.asc())
            if event_type is not None:
                statement = statement.where(WorkspaceUsageEventModel.event_type == str(event_type).strip().lower())
            rows = db.execute(statement).scalars().all()
            return [_workspace_usage_payload(row) for row in rows]


class BillingWebhookEventRepository:
    def has_event(self, *, provider: str, event_id: str) -> bool:
        with session_scope() as db:
            statement = select(BillingWebhookEventModel.id).where(
                BillingWebhookEventModel.provider == str(provider).strip().lower(),
                BillingWebhookEventModel.event_id == str(event_id).strip(),
            )
            return db.execute(statement).scalar_one_or_none() is not None

    def record_processed_event(
        self,
        *,
        provider: str,
        event_id: str,
        event_type: str,
        workspace_id: str | None = None,
        payload: dict[str, Any] | None = None,
        processed_at: datetime | None = None,
    ) -> bool:
        with session_scope() as db:
            record = BillingWebhookEventModel(
                provider=str(provider).strip().lower(),
                event_id=str(event_id).strip(),
                event_type=str(event_type).strip().lower(),
                workspace_id=str(workspace_id or "").strip() or None,
                processed_at=processed_at or _utc_now(),
                payload_json=dict(payload or {}),
            )
            db.add(record)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                return False
            return True

    def list_events(self, *, provider: str | None = None) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(BillingWebhookEventModel).order_by(
                BillingWebhookEventModel.processed_at.asc(),
                BillingWebhookEventModel.id.asc(),
            )
            if provider is not None:
                statement = statement.where(BillingWebhookEventModel.provider == str(provider).strip().lower())
            rows = db.execute(statement).scalars().all()
            return [
                {
                    "provider": row.provider,
                    "event_id": row.event_id,
                    "event_type": row.event_type,
                    "workspace_id": row.workspace_id or "",
                    "processed_at": row.processed_at,
                    "payload": row.payload_json or {},
                }
                for row in rows
            ]


class ArtifactRepository:
    def __init__(
        self,
        session_repository: SessionRepository | None = None,
        job_repository: JobRepository | None = None,
    ) -> None:
        self.session_repository = session_repository or SessionRepository()
        self.job_repository = job_repository or JobRepository(session_repository=self.session_repository)

    def _resolve_workspace_id(self, *, session_id: str | None, job_id: str | None, workspace_id: str | None) -> str:
        if workspace_id:
            return workspace_id
        if session_id:
            try:
                return self.session_repository.get_session(session_id)["workspace_id"]
            except FileNotFoundError:
                pass
        if job_id:
            try:
                return self.job_repository.get_job(job_id)["workspace_id"]
            except FileNotFoundError:
                pass
        return LEGACY_WORKSPACE_ID

    def register_artifact(
        self,
        *,
        artifact_type: str,
        path: str | Path,
        session_id: str | None = None,
        job_id: str | None = None,
        workspace_id: str | None = None,
        created_by_user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_path = _normalize_path(path)
        if session_id:
            self.session_repository.upsert_session(session_id=session_id, workspace_id=workspace_id, created_by_user_id=created_by_user_id)
        effective_workspace_id = self._resolve_workspace_id(session_id=session_id, job_id=job_id, workspace_id=workspace_id)
        timestamp = _utc_now()

        with session_scope() as db:
            statement = select(ArtifactRecordModel).where(ArtifactRecordModel.path == normalized_path)
            record = db.execute(statement).scalar_one_or_none()
            if record is None:
                record = ArtifactRecordModel(
                    artifact_type=str(artifact_type),
                    path=normalized_path,
                    session_id=session_id,
                    job_id=job_id,
                    workspace_id=effective_workspace_id,
                    created_by_user_id=created_by_user_id or None,
                    created_at=timestamp,
                    updated_at=timestamp,
                    metadata_json=dict(metadata or {}),
                )
            else:
                if record.workspace_id != effective_workspace_id:
                    raise ValueError("Artifact metadata cannot be reassigned across workspaces.")
                if session_id and record.session_id and record.session_id != session_id:
                    raise ValueError("Artifact metadata cannot be reassigned across sessions.")
                if job_id and record.job_id and record.job_id != job_id and record.session_id != session_id:
                    raise ValueError("Artifact metadata cannot be reassigned across jobs.")
                record.artifact_type = str(artifact_type)
                record.session_id = session_id or record.session_id
                record.job_id = job_id or record.job_id
                record.workspace_id = effective_workspace_id
                record.created_by_user_id = created_by_user_id or record.created_by_user_id
                record.updated_at = timestamp
                record.metadata_json = _merge_dicts(record.metadata_json, metadata)

            db.add(record)
            db.flush()
            db.refresh(record)
            return _artifact_payload(record)

    def register_artifacts(
        self,
        *,
        artifact_refs: dict[str, Any],
        session_id: str | None = None,
        job_id: str | None = None,
        workspace_id: str | None = None,
        created_by_user_id: str | None = None,
        metadata_by_type: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        saved: list[dict[str, Any]] = []
        for artifact_type, value in dict(artifact_refs or {}).items():
            path_text = str(value or "").strip()
            if not path_text or artifact_type.endswith("_url") or "://" in path_text:
                continue
            saved.append(
                self.register_artifact(
                    artifact_type=artifact_type,
                    path=path_text,
                    session_id=session_id,
                    job_id=job_id,
                    workspace_id=workspace_id,
                    created_by_user_id=created_by_user_id,
                    metadata=(metadata_by_type or {}).get(artifact_type),
                )
            )
        return saved

    def get_latest_artifact(
        self,
        *,
        artifact_type: str,
        session_id: str | None = None,
        job_id: str | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any] | None:
        with session_scope() as db:
            statement = select(ArtifactRecordModel).where(ArtifactRecordModel.artifact_type == artifact_type)
            if session_id is not None:
                statement = statement.where(ArtifactRecordModel.session_id == session_id)
            if job_id is not None:
                statement = statement.where(ArtifactRecordModel.job_id == job_id)
            if workspace_id is not None:
                statement = statement.where(ArtifactRecordModel.workspace_id == workspace_id)
            statement = statement.order_by(desc(ArtifactRecordModel.updated_at), desc(ArtifactRecordModel.id))
            record = db.execute(statement).scalars().first()
            return _artifact_payload(record) if record is not None else None

    def get_latest_artifact_path(
        self,
        *,
        artifact_type: str,
        session_id: str | None = None,
        job_id: str | None = None,
        workspace_id: str | None = None,
    ) -> Path | None:
        artifact = self.get_latest_artifact(
            artifact_type=artifact_type,
            session_id=session_id,
            job_id=job_id,
            workspace_id=workspace_id,
        )
        if not artifact:
            return None
        try:
            from system.services.artifact_service import ensure_safe_artifact_path

            return ensure_safe_artifact_path(artifact["path"], require_exists=True)
        except (FileNotFoundError, ValueError):
            return None

    def list_artifacts(
        self,
        *,
        session_id: str | None = None,
        job_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with session_scope() as db:
            statement = select(ArtifactRecordModel).order_by(ArtifactRecordModel.updated_at.asc(), ArtifactRecordModel.id.asc())
            if session_id is not None:
                statement = statement.where(ArtifactRecordModel.session_id == session_id)
            if job_id is not None:
                statement = statement.where(ArtifactRecordModel.job_id == job_id)
            if workspace_id is not None:
                statement = statement.where(ArtifactRecordModel.workspace_id == workspace_id)
            rows = db.execute(statement).scalars().all()
            return [_artifact_payload(row) for row in rows]
