"""T1 feature extraction from PSP-observable transaction inputs.

All features must be observable at PSP inference time from the transaction
inputs alone. No generation metadata (family, note, family_note) is used.
"""

from __future__ import annotations

import math
from datetime import datetime

from contracts import CartMandate, DelegationToken, IntentMandate, Money

FEATURE_NAMES: tuple[str, ...] = (
    "amount_to_cap_ratio",
    "amount_minor_units",
    "log_amount",
    "days_until_expiry",
    "days_since_issued",
    "mandate_age_fraction",
    "cart_item_count",
    "cart_total_minor_units",
    "amount_to_cart_ratio",
    "max_amount_set",
    "merchants_restricted",
    "categories_restricted",
    "has_delegation_token",
    "cart_hash_pinned",
    "intent_cart_name_overlap",
)


def extract_features(
    intent: IntentMandate,
    cart: CartMandate,
    token: DelegationToken | None,
    transaction_amount: Money,
    merchant_id: str,
    mcc: str,
    now: datetime,
) -> list[float]:
    """Return exactly len(FEATURE_NAMES) floats in FEATURE_NAMES order."""
    if intent.scope.max_amount is None:
        amount_to_cap_ratio = -1.0
    else:
        amount_to_cap_ratio = (
            transaction_amount.minor_units / intent.scope.max_amount.minor_units
        )

    amount_minor_units = float(transaction_amount.minor_units)
    log_amount = math.log1p(transaction_amount.minor_units)

    days_until_expiry = float((intent.expires_at - now).days)
    days_since_issued = float((now - intent.issued_at).days)
    total_age = days_since_issued + days_until_expiry
    mandate_age_fraction = 0.0 if total_age <= 0.0 else days_since_issued / total_age

    cart_item_count = float(len(cart.items))
    cart_total_minor_units = float(cart.total.minor_units)

    if cart.total.minor_units == 0:
        amount_to_cart_ratio = 0.0
    else:
        amount_to_cart_ratio = transaction_amount.minor_units / cart.total.minor_units

    max_amount_set = 1.0 if intent.scope.max_amount is not None else 0.0
    merchants_restricted = 1.0 if intent.scope.merchants is not None else 0.0
    categories_restricted = 1.0 if intent.scope.categories is not None else 0.0
    has_delegation_token = 1.0 if token is not None else 0.0
    cart_hash_pinned = 1.0 if intent.cart_hash is not None else 0.0

    features = [
        amount_to_cap_ratio,
        amount_minor_units,
        log_amount,
        days_until_expiry,
        days_since_issued,
        mandate_age_fraction,
        cart_item_count,
        cart_total_minor_units,
        amount_to_cart_ratio,
        max_amount_set,
        merchants_restricted,
        categories_restricted,
        has_delegation_token,
        cart_hash_pinned,
    ]

    if not intent.purchase_intent:
        intent_cart_overlap = -1.0
    else:
        intent_tokens = set(intent.purchase_intent.lower().split())
        cart_text = " ".join(item.name.lower() for item in cart.items)
        cart_tokens = set(cart_text.split())
        if not intent_tokens:
            intent_cart_overlap = -1.0
        else:
            matched = intent_tokens & cart_tokens
            intent_cart_overlap = len(matched) / len(intent_tokens)

    features.append(intent_cart_overlap)

    assert len(features) == len(FEATURE_NAMES), (
        f"feature count mismatch: {len(features)} != {len(FEATURE_NAMES)}"
    )
    return features
