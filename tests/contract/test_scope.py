"""Tests for contracts.scope.Scope."""

from __future__ import annotations

from datetime import datetime

import pytest

from contracts.money import Money
from contracts.scope import Scope

AMAZON = frozenset({"amazon.com"})
FLIPKART = frozenset({"flipkart.com"})
BOTH_MERCHANTS = frozenset({"amazon.com", "flipkart.com"})

JAN_1 = datetime(2026, 1, 1)  # noqa: DTZ001
MAR_1 = datetime(2026, 3, 1)  # noqa: DTZ001
SEP_30 = datetime(2026, 9, 30)  # noqa: DTZ001
DEC_31 = datetime(2026, 12, 31)  # noqa: DTZ001

AMOUNT_10000 = Money(10000, "INR")
AMOUNT_5000 = Money(5000, "INR")


def test_unrestricted_contains_restricted() -> None:
    parent = Scope()
    child = Scope(merchants=AMAZON)
    assert parent.contains(child) is True


def test_restricted_does_not_contain_unrestricted() -> None:
    parent = Scope(merchants=AMAZON)
    child = Scope()
    assert parent.contains(child) is False


def test_reflexive_merchant_scope() -> None:
    scope = Scope(merchants=AMAZON)
    assert scope.contains(Scope(merchants=AMAZON)) is True


def test_proper_merchant_subset() -> None:
    parent = Scope(merchants=BOTH_MERCHANTS)
    child = Scope(merchants=AMAZON)
    assert parent.contains(child) is True


def test_child_adds_merchant_not_in_parent() -> None:
    parent = Scope(merchants=AMAZON)
    child = Scope(merchants=BOTH_MERCHANTS)
    assert parent.contains(child) is False


def test_amount_narrowing() -> None:
    parent = Scope(max_amount=AMOUNT_10000)
    child = Scope(max_amount=AMOUNT_5000)
    assert parent.contains(child) is True


def test_amount_widening() -> None:
    parent = Scope(max_amount=AMOUNT_5000)
    child = Scope(max_amount=AMOUNT_10000)
    assert parent.contains(child) is False


def test_time_window_narrowing() -> None:
    parent = Scope(valid_from=JAN_1, valid_until=DEC_31)
    child = Scope(valid_from=MAR_1, valid_until=SEP_30)
    assert parent.contains(child) is True


def test_child_starts_earlier_than_parent() -> None:
    parent = Scope(valid_from=MAR_1)
    child = Scope(valid_from=JAN_1)
    assert parent.contains(child) is False


def test_child_ends_later_than_parent() -> None:
    parent = Scope(valid_until=SEP_30)
    child = Scope(valid_until=DEC_31)
    assert parent.contains(child) is False


def test_cross_dimension_narrow_merchants_widen_amount() -> None:
    parent = Scope(merchants=BOTH_MERCHANTS, max_amount=AMOUNT_5000)
    child = Scope(merchants=AMAZON, max_amount=AMOUNT_10000)
    assert parent.contains(child) is False


def test_currency_mismatch_in_amount_comparison_raises() -> None:
    parent = Scope(max_amount=AMOUNT_10000)
    child = Scope(max_amount=Money(5000, "USD"))
    with pytest.raises(ValueError, match="currency mismatch in scope comparison"):
        parent.contains(child)
