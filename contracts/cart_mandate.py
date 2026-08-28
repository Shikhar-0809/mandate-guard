"""Cart mandate: priced cart bound to a mandate with integrity hash."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.cart_item import CartItem
from contracts.money import Money


@dataclass(frozen=True)
class CartMandate:
    mandate_id: str
    items: tuple[CartItem, ...]
    total: Money
    cart_hash: str

    def __post_init__(self) -> None:
        if not self.mandate_id:
            raise ValueError("mandate_id must not be empty")
        if not self.cart_hash:
            raise ValueError("cart_hash must not be empty")
        if not self.items:
            raise ValueError("items must not be empty")

        for item in self.items:
            if item.unit_price.currency != self.total.currency:
                raise ValueError("all item prices must share the cart currency")

        expected = Money(0, self.total.currency)
        for item in self.items:
            expected = expected + (item.unit_price * item.quantity)

        if expected != self.total:
            raise ValueError("total does not match sum of item prices")
