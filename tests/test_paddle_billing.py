import hmac
import json
import os
import re
import tempfile
import time
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as discovery_app
from system.auth import hash_password
from system.billing import billing_service
from system.db import ensure_database_ready, reset_database_state
from system.db.repositories import BillingWebhookEventRepository, UserRepository, WorkspaceRepository


class PaddleBillingTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["DISCOVERY_ALLOWED_ARTIFACT_ROOTS"] = self.tmpdir.name
        os.environ["DISCOVERY_DATABASE_URL"] = f"sqlite:///{Path(self.tmpdir.name) / 'control_plane.db'}"
        os.environ["DISCOVERY_APP_BASE_URL"] = "https://discovery.example.com"
        os.environ["PADDLE_ENVIRONMENT"] = "sandbox"
        os.environ["PADDLE_API_KEY"] = "pdl_test_key"
        os.environ["PADDLE_WEBHOOK_SECRET"] = "whsec_test_secret"
        os.environ["PADDLE_PRO_PRICE_ID"] = "pri_test_pro"
        os.environ["PADDLE_BILLING_RETURN_URL"] = "https://discovery.example.com/billing"
        os.environ["PADDLE_WEBHOOK_TOLERANCE_SECONDS"] = "300"
        reset_database_state(os.environ["DISCOVERY_DATABASE_URL"])
        ensure_database_ready()

        self.user_repository = UserRepository()
        self.workspace_repository = WorkspaceRepository()
        self.webhook_repository = BillingWebhookEventRepository()

        self.owner = self.user_repository.create_user(
            email="owner@example.com",
            password_hash=hash_password("secret123"),
            display_name="Owner",
        )
        self.workspace = self.workspace_repository.create_workspace(
            name="Workspace A",
            owner_user_id=self.owner["user_id"],
        )
        self.workspace_repository.add_membership(
            workspace_id=self.workspace["workspace_id"],
            user_id=self.owner["user_id"],
            role="owner",
        )
        self.client = TestClient(discovery_app.app)

    def tearDown(self):
        reset_database_state()
        for name in (
            "DISCOVERY_ALLOWED_ARTIFACT_ROOTS",
            "DISCOVERY_DATABASE_URL",
            "DISCOVERY_APP_BASE_URL",
            "PADDLE_ENVIRONMENT",
            "PADDLE_API_KEY",
            "PADDLE_WEBHOOK_SECRET",
            "PADDLE_PRO_PRICE_ID",
            "PADDLE_BILLING_RETURN_URL",
            "PADDLE_WEBHOOK_TOLERANCE_SECONDS",
        ):
            os.environ.pop(name, None)
        self.tmpdir.cleanup()

    def _extract_csrf_token(self, text: str) -> str:
        match = re.search(r'name="csrf_token" value="([^"]+)"', text)
        if match:
            return match.group(1)
        meta = re.search(r'<meta name="csrf-token" content="([^"]*)"', text)
        self.assertIsNotNone(meta)
        return meta.group(1)

    def _login(self, email: str, password: str = "secret123") -> None:
        response = self.client.get("/login")
        csrf_token = self._extract_csrf_token(response.text)
        login_response = self.client.post(
            "/login",
            data={"email": email, "password": password, "csrf_token": csrf_token, "next": "/billing"},
            follow_redirects=False,
        )
        self.assertEqual(login_response.status_code, 303)

    def _authenticated_csrf(self, path: str = "/billing") -> str:
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return self._extract_csrf_token(response.text)

    def _signed_webhook(self, payload: dict[str, object]) -> tuple[bytes, str]:
        raw = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        digest = hmac.new(
            os.environ["PADDLE_WEBHOOK_SECRET"].encode("utf-8"),
            timestamp.encode("utf-8") + b":" + raw,
            sha256,
        ).hexdigest()
        return raw, f"ts={timestamp};h1={digest}"

    def test_owner_can_start_paddle_checkout(self):
        self._login(self.owner["email"])
        with patch.object(
            discovery_app.paddle_billing_service,
            "_request",
            side_effect=[
                {"data": {"id": "ctm_123"}},
                {"data": {"id": "txn_123", "checkout": {"url": "https://pay.paddle.test/checkout/txn_123"}}},
            ],
        ):
            response = self.client.post(
                "/billing/checkout",
                data={"csrf_token": self._authenticated_csrf()},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "https://pay.paddle.test/checkout/txn_123")
        workspace = self.workspace_repository.get_workspace(self.workspace["workspace_id"])
        self.assertEqual(workspace["external_billing_provider"], "paddle")
        self.assertEqual(workspace["external_customer_ref"], "ctm_123")
        self.assertEqual(workspace["external_price_ref"], "pri_test_pro")
        self.assertEqual(workspace["billing_metadata"]["paddle"]["last_checkout_transaction_id"], "txn_123")

    def test_non_owner_cannot_start_or_manage_billing(self):
        member = self.user_repository.create_user(
            email="member@example.com",
            password_hash=hash_password("secret123"),
            display_name="Member",
        )
        self.workspace_repository.add_membership(
            workspace_id=self.workspace["workspace_id"],
            user_id=member["user_id"],
            role="member",
        )
        self._login(member["email"])
        checkout = self.client.post(
            "/billing/checkout",
            data={"csrf_token": self._authenticated_csrf()},
            follow_redirects=False,
        )
        manage = self.client.post(
            "/billing/manage",
            data={"csrf_token": self._authenticated_csrf()},
            follow_redirects=False,
        )

        self.assertEqual(checkout.status_code, 403)
        self.assertEqual(manage.status_code, 403)

    def test_internal_workspace_is_not_routed_into_paddle_checkout(self):
        self.workspace_repository.update_workspace_plan(self.workspace["workspace_id"], plan_tier="internal")
        self._login(self.owner["email"])
        response = self.client.post(
            "/billing/checkout",
            data={"csrf_token": self._authenticated_csrf()},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertIn("/billing?error=", response.headers["location"])

    def test_manage_billing_uses_paddle_portal_for_owner(self):
        self.workspace_repository.update_workspace_plan(
            self.workspace["workspace_id"],
            plan_tier="pro",
            external_billing_provider="paddle",
            external_customer_ref="ctm_123",
            external_subscription_ref="sub_123",
        )
        self._login(self.owner["email"])
        with patch.object(
            discovery_app.paddle_billing_service,
            "_request",
            return_value={"data": {"urls": {"general": {"overview": "https://billing.paddle.test/portal"}}}},
        ):
            response = self.client.post(
                "/billing/manage",
                data={"csrf_token": self._authenticated_csrf()},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "https://billing.paddle.test/portal")

    def test_webhook_sync_promotes_workspace_to_pro_and_is_idempotent(self):
        payload = {
            "event_id": "evt_activated_1",
            "event_type": "subscription.activated",
            "occurred_at": "2026-03-28T12:00:00Z",
            "data": {
                "id": "sub_123",
                "customer_id": "ctm_123",
                "status": "active",
                "current_billing_period": {"ends_at": "2026-04-28T12:00:00Z"},
                "items": [{"price": {"id": "pri_test_pro"}}],
                "custom_data": {"workspace_id": self.workspace["workspace_id"]},
            },
        }
        raw, signature = self._signed_webhook(payload)

        first = self.client.post(
            "/api/webhooks/paddle",
            content=raw,
            headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
        )
        second = self.client.post(
            "/api/webhooks/paddle",
            content=raw,
            headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(first.json()["duplicate"])
        self.assertTrue(second.json()["duplicate"])

        workspace = self.workspace_repository.get_workspace(self.workspace["workspace_id"])
        self.assertEqual(workspace["plan_tier"], "pro")
        self.assertEqual(workspace["plan_status"], "active")
        self.assertEqual(workspace["external_subscription_ref"], "sub_123")
        self.assertEqual(workspace["external_customer_ref"], "ctm_123")
        self.assertEqual(len(self.webhook_repository.list_events(provider="paddle")), 1)

    def test_canceled_subscription_degrades_effective_plan(self):
        activated = {
            "event_id": "evt_activated_2",
            "event_type": "subscription.activated",
            "occurred_at": "2026-03-28T12:00:00Z",
            "data": {
                "id": "sub_999",
                "customer_id": "ctm_999",
                "status": "active",
                "current_billing_period": {"ends_at": "2026-04-28T12:00:00Z"},
                "items": [{"price": {"id": "pri_test_pro"}}],
                "custom_data": {"workspace_id": self.workspace["workspace_id"]},
            },
        }
        canceled = {
            "event_id": "evt_canceled_2",
            "event_type": "subscription.canceled",
            "occurred_at": "2026-04-01T12:00:00Z",
            "data": {
                "id": "sub_999",
                "customer_id": "ctm_999",
                "status": "canceled",
                "current_billing_period": {"ends_at": "2026-04-28T12:00:00Z"},
                "items": [{"price": {"id": "pri_test_pro"}}],
                "custom_data": {"workspace_id": self.workspace["workspace_id"]},
            },
        }
        for event in (activated, canceled):
            raw, signature = self._signed_webhook(event)
            response = self.client.post(
                "/api/webhooks/paddle",
                content=raw,
                headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
            )
            self.assertEqual(response.status_code, 200)

        workspace = self.workspace_repository.get_workspace(self.workspace["workspace_id"])
        summary = billing_service.plan_summary(self.workspace["workspace_id"])
        self.assertEqual(workspace["plan_tier"], "pro")
        self.assertEqual(workspace["plan_status"], "canceled")
        self.assertEqual(summary["effective_plan_tier"], "free")

    def test_invalid_webhook_signature_is_rejected(self):
        payload = {
            "event_id": "evt_invalid",
            "event_type": "subscription.activated",
            "occurred_at": "2026-03-28T12:00:00Z",
            "data": {"custom_data": {"workspace_id": self.workspace["workspace_id"]}},
        }
        raw = json.dumps(payload).encode("utf-8")
        response = self.client.post(
            "/api/webhooks/paddle",
            content=raw,
            headers={"Paddle-Signature": "ts=1;h1=bad", "Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
