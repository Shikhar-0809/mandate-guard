"""Tests for mandate_guard.features."""

from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from contracts import CartItem, CartMandate, IntentMandate, Money, Scope
from mandate_guard.features import FEATURE_NAMES, extract_features

BASE_NOW = datetime(2026, 8, 1, 12, 0, 0)  # noqa: DTZ001
VALID_MERCHANT = "amazon.in"
VALID_MCC = "electronics"

VALID_ITEM = CartItem(
    sku="SKU001",
    name="USB Cable",
    quantity=2,
    unit_price=Money(500, "INR"),
)
VALID_CART = CartMandate(
    mandate_id="mandate-001",
    items=(VALID_ITEM,),
    total=Money(1000, "INR"),
    cart_hash="hash-abc",
)
VALID_INTENT = IntentMandate(
    mandate_id="mandate-001",
    principal_id="user-001",
    scope=Scope(
        merchants=frozenset({VALID_MERCHANT}),
        categories=frozenset({VALID_MCC}),
        max_amount=Money(10000, "INR"),
    ),
    issued_at=BASE_NOW - timedelta(days=1),
    expires_at=BASE_NOW + timedelta(days=30),
    cart_hash="hash-abc",
)


def run_extract(**overrides: object) -> list[float]:
    defaults: dict[str, object] = {
        "intent": VALID_INTENT,
        "cart": VALID_CART,
        "token": None,
        "transaction_amount": Money(1000, "INR"),
        "merchant_id": VALID_MERCHANT,
        "mcc": VALID_MCC,
        "now": BASE_NOW,
    }
    defaults.update(overrides)
    return extract_features(**defaults)  # type: ignore[arg-type]


def test_feature_count() -> None:
    features = run_extract()
    assert len(features) == len(FEATURE_NAMES) == 15


def test_all_finite() -> None:
    features = run_extract()
    assert all(math.isfinite(value) for value in features)


def test_amount_to_cap_ratio_at_cap() -> None:
    features = run_extract(transaction_amount=Money(10000, "INR"))
    index = FEATURE_NAMES.index("amount_to_cap_ratio")
    assert features[index] == 1.0


def test_amount_to_cap_ratio_no_cap() -> None:
    intent = IntentMandate(
        mandate_id=VALID_INTENT.mandate_id,
        principal_id=VALID_INTENT.principal_id,
        scope=Scope(
            merchants=VALID_INTENT.scope.merchants,
            categories=VALID_INTENT.scope.categories,
            max_amount=None,
        ),
        issued_at=VALID_INTENT.issued_at,
        expires_at=VALID_INTENT.expires_at,
        cart_hash=VALID_INTENT.cart_hash,
    )
    features = run_extract(intent=intent)
    index = FEATURE_NAMES.index("amount_to_cap_ratio")
    assert features[index] == -1.0


def test_deterministic() -> None:
    result1 = run_extract()
    result2 = run_extract()
    assert result1 == result2
