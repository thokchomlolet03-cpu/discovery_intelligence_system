from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from system.db.repositories import BillingWebhookEventRepository, WorkspaceRepository


PADDLE_PROVIDER = "paddle"
PADDLE_API_KEY_ENV = "PADDLE_API_KEY"
PADDLE_ENVIRONMENT_ENV = "PADDLE_ENVIRONMENT"
PADDLE_WEBHOOK_SECRET_ENV = "PADDLE_WEBHOOK_SECRET"
PADDLE_WEBHOOK_TOLERANCE_ENV = "PADDLE_WEBHOOK_TOLERANCE_SECONDS"
PADDLE_PRO_PRICE_ID_ENV = "PADDLE_PRO_PRICE_ID"
PADDLE_CHECKOUT_URL_ENV = "PADDLE_CHECKOUT_URL"
PADDLE_BILLING_RETURN_URL_ENV = "PADDLE_BILLING_RETURN_URL"
APP_BASE_URL_ENV = "DISCOVERY_APP_BASE_URL"

DEFAULT_WEBHOOK_TOLERANCE_SECONDS = 300
PADDLE_SANDBOX_API_BASE = "https://sandbox-api.paddle.com"
PADDLE_PRODUCTION_API_BASE = "https://api.paddle.com"

ACTIVE_PROVIDER_STATUSES = {"active", "completed"}
TRIALING_PROVIDER_STATUSES = {"trialing"}
PAST_DUE_PROVIDER_STATUSES = {"past_due", "paused", "unpaid", "payment_failed"}
CANCELED_PROVIDER_STATUSES = {"canceled", "inactive", "expired"}

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _coerce_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = _clean_text(value).replace("Z", "+00:00")
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class PaddleIntegrationError(RuntimeError):
    pass


class PaddleConfigurationError(PaddleIntegrationError):
    pass


class PaddleWebhookVerificationError(PaddleIntegrationError):
    pass


@dataclass(frozen=True)
class PaddleConfig:
    environment: str
    api_key: str
    webhook_secret: str
    pro_price_id: str
    app_base_url: str
    checkout_url: str
    billing_return_url: str
    webhook_tolerance_seconds: int

    @property
    def api_base_url(self) -> str:
        if self.environment == "production":
            return PADDLE_PRODUCTION_API_BASE
        return PADDLE_SANDBOX_API_BASE

    @property
    def checkout_enabled(self) -> bool:
        return bool(self.api_key and self.pro_price_id)

    @property
    def portal_enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def webhook_enabled(self) -> bool:
        return bool(self.webhook_secret)


def get_paddle_config() -> PaddleConfig:
    environment = _clean_text(os.getenv(PADDLE_ENVIRONMENT_ENV, "sandbox")).lower() or "sandbox"
    if environment not in {"sandbox", "production"}:
        environment = "sandbox"
    app_base_url = _clean_text(os.getenv(APP_BASE_URL_ENV)).rstrip("/")
    try:
        tolerance = int(_clean_text(os.getenv(PADDLE_WEBHOOK_TOLERANCE_ENV)) or DEFAULT_WEBHOOK_TOLERANCE_SECONDS)
    except ValueError:
        tolerance = DEFAULT_WEBHOOK_TOLERANCE_SECONDS
    billing_return_url = _clean_text(os.getenv(PADDLE_BILLING_RETURN_URL_ENV)).rstrip("/")
    if not billing_return_url and app_base_url:
        billing_return_url = f"{app_base_url}/billing"
    return PaddleConfig(
        environment=environment,
        api_key=_clean_text(os.getenv(PADDLE_API_KEY_ENV)),
        webhook_secret=_clean_text(os.getenv(PADDLE_WEBHOOK_SECRET_ENV)),
        pro_price_id=_clean_text(os.getenv(PADDLE_PRO_PRICE_ID_ENV)),
        app_base_url=app_base_url,
        checkout_url=_clean_text(os.getenv(PADDLE_CHECKOUT_URL_ENV)).rstrip("/"),
        billing_return_url=billing_return_url,
        webhook_tolerance_seconds=max(tolerance, 0),
    )


