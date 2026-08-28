"""Tests for contracts.money.Money."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from contracts.money import Money


def test_construction_with_minor_units() -> None:
    money = Money(4999, "INR")
    assert money.minor_units == 4999


def test_zero_minor_units_is_valid() -> None:
    money = Money(minor_units=0, currency="INR")
    assert money.minor_units == 0


def test_negative_minor_units_is_valid() -> None:
    money = Money(minor_units=-100, currency="INR")
    assert money.minor_units == -100


def test_float_minor_units_raises_type_error() -> None:
    with pytest.raises(TypeError):
        Money(minor_units=49.99, currency="INR")  # type: ignore[arg-type]


def test_bool_minor_units_raises_type_error() -> None:
    with pytest.raises(TypeError):
        Money(minor_units=True, currency="INR")  # type: ignore[arg-type]


def test_two_letter_currency_raises_value_error() -> None:
    with pytest.raises(ValueError):
        Money(minor_units=100, currency="IN")


def test_addition_same_currency() -> None:
    assert Money(100, "INR") + Money(200, "INR") == Money(300, "INR")


def test_subtraction_same_currency() -> None:
    assert Money(300, "INR") - Money(100, "INR") == Money(200, "INR")


def test_addition_currency_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="currency mismatch"):
        Money(100, "INR") + Money(100, "USD")


def test_subtraction_currency_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="currency mismatch"):
        Money(100, "INR") - Money(100, "USD")


def test_less_than_same_currency_true() -> None:
    assert Money(100, "INR") < Money(200, "INR")


def test_less_than_same_currency_false() -> None:
    assert not (Money(200, "INR") < Money(100, "INR"))


def test_less_than_currency_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="currency mismatch"):
        _ = Money(100, "INR") < Money(100, "USD")


def test_less_than_or_equal_equal_amount() -> None:
    assert Money(100, "INR") <= Money(100, "INR")


def test_frozen_instance_error_on_mutation() -> None:
    money = Money(100, "INR")
    with pytest.raises(FrozenInstanceError):
        money.minor_units = 999  # type: ignore[misc]
