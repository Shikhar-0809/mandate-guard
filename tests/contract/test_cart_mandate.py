"""Tests for contracts.cart_mandate.CartMandate and contracts.cart_item.CartItem."""

from __future__ import annotations

import pytest

from contracts.cart_item import CartItem
from contracts.cart_mandate import CartMandate
from contracts.money import Money


def _item(sku: str, quantity: int, unit_minor: int) -> CartItem:
    return CartItem(
        sku=sku,
        name=f"Product {sku}",
        quantity=quantity,
        unit_price=Money(unit_minor, "INR"),
    )


def test_valid_single_item_cart() -> None:
    item = _item("SKU-1", 2, 100)
    cart = CartMandate(
        mandate_id="mandate-001",
        items=(item,),
        total=Money(200, "INR"),
        cart_hash="hash-001",
    )
    assert cart.total == Money(200, "INR")


def test_valid_multi_item_cart() -> None:
    item_a = _item("SKU-A", 2, 100)
    item_b = _item("SKU-B", 1, 100)
    cart = CartMandate(
        mandate_id="mandate-001",
        items=(item_a, item_b),
        total=Money(300, "INR"),
        cart_hash="hash-002",
    )
    assert cart.total == Money(300, "INR")


def test_empty_mandate_id_raises() -> None:
    item = _item("SKU-1", 1, 100)
    with pytest.raises(ValueError):
        CartMandate(
            mandate_id="",
            items=(item,),
            total=Money(100, "INR"),
            cart_hash="hash-001",
        )


def test_empty_cart_hash_raises() -> None:
    item = _item("SKU-1", 1, 100)
    with pytest.raises(ValueError):
        CartMandate(
            mandate_id="mandate-001",
            items=(item,),
            total=Money(100, "INR"),
            cart_hash="",
        )


def test_empty_items_raises() -> None:
    with pytest.raises(ValueError, match="items must not be empty"):
        CartMandate(
            mandate_id="mandate-001",
            items=(),
            total=Money(0, "INR"),
            cart_hash="hash-001",
        )


def test_total_mismatch_raises() -> None:
    item_a = _item("SKU-A", 1, 100)
    item_b = _item("SKU-B", 2, 100)
    with pytest.raises(ValueError, match="total does not match sum of item prices"):
        CartMandate(
            mandate_id="mandate-001",
            items=(item_a, item_b),
            total=Money(400, "INR"),
            cart_hash="hash-003",
        )


def test_currency_mismatch_raises() -> None:
    item = CartItem(
        sku="SKU-USD",
        name="USD Product",
        quantity=1,
        unit_price=Money(100, "USD"),
    )
    with pytest.raises(
        ValueError, match="all item prices must share the cart currency"
    ):
        CartMandate(
            mandate_id="mandate-001",
            items=(item,),
            total=Money(100, "INR"),
            cart_hash="hash-004",
        )


def test_cart_item_zero_quantity_raises() -> None:
    with pytest.raises(ValueError, match="quantity must be positive"):
        CartItem(
            sku="SKU-1",
            name="Product",
            quantity=0,
            unit_price=Money(100, "INR"),
        )


def test_cart_item_empty_sku_raises() -> None:
    with pytest.raises(ValueError, match="sku must not be empty"):
        CartItem(
            sku="",
            name="Product",
            quantity=1,
            unit_price=Money(100, "INR"),
        )