class PaddleBillingService:
    def __init__(
        self,
        *,
        workspace_repository: WorkspaceRepository | None = None,
        webhook_event_repository: BillingWebhookEventRepository | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository or WorkspaceRepository()
        self.webhook_event_repository = webhook_event_repository or BillingWebhookEventRepository()

    def config(self) -> PaddleConfig:
        return get_paddle_config()

    def checkout_available(self) -> bool:
        return self.config().checkout_enabled

    def management_available(self) -> bool:
        return self.config().portal_enabled

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        config = self.config()
        if not config.api_key:
            raise PaddleConfigurationError("Paddle API credentials are not configured.")

        url = f"{config.api_base_url}{path}"
        data = None
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Accept": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            logger.warning("Paddle API request failed (%s %s): %s", method.upper(), path, error_body)
            raise PaddleIntegrationError("Paddle rejected the billing request.") from exc
        except URLError as exc:
            logger.warning("Paddle API request failed (%s %s): %s", method.upper(), path, exc)
            raise PaddleIntegrationError("Paddle could not be reached.") from exc
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise PaddleIntegrationError("Paddle returned an invalid response.") from exc
        if not isinstance(parsed, dict):
            raise PaddleIntegrationError("Paddle returned an invalid response shape.")
        return parsed

    def _paddle_metadata(self, workspace: dict[str, Any]) -> dict[str, Any]:
        return dict((workspace.get("billing_metadata") or {}).get(PADDLE_PROVIDER) or {})

    def _merged_billing_metadata(self, workspace: dict[str, Any], **updates: Any) -> dict[str, Any]:
        metadata = self._paddle_metadata(workspace)
        metadata.update({key: value for key, value in updates.items() if value is not None})
        return {PADDLE_PROVIDER: metadata}

    def _checkout_custom_data(self, *, workspace: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        return {
            "workspace_id": workspace["workspace_id"],
            "workspace_name": workspace["name"],
            "plan_tier": "pro",
            "initiated_by_user_id": user["user_id"],
            "initiated_by_email": user["email"],
        }

    def _extract_price_ref(self, payload: dict[str, Any]) -> str:
        for item in list(payload.get("items") or []):
            price_id = _clean_text(item.get("price_id"))
            if price_id:
                return price_id
            price = item.get("price") or {}
            price_id = _clean_text(price.get("id"))
            if price_id:
                return price_id
        return ""

    def _provider_status_mapping(self, status: str, *, default_to_canceled: bool = False) -> tuple[str, str]:
        normalized = _clean_text(status).lower()
        if normalized in ACTIVE_PROVIDER_STATUSES:
            return "pro", "active"
        if normalized in TRIALING_PROVIDER_STATUSES:
            return "pro", "trialing"
        if normalized in PAST_DUE_PROVIDER_STATUSES:
            return "pro", "past_due"
        if normalized in CANCELED_PROVIDER_STATUSES:
            return "pro", "canceled"
        return ("pro", "canceled") if default_to_canceled else ("pro", "past_due")

    def _ensure_purchasable_workspace(self, workspace: dict[str, Any]) -> None:
        if _clean_text(workspace.get("plan_tier")).lower() == "internal":
            raise PaddleIntegrationError("Internal workspaces are managed inside the app and cannot be purchased through billing.")

    def _create_or_reuse_customer(self, *, workspace: dict[str, Any], user: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        existing = _clean_text(workspace.get("external_customer_ref"))
        if existing:
            return existing, workspace

        response = self._request(
            "POST",
            "/customers",
            {
                "email": user["email"],
                "name": _clean_text(user.get("display_name")) or user["email"],
                "custom_data": self._checkout_custom_data(workspace=workspace, user=user),
            },
        )
        customer_id = _clean_text((response.get("data") or {}).get("id"))
        if not customer_id:
            raise PaddleIntegrationError("Paddle did not return a customer reference.")
        updated_workspace = self.workspace_repository.update_workspace_plan(
            workspace["workspace_id"],
            external_billing_provider=PADDLE_PROVIDER,
            external_customer_ref=customer_id,
            billing_synced_at=_utc_now(),
            billing_metadata=self._merged_billing_metadata(
                workspace,
                environment=self.config().environment,
                external_customer_ref=customer_id,
            ),
        )
        return customer_id, updated_workspace

    def create_pro_checkout(self, *, workspace: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        config = self.config()
        if not config.checkout_enabled:
            raise PaddleConfigurationError("Paddle checkout is not configured for this deployment.")
        self._ensure_purchasable_workspace(workspace)
        if _clean_text(workspace.get("plan_tier")).lower() == "pro" and _clean_text(workspace.get("plan_status")).lower() in {
            "active",
            "trialing",
        }:
            raise PaddleIntegrationError("This workspace already has an active Pro subscription.")

        customer_id, current_workspace = self._create_or_reuse_customer(workspace=workspace, user=user)
        payload: dict[str, Any] = {
            "items": [{"price_id": config.pro_price_id, "quantity": 1}],
            "customer_id": customer_id,
            "collection_mode": "automatic",
            "custom_data": self._checkout_custom_data(workspace=current_workspace, user=user),
        }
        if config.checkout_url:
            payload["checkout"] = {"url": config.checkout_url}
        response = self._request("POST", "/transactions", payload)
        data = response.get("data") or {}
        checkout = data.get("checkout") or {}
        checkout_url = _clean_text(checkout.get("url"))
        if not checkout_url:
            raise PaddleIntegrationError("Paddle did not return a hosted checkout URL.")
        transaction_id = _clean_text(data.get("id"))
        updated_workspace = self.workspace_repository.update_workspace_plan(
            current_workspace["workspace_id"],
            external_billing_provider=PADDLE_PROVIDER,
            external_customer_ref=customer_id,
            external_price_ref=config.pro_price_id,
            billing_synced_at=_utc_now(),
            billing_metadata=self._merged_billing_metadata(
                current_workspace,
                environment=config.environment,
                last_checkout_transaction_id=transaction_id,
                last_checkout_created_at=_utc_now().isoformat(),
                last_checkout_initiated_by=user["user_id"],
            ),
        )
        return {
            "checkout_url": checkout_url,
            "transaction_id": transaction_id,
            "customer_id": customer_id,
            "workspace": updated_workspace,
        }

    def create_management_session(self, *, workspace: dict[str, Any]) -> dict[str, Any]:
        config = self.config()
        if not config.portal_enabled:
            raise PaddleConfigurationError("Paddle billing management is not configured for this deployment.")
        self._ensure_purchasable_workspace(workspace)
        customer_id = _clean_text(workspace.get("external_customer_ref"))
        if not customer_id:
            raise PaddleIntegrationError("This workspace is not linked to a Paddle customer yet.")

        payload: dict[str, Any] = {}
        if config.billing_return_url:
            payload["return_url"] = config.billing_return_url
        subscription_id = _clean_text(workspace.get("external_subscription_ref"))
        if subscription_id:
            payload["subscription_ids"] = [subscription_id]
        response = self._request(
            "POST",
            f"/customers/{quote(customer_id, safe='')}/portal-sessions",
            payload or {},
        )
        data = response.get("data") or {}
        urls = data.get("urls") or {}
        general = urls.get("general") or {}
        portal_url = _clean_text(general.get("overview")) or _clean_text(data.get("url"))
        if not portal_url:
            raise PaddleIntegrationError("Paddle did not return a billing-management URL.")
        return {"management_url": portal_url}

    def verify_webhook_signature(self, raw_body: bytes, signature_header: str) -> None:
        config = self.config()
        if not config.webhook_enabled:
            raise PaddleConfigurationError("Paddle webhook verification is not configured.")
        parts = {}
        for item in _clean_text(signature_header).split(";"):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            parts[_clean_text(key).lower()] = _clean_text(value)
        timestamp_text = parts.get("ts")
        provided_signature = parts.get("h1")
        if not timestamp_text or not provided_signature:
            raise PaddleWebhookVerificationError("Missing Paddle signature components.")
        try:
            timestamp = int(timestamp_text)
        except ValueError as exc:
            raise PaddleWebhookVerificationError("Invalid Paddle webhook timestamp.") from exc
        if config.webhook_tolerance_seconds > 0:
            age = abs(int(_utc_now().timestamp()) - timestamp)
            if age > config.webhook_tolerance_seconds:
                raise PaddleWebhookVerificationError("Paddle webhook timestamp is outside the allowed tolerance.")
        signed_payload = timestamp_text.encode("utf-8") + b":" + raw_body
        expected_signature = hmac.new(
            config.webhook_secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, provided_signature):
            raise PaddleWebhookVerificationError("Paddle webhook signature verification failed.")

    def _resolve_workspace_from_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        custom_data = payload.get("custom_data") or {}
        workspace_id = _clean_text(custom_data.get("workspace_id"))
        if workspace_id:
            return self.workspace_repository.get_workspace(workspace_id)

        subscription_ref = _clean_text(payload.get("id")) if _clean_text(payload.get("object")).lower() == "subscription" else ""
        if not subscription_ref:
            subscription_ref = _clean_text(payload.get("subscription_id"))
        if subscription_ref:
            try:
                return self.workspace_repository.get_workspace_by_external_subscription_ref(
                    subscription_ref,
                    provider=PADDLE_PROVIDER,
                )
            except FileNotFoundError:
                pass

        customer_ref = _clean_text(payload.get("customer_id"))
        if customer_ref:
            try:
                return self.workspace_repository.get_workspace_by_external_customer_ref(
                    customer_ref,
                    provider=PADDLE_PROVIDER,
                )
            except FileNotFoundError:
                pass
        raise PaddleIntegrationError("Could not map the Paddle event to a workspace.")

    def _apply_subscription_state(
        self,
        *,
        workspace: dict[str, Any],
        provider_status: str,
        subscription_ref: str,
        customer_ref: str,
        price_ref: str,
        occurred_at: datetime | None,
        period_ends_at: datetime | None,
        trial_ends_at: datetime | None,
        event_type: str,
        event_id: str,
    ) -> dict[str, Any]:
        plan_tier, plan_status = self._provider_status_mapping(provider_status, default_to_canceled=True)
        metadata = self._merged_billing_metadata(
            workspace,
            environment=self.config().environment,
            last_event_id=event_id,
            last_event_type=event_type,
            last_event_occurred_at=(occurred_at or _utc_now()).isoformat(),
            external_customer_ref=customer_ref or _clean_text(workspace.get("external_customer_ref")),
            external_subscription_ref=subscription_ref or _clean_text(workspace.get("external_subscription_ref")),
            provider_subscription_status=_clean_text(provider_status).lower(),
        )
        return self.workspace_repository.update_workspace_plan(
            workspace["workspace_id"],
            plan_tier=plan_tier,
            plan_status=plan_status,
            trial_ends_at=trial_ends_at,
            current_period_ends_at=period_ends_at,
            external_billing_provider=PADDLE_PROVIDER,
            external_customer_ref=customer_ref or _clean_text(workspace.get("external_customer_ref")) or None,
            external_subscription_ref=subscription_ref or _clean_text(workspace.get("external_subscription_ref")) or None,
            external_price_ref=price_ref or _clean_text(workspace.get("external_price_ref")) or None,
            provider_subscription_status=_clean_text(provider_status).lower() or None,
            billing_synced_at=occurred_at or _utc_now(),
            billing_metadata=metadata,
        )

    def _process_subscription_event(
        self,
        *,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
        occurred_at: datetime | None,
    ) -> dict[str, Any]:
        workspace = self._resolve_workspace_from_payload(payload)
        self._ensure_purchasable_workspace(workspace)
        provider_status = _clean_text(payload.get("status")) or "active"
        current_billing_period = payload.get("current_billing_period") or {}
        period_ends_at = _coerce_datetime(current_billing_period.get("ends_at"))
        trial_ends_at = period_ends_at if provider_status == "trialing" else None
        return self._apply_subscription_state(
            workspace=workspace,
            provider_status=provider_status,
            subscription_ref=_clean_text(payload.get("id")),
            customer_ref=_clean_text(payload.get("customer_id")),
            price_ref=self._extract_price_ref(payload) or self.config().pro_price_id,
            occurred_at=occurred_at,
            period_ends_at=period_ends_at,
            trial_ends_at=trial_ends_at,
            event_type=event_type,
            event_id=event_id,
        )

    def _process_transaction_event(
        self,
        *,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
        occurred_at: datetime | None,
    ) -> dict[str, Any]:
        workspace = self._resolve_workspace_from_payload(payload)
        self._ensure_purchasable_workspace(workspace)
        transaction_status = _clean_text(payload.get("status")).lower() or "completed"
        if transaction_status not in (
            ACTIVE_PROVIDER_STATUSES
            | TRIALING_PROVIDER_STATUSES
            | PAST_DUE_PROVIDER_STATUSES
            | CANCELED_PROVIDER_STATUSES
        ):
            transaction_status = _clean_text(workspace.get("provider_subscription_status") or workspace.get("plan_status")).lower() or "active"
        billing_period = payload.get("billing_period") or {}
        period_ends_at = _coerce_datetime(billing_period.get("ends_at"))
        return self._apply_subscription_state(
            workspace=workspace,
            provider_status=transaction_status,
            subscription_ref=_clean_text(payload.get("subscription_id")) or _clean_text(workspace.get("external_subscription_ref")),
            customer_ref=_clean_text(payload.get("customer_id")) or _clean_text(workspace.get("external_customer_ref")),
            price_ref=self._extract_price_ref(payload) or self.config().pro_price_id,
            occurred_at=occurred_at,
            period_ends_at=period_ends_at,
            trial_ends_at=None,
            event_type=event_type,
            event_id=event_id,
        )

    def handle_webhook(self, raw_body: bytes, signature_header: str) -> dict[str, Any]:
        self.verify_webhook_signature(raw_body, signature_header)
        try:
            event = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise PaddleIntegrationError("Paddle webhook payload is not valid JSON.") from exc
        if not isinstance(event, dict):
            raise PaddleIntegrationError("Paddle webhook payload has an invalid shape.")

        event_id = _clean_text(event.get("event_id"))
        event_type = _clean_text(event.get("event_type")).lower()
        payload = event.get("data") or {}
        if not event_id or not event_type or not isinstance(payload, dict):
            raise PaddleIntegrationError("Paddle webhook payload is missing required fields.")

        if self.webhook_event_repository.has_event(provider=PADDLE_PROVIDER, event_id=event_id):
            return {"provider": PADDLE_PROVIDER, "event_id": event_id, "event_type": event_type, "duplicate": True}

        occurred_at = _coerce_datetime(event.get("occurred_at")) or _utc_now()
        if event_type.startswith("subscription."):
            updated_workspace = self._process_subscription_event(
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                occurred_at=occurred_at,
            )
            processed = True
        elif event_type in {"transaction.completed", "transaction.updated"}:
            updated_workspace = self._process_transaction_event(
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                occurred_at=occurred_at,
            )
            processed = True
        else:
            updated_workspace = None
            processed = False

        recorded = self.webhook_event_repository.record_processed_event(
            provider=PADDLE_PROVIDER,
            event_id=event_id,
            event_type=event_type,
            workspace_id=(updated_workspace or {}).get("workspace_id"),
            payload={"occurred_at": occurred_at.isoformat()},
            processed_at=occurred_at,
        )
        if not recorded:
            return {"provider": PADDLE_PROVIDER, "event_id": event_id, "event_type": event_type, "duplicate": True}

        response = {
            "provider": PADDLE_PROVIDER,
            "event_id": event_id,
            "event_type": event_type,
            "duplicate": False,
            "processed": processed,
        }
        if updated_workspace is not None:
            response["workspace_id"] = updated_workspace["workspace_id"]
            response["plan_tier"] = updated_workspace["plan_tier"]
            response["plan_status"] = updated_workspace["plan_status"]
        return response


paddle_billing_service = PaddleBillingService()


__all__ = [
    "PADDLE_PROVIDER",
    "PaddleBillingService",
    "PaddleConfigurationError",
    "PaddleIntegrationError",
    "PaddleWebhookVerificationError",
    "get_paddle_config",
    "paddle_billing_service",
]
