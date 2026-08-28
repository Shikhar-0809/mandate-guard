"""Cart line item: SKU, name, quantity, and unit price."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.money import Money


@dataclass(frozen=True)
class CartItem:
    sku: str
    name: str
    quantity: int
    unit_price: Money

    def __post_init__(self) -> None:
        if not self.sku:
            raise ValueError("sku must not be empty")
        if not self.name:
            raise ValueError("name must not be empty")
        if not isinstance(self.quantity, int) or isinstance(self.quantity, bool):
            raise TypeError("quantity must be int, not bool")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
