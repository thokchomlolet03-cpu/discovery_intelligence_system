import base64
import json
import os
from typing import Any

from googleapiclient import discovery


TARGET_PROJECT_ID = os.environ["TARGET_PROJECT_ID"]
TARGET_ZONE = os.environ["TARGET_ZONE"]
TARGET_INSTANCE_NAME = os.environ["TARGET_INSTANCE_NAME"]
STOP_THRESHOLD_AMOUNT = float(os.environ.get("STOP_THRESHOLD_AMOUNT", "360"))
BILLING_CURRENCY = os.environ.get("BILLING_CURRENCY", "INR")


def _decode_budget_payload(event: dict[str, Any]) -> dict[str, Any]:
    raw_data = event.get("data")
    if not raw_data:
        return {}
    decoded = base64.b64decode(raw_data).decode("utf-8")
    return json.loads(decoded)


def _instance_status(compute: Any) -> str | None:
    response = (
        compute.instances()
        .get(
            project=TARGET_PROJECT_ID,
            zone=TARGET_ZONE,
            instance=TARGET_INSTANCE_NAME,
        )
        .execute()
    )
    return response.get("status")


def limit_use(event: dict[str, Any], context: Any) -> None:
    del context

    payload = _decode_budget_payload(event)
    cost_amount = float(payload.get("costAmount", 0.0))
    budget_amount = float(payload.get("budgetAmount", 0.0))
    budget_name = payload.get("budgetDisplayName", "unnamed-budget")
    currency_code = payload.get("currencyCode", BILLING_CURRENCY)

    print(
        json.dumps(
            {
                "message": "Budget notification received",
                "budget": budget_name,
                "budget_amount": budget_amount,
                "cost_amount": cost_amount,
                "currency_code": currency_code,
                "stop_threshold_amount": STOP_THRESHOLD_AMOUNT,
                "target_instance": TARGET_INSTANCE_NAME,
                "target_zone": TARGET_ZONE,
            }
        )
    )

    if cost_amount < STOP_THRESHOLD_AMOUNT:
        print(
            json.dumps(
                {
                    "message": "Threshold not reached; leaving VM running",
                    "cost_amount": cost_amount,
                    "currency_code": currency_code,
                    "stop_threshold_amount": STOP_THRESHOLD_AMOUNT,
                }
            )
        )
        return

    compute = discovery.build("compute", "v1", cache_discovery=False)
    status = _instance_status(compute)

    if status != "RUNNING":
        print(
            json.dumps(
                {
                    "message": "VM already not running; no stop needed",
                    "instance_status": status,
                }
            )
        )
        return

    operation = (
        compute.instances()
        .stop(
            project=TARGET_PROJECT_ID,
            zone=TARGET_ZONE,
            instance=TARGET_INSTANCE_NAME,
        )
        .execute()
    )

    print(
        json.dumps(
            {
                "message": "Stop operation requested",
                "instance": TARGET_INSTANCE_NAME,
                "zone": TARGET_ZONE,
                "operation": operation.get("name"),
            }
        )
    )
