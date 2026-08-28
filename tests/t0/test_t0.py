"""Tests for src.mandate_guard.t0."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from contracts.cart_item import CartItem
from contracts.cart_mandate import CartMandate
from contracts.delegation_token import DelegationToken
from contracts.intent_mandate import IntentMandate
from contracts.money import Money
from contracts.scope import Scope
from mandate_guard.t0 import (
    AMOUNT_EXCEEDS_CAP,
    BENEFICIARY_NOT_ALLOWED,
    CART_HASH_MISMATCH,
    CATEGORY_NOT_ALLOWED,
    MANDATE_EXPIRED,
    MANDATE_ID_MISMATCH,
    SCOPE_EXPANSION,
    T0Result,
    check,
)

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


def run_check(**overrides: object) -> T0Result:
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
    return check(**defaults)  # type: ignore[arg-type]


def test_all_checks_pass() -> None:
    result = run_check()
    assert result.passed is True
    assert result.reason_code is None
    assert result.triggered_rules == ()


def test_mandate_expired_at_boundary() -> None:
    result = run_check(now=VALID_INTENT.expires_at)
    assert MANDATE_EXPIRED in result.triggered_rules


def test_amount_exceeds_cap() -> None:
    result = run_check(transaction_amount=Money(15000, "INR"))
    assert AMOUNT_EXCEEDS_CAP in result.triggered_rules


def test_beneficiary_not_allowed() -> None:
    result = run_check(merchant_id="flipkart.com")
    assert BENEFICIARY_NOT_ALLOWED in result.triggered_rules


def test_category_not_allowed() -> None:
    result = run_check(mcc="groceries")
    assert CATEGORY_NOT_ALLOWED in result.triggered_rules


def test_cart_hash_mismatch() -> None:
    wrong_cart = CartMandate(
        mandate_id="mandate-001",
        items=(VALID_ITEM,),
        total=Money(1000, "INR"),
        cart_hash="hash-WRONG",
    )
    result = run_check(cart=wrong_cart)
    assert CART_HASH_MISMATCH in result.triggered_rules


def test_scope_expansion() -> None:
    token = DelegationToken(
        token_id="token-001",
        parent_mandate_id="mandate-001",
        parent_scope=Scope(max_amount=Money(5000, "INR")),
        delegated_scope=Scope(max_amount=Money(10000, "INR")),
        issued_at=BASE_NOW - timedelta(days=1),
        expires_at=BASE_NOW + timedelta(days=30),
    )
    result = run_check(token=token)
    assert SCOPE_EXPANSION in result.triggered_rules


def test_mandate_id_mismatch() -> None:
    wrong_cart = CartMandate(
        mandate_id="mandate-WRONG",
        items=(VALID_ITEM,),
        total=Money(1000, "INR"),
        cart_hash="hash-abc",
    )
    result = run_check(cart=wrong_cart)
    assert MANDATE_ID_MISMATCH in result.triggered_rules


def test_multiple_failures_accumulate_in_order() -> None:
    result = run_check(
        now=VALID_INTENT.expires_at,
        merchant_id="flipkart.com",
        mcc="groceries",
    )
    assert result.triggered_rules == (
        MANDATE_EXPIRED,
        BENEFICIARY_NOT_ALLOWED,
        CATEGORY_NOT_ALLOWED,
    )
    assert result.reason_code == MANDATE_EXPIRED


def test_unrestricted_merchants_allow_any_merchant() -> None:
    intent = IntentMandate(
        mandate_id="mandate-001",
        principal_id="user-001",
        scope=Scope(
            merchants=None,
            categories=frozenset({VALID_MCC}),
            max_amount=Money(10000, "INR"),
        ),
        issued_at=BASE_NOW - timedelta(days=1),
        expires_at=BASE_NOW + timedelta(days=30),
        cart_hash="hash-abc",
    )
    result = run_check(intent=intent, merchant_id="anyone.com")
    assert result.passed is True


def test_unrestricted_categories_allow_any_mcc() -> None:
    intent = IntentMandate(
        mandate_id="mandate-001",
        principal_id="user-001",
        scope=Scope(
            merchants=frozenset({VALID_MERCHANT}),
            categories=None,
            max_amount=Money(10000, "INR"),
        ),
        issued_at=BASE_NOW - timedelta(days=1),
        expires_at=BASE_NOW + timedelta(days=30),
        cart_hash="hash-abc",
    )
    result = run_check(intent=intent, mcc="anything")
    assert result.passed is True


def test_null_intent_cart_hash_skips_mismatch_check() -> None:
    intent = IntentMandate(
        mandate_id="mandate-001",
        principal_id="user-001",
        scope=Scope(
            merchants=frozenset({VALID_MERCHANT}),
            categories=frozenset({VALID_MCC}),
            max_amount=Money(10000, "INR"),
        ),
        issued_at=BASE_NOW - timedelta(days=1),
        expires_at=BASE_NOW + timedelta(days=30),
        cart_hash=None,
    )
    wrong_cart = CartMandate(
        mandate_id="mandate-001",
        items=(VALID_ITEM,),
        total=Money(1000, "INR"),
        cart_hash="anything",
    )
    result = run_check(intent=intent, cart=wrong_cart)
    assert CART_HASH_MISMATCH not in result.triggered_rules
    assert result.passed is True


def test_t0_result_passed_with_reason_code_raises() -> None:
    with pytest.raises(ValueError):
        T0Result(passed=True, reason_code="SOMETHING", triggered_rules=())


def test_t0_result_failed_without_reason_code_raises() -> None:
    with pytest.raises(ValueError):
        T0Result(passed=False, reason_code=None, triggered_rules=())
