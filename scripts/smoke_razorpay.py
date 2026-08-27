"""Smoke-test Razorpay test-mode credentials and capture replay fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import razorpay
from dotenv import load_dotenv
from razorpay.errors import (
    BadRequestError,
    GatewayError,
    ServerError,
    SignatureVerificationError,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "fixtures"

ORDER_AMOUNT_PAISE = 250_000
ORDER_CURRENCY = "INR"
ORDER_RECEIPT = "mandate-guard-smoke-001"

PLAN_PERIOD = "monthly"
PLAN_INTERVAL = 1
PLAN_ITEM = {
    "name": "mandate-guard-smoke-monthly",
    "amount": ORDER_AMOUNT_PAISE,
    "currency": ORDER_CURRENCY,
}

SUBSCRIPTION_TOTAL_COUNT = 12


def load_credentials() -> tuple[str, str]:
    load_dotenv(PROJECT_ROOT / ".env")

    key_id = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise SystemExit("Missing RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET in .env")

    if not key_id.startswith("rzp_test_"):
        raise SystemExit(
            f"RAZORPAY_KEY_ID must start with rzp_test_ (got {key_id[:12]}...)"
        )

    return key_id, key_secret


def write_fixture(name: str, payload: dict[str, Any]) -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURES_DIR / name
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def check_order(client: razorpay.Client) -> None:
    order = client.order.create(
        data={
            "amount": ORDER_AMOUNT_PAISE,
            "currency": ORDER_CURRENCY,
            "receipt": ORDER_RECEIPT,
        }
    )
    if order["status"] != "created":
        raise SystemExit(f"Order status expected 'created', got {order['status']!r}")

    write_fixture("order_created.json", order)
    print(f"PASS order: {order['id']}")


def check_mandate(client: razorpay.Client) -> None:
    try:
        plan = client.plan.create(
            data={
                "period": PLAN_PERIOD,
                "interval": PLAN_INTERVAL,
                "item": PLAN_ITEM,
            }
        )
        subscription = client.subscription.create(
            data={
                "plan_id": plan["id"],
                "total_count": SUBSCRIPTION_TOTAL_COUNT,
            }
        )
    except (
        BadRequestError,
        GatewayError,
        ServerError,
        SignatureVerificationError,
    ) as exc:
        print(f"GATED mandate: {type(exc).__name__}: {exc}")
        return

    write_fixture("plan_created.json", plan)
    write_fixture("subscription_created.json", subscription)
    print(f"PASS mandate: {subscription['id']}")


def main() -> None:
    key_id, key_secret = load_credentials()
    client = razorpay.Client(auth=(key_id, key_secret))

    check_order(client)
    check_mandate(client)


if __name__ == "__main__":
    main()
