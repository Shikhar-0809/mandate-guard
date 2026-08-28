"""Tests for contracts.delegation_token.DelegationToken."""

from __future__ import annotations

from datetime import datetime

import pytest

from contracts.delegation_token import DelegationToken
from contracts.money import Money
from contracts.scope import Scope

ISSUED_AT = datetime(2026, 1, 1, 12, 0, 0)  # noqa: DTZ001
EXPIRES_AT = datetime(2026, 12, 31, 23, 59, 59)  # noqa: DTZ001

AMAZON = frozenset({"amazon.com"})
BOTH_MERCHANTS = frozenset({"amazon.com", "flipkart.com"})
AMOUNT_10000 = Money(10000, "INR")
AMOUNT_5000 = Money(5000, "INR")


def test_valid_delegation_with_narrowed_merchants() -> None:
    token = DelegationToken(
        token_id="token-001",
        parent_mandate_id="mandate-001",
        parent_scope=Scope(merchants=BOTH_MERCHANTS),
        delegated_scope=Scope(merchants=AMAZON),
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
    )
    assert token.is_valid_delegation() is True


def test_delegation_widening_merchants_is_invalid() -> None:
    token = DelegationToken(
        token_id="token-002",
        parent_mandate_id="mandate-001",
        parent_scope=Scope(merchants=AMAZON),
        delegated_scope=Scope(merchants=BOTH_MERCHANTS),
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
    )
    assert token.is_valid_delegation() is False


def test_delegation_widening_amount_is_invalid() -> None:
    token = DelegationToken(
        token_id="token-003",
        parent_mandate_id="mandate-001",
        parent_scope=Scope(max_amount=AMOUNT_5000),
        delegated_scope=Scope(max_amount=AMOUNT_10000),
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
    )
    assert token.is_valid_delegation() is False


def test_cross_dimension_narrow_merchants_widen_amount_is_invalid() -> None:
    token = DelegationToken(
        token_id="token-004",
        parent_mandate_id="mandate-001",
        parent_scope=Scope(merchants=BOTH_MERCHANTS, max_amount=AMOUNT_5000),
        delegated_scope=Scope(merchants=AMAZON, max_amount=AMOUNT_10000),
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
    )
    assert token.is_valid_delegation() is False


def test_empty_token_id_raises() -> None:
    with pytest.raises(ValueError):
        DelegationToken(
            token_id="",
            parent_mandate_id="mandate-001",
            parent_scope=Scope(),
            delegated_scope=Scope(),
            issued_at=ISSUED_AT,
            expires_at=EXPIRES_AT,
        )


def test_expires_at_before_issued_at_raises() -> None:
    with pytest.raises(ValueError, match="expires_at must be after issued_at"):
        DelegationToken(
            token_id="token-005",
            parent_mandate_id="mandate-001",
            parent_scope=Scope(),
            delegated_scope=Scope(),
            issued_at=EXPIRES_AT,
            expires_at=ISSUED_AT,
        )
