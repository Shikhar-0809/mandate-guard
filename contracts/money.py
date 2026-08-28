"""Money value object: integer minor units with ISO 4217 currency."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    minor_units: int
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.minor_units, int) or isinstance(self.minor_units, bool):
            raise TypeError("minor_units must be int, not bool")
        if not isinstance(self.currency, str) or len(self.currency) != 3:
            raise ValueError("currency must be a three-letter ISO 4217 code")

    def __add__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError("currency mismatch")
        return Money(self.minor_units + other.minor_units, self.currency)

    def __sub__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError("currency mismatch")
        return Money(self.minor_units - other.minor_units, self.currency)

    def __lt__(self, other: Money) -> bool:
        if self.currency != other.currency:
            raise ValueError("currency mismatch")
        return self.minor_units < other.minor_units

    def __le__(self, other: Money) -> bool:
        if self.currency != other.currency:
            raise ValueError("currency mismatch")
        return self.minor_units <= other.minor_units

    def __gt__(self, other: Money) -> bool:
        if self.currency != other.currency:
            raise ValueError("currency mismatch")
        return self.minor_units > other.minor_units

    def __ge__(self, other: Money) -> bool:
        if self.currency != other.currency:
            raise ValueError("currency mismatch")
        return self.minor_units >= other.minor_units

    def __mul__(self, quantity: int) -> Money:
        if not isinstance(quantity, int) or isinstance(quantity, bool):
            raise TypeError(
                f"Money can only be multiplied by int, got {type(quantity).__name__}"
            )
        return Money(self.minor_units * quantity, self.currency)
