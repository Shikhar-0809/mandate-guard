"""Scope lattice: merchant, category, amount, and time-window restrictions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from contracts.money import Money


@dataclass(frozen=True)
class Scope:
    merchants: frozenset[str] | None = None
    categories: frozenset[str] | None = None
    max_amount: Money | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    def contains(self, other: Scope) -> bool:
        """Return True when ``other`` is equal to or strictly narrower than ``self``."""
        if self.merchants is not None:
            if other.merchants is None:
                return False
            if not other.merchants.issubset(self.merchants):
                return False

        if self.categories is not None:
            if other.categories is None:
                return False
            if not other.categories.issubset(self.categories):
                return False

        if self.max_amount is not None:
            if other.max_amount is None:
                return False
            if self.max_amount.currency != other.max_amount.currency:
                raise ValueError("currency mismatch in scope comparison")
            if other.max_amount > self.max_amount:
                return False

        if self.valid_from is not None:
            if other.valid_from is None:
                return False
            if other.valid_from < self.valid_from:
                return False

        if self.valid_until is not None:
            if other.valid_until is None:
                return False
            if other.valid_until > self.valid_until:
                return False

        return True
