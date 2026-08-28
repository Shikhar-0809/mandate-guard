"""Tests for contracts.intent_mandate.IntentMandate."""

from __future__ import annotations

from datetime import datetime

import pytest

from contracts.intent_mandate import IntentMandate
from contracts.scope import Scope

ISSUED_AT = datetime(2026, 1, 1, 12, 0, 0)  # noqa: DTZ001
EXPIRES_AT = datetime(2026, 12, 31, 23, 59, 59)  # noqa: DTZ001
SCOPE = Scope()


def test_valid_construction() -> None:
    mandate = IntentMandate(
        mandate_id="mandate-001",
        principal_id="principal-001",
        scope=SCOPE,
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
    )
    assert mandate.mandate_id == "mandate-001"


def test_empty_mandate_id_raises() -> None:
    with pytest.raises(ValueError):
        IntentMandate(
            mandate_id="",
            principal_id="principal-001",
            scope=SCOPE,
            issued_at=ISSUED_AT,
            expires_at=EXPIRES_AT,
        )


def test_empty_principal_id_raises() -> None:
    with pytest.raises(ValueError):
        IntentMandate(
            mandate_id="mandate-001",
            principal_id="",
            scope=SCOPE,
            issued_at=ISSUED_AT,
            expires_at=EXPIRES_AT,
        )


def test_expires_at_equal_to_issued_at_raises() -> None:
    with pytest.raises(ValueError, match="expires_at must be after issued_at"):
        IntentMandate(
            mandate_id="mandate-001",
            principal_id="principal-001",
            scope=SCOPE,
            issued_at=ISSUED_AT,
            expires_at=ISSUED_AT,
        )


def test_expires_at_before_issued_at_raises() -> None:
    with pytest.raises(ValueError, match="expires_at must be after issued_at"):
        IntentMandate(
            mandate_id="mandate-001",
            principal_id="principal-001",
            scope=SCOPE,
            issued_at=EXPIRES_AT,
            expires_at=ISSUED_AT,
        )


def test_cart_hash_none_is_valid() -> None:
    mandate = IntentMandate(
        mandate_id="mandate-001",
        principal_id="principal-001",
        scope=SCOPE,
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
        cart_hash=None,
    )
    assert mandate.cart_hash is None


def test_cart_hash_set_is_valid() -> None:
    mandate = IntentMandate(
        mandate_id="mandate-001",
        principal_id="principal-001",
        scope=SCOPE,
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
        cart_hash="abc123",
    )
    assert mandate.cart_hash == "abc123"
