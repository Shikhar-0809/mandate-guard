"""Tests for Money.__mul__."""

from __future__ import annotations

import pytest

from contracts.money import Money


def test_multiply_by_positive_integer() -> None:
    assert Money(100, "INR") * 3 == Money(300, "INR")


def test_multiply_by_zero() -> None:
    assert Money(100, "INR") * 0 == Money(0, "INR")


def test_multiply_by_bool_raises_type_error() -> None:
    with pytest.raises(TypeError):
        Money(100, "INR") * True  # type: ignore[operator]


def test_multiply_by_float_raises_type_error() -> None:
    with pytest.raises(TypeError):
        Money(100, "INR") * 2.5  # type: ignore[operator]


def test_multiply_by_negative_integer() -> None:
    assert Money(100, "INR") * -1 == Money(-100, "INR")
