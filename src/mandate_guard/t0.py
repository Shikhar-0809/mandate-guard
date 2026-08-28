"""T0 deterministic mandate constraint checks.

Three concept classes:

- Authorization violation (checks 1-4): mandate expired, amount cap, beneficiary,
  category — deterministic constraint checks.
- Integrity violation (check 5): cart hash mismatch — cryptographic consistency
  between approved snapshot and submitted cart.
- Behavioral/semantic risk (checks 6-7): scope expansion and mandate ID mismatch
  — structural properties of the delegation chain.

Behavioral/semantic risk at the content level (is this item semantically
inconsistent with the stated purpose?) is T1/T2 territory, not T0.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from contracts.cart_mandate import CartMandate
from contracts.delegation_token import DelegationToken
from contracts.intent_mandate import IntentMandate
from contracts.money import Money

MANDATE_EXPIRED = "MANDATE_EXPIRED"
AMOUNT_EXCEEDS_CAP = "AMOUNT_EXCEEDS_CAP"
BENEFICIARY_NOT_ALLOWED = "BENEFICIARY_NOT_ALLOWED"
CATEGORY_NOT_ALLOWED = "CATEGORY_NOT_ALLOWED"
CART_HASH_MISMATCH = "CART_HASH_MISMATCH"
SCOPE_EXPANSION = "SCOPE_EXPANSION"
MANDATE_ID_MISMATCH = "MANDATE_ID_MISMATCH"


@dataclass(frozen=True)
class T0Result:
    passed: bool
    reason_code: str | None
    triggered_rules: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.passed:
            if self.reason_code is not None or self.triggered_rules:
                raise ValueError(
                    "passed=True requires reason_code=None and empty triggered_rules"
                )
            return

        if not self.reason_code:
            raise ValueError("passed=False requires a non-empty reason_code")
        if not self.triggered_rules:
            raise ValueError("passed=False requires non-empty triggered_rules")


def check(
    intent: IntentMandate,
    cart: CartMandate,
    token: DelegationToken | None,
    transaction_amount: Money,
    merchant_id: str,
    mcc: str,
    now: datetime,
) -> T0Result:
    """Run all T0 checks and return a consolidated result."""
    triggered: list[str] = []

    if now >= intent.expires_at:
        triggered.append(MANDATE_EXPIRED)

    if (
        intent.scope.max_amount is not None
        and transaction_amount > intent.scope.max_amount
    ):
        triggered.append(AMOUNT_EXCEEDS_CAP)

    if intent.scope.merchants is not None and merchant_id not in intent.scope.merchants:
        triggered.append(BENEFICIARY_NOT_ALLOWED)

    if intent.scope.categories is not None and mcc not in intent.scope.categories:
        triggered.append(CATEGORY_NOT_ALLOWED)

    if intent.cart_hash is not None and cart.cart_hash != intent.cart_hash:
        triggered.append(CART_HASH_MISMATCH)

    if token is not None and not token.is_valid_delegation():
        triggered.append(SCOPE_EXPANSION)

    if cart.mandate_id != intent.mandate_id:
        triggered.append(MANDATE_ID_MISMATCH)

    if triggered:
        return T0Result(
            passed=False,
            reason_code=triggered[0],
            triggered_rules=tuple(triggered),
        )

    return T0Result(passed=True, reason_code=None, triggered_rules=())
