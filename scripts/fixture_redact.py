"""Allowlist redactor for Razorpay payment API objects."""

from __future__ import annotations

from typing import Any

TOP_LEVEL_ALLOWLIST: frozenset[str] = frozenset(
    {
        "id",
        "entity",
        "amount",
        "currency",
        "status",
        "order_id",
        "invoice_id",
        "international",
        "method",
        "amount_refunded",
        "refund_status",
        "captured",
        "description",
        "card_id",
        "bank",
        "wallet",
        "fee",
        "tax",
        "error_code",
        "error_description",
        "error_source",
        "error_step",
        "error_reason",
        "created_at",
    }
)

CARD_ALLOWLIST: frozenset[str] = frozenset(
    {
        "id",
        "entity",
        "network",
        "type",
        "issuer",
        "international",
        "emi",
        "sub_type",
    }
)


def redact_payment(payment: dict[str, Any]) -> dict[str, Any]:
    amount = payment["amount"]
    if not isinstance(amount, int):
        raise TypeError(f"payment['amount'] must be int, got {type(amount).__name__}")

    redacted: dict[str, Any] = {}
    for key in TOP_LEVEL_ALLOWLIST:
        if key in payment:
            redacted[key] = payment[key]

    card = payment.get("card")
    if isinstance(card, dict):
        redacted["card"] = {key: card[key] for key in CARD_ALLOWLIST if key in card}

    redacted["notes"] = {}
    return redacted
