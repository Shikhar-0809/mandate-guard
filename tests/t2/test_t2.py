"""Tests for mandate_guard.t2 and T2 contract types."""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from contracts import (
    CartItem,
    CartMandate,
    EvidenceSpan,
    IntentMandate,
    Money,
    Scope,
    T2Config,
    VerdictState,
    VerifierOutput,
)
from mandate_guard.t2 import UntrustedBlob, verify

BASE_NOW = datetime(2026, 8, 1, 12, 0, 0)  # noqa: DTZ001
VALID_MERCHANT = "amazon.in"
VALID_MCC = "electronics"

VALID_ITEM = CartItem(
    sku="SKU001",
    name="USB Cable",
    quantity=2,
    unit_price=Money(500, "INR"),
)
VALID_CART = CartMandate(
    mandate_id="mandate-001",
    items=(VALID_ITEM,),
    total=Money(1000, "INR"),
    cart_hash="hash-abc",
)
VALID_INTENT = IntentMandate(
    mandate_id="mandate-001",
    principal_id="user-001",
    scope=Scope(
        merchants=frozenset({VALID_MERCHANT}),
        categories=frozenset({VALID_MCC}),
        max_amount=Money(10000, "INR"),
    ),
    issued_at=BASE_NOW - timedelta(days=1),
    expires_at=BASE_NOW + timedelta(days=30),
    cart_hash="hash-abc",
)


def test_degraded_returns_verifier_output() -> None:
    result = verify(VALID_INTENT, VALID_CART, None, None, T2Config())
    assert isinstance(result, VerifierOutput)
    assert result.invoked is False


def test_degraded_verdict_is_hold() -> None:
    result = verify(VALID_INTENT, VALID_CART, None, None, T2Config())
    assert result.verdict == VerdictState.HOLD


def test_degraded_evidence_spans_empty() -> None:
    result = verify(VALID_INTENT, VALID_CART, None, None, T2Config())
    assert result.evidence_spans == ()


def test_degraded_confidence_zero() -> None:
    result = verify(VALID_INTENT, VALID_CART, None, None, T2Config())
    assert result.confidence == 0.0


def test_degraded_reason_non_empty() -> None:
    result = verify(VALID_INTENT, VALID_CART, None, None, T2Config())
    assert result.degraded_reason is not None
    assert len(result.degraded_reason) > 0


def test_enabled_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        verify(VALID_INTENT, VALID_CART, None, None, T2Config(t2_enabled=True))


def test_verifier_output_invoked_false_nonempty_spans_raises() -> None:
    with pytest.raises(ValueError):
        VerifierOutput(
            verdict=VerdictState.HOLD,
            evidence_spans=(
                EvidenceSpan(
                    field="merchant_id",
                    text="zz-attacker.test",
                    relevance="not in allowlist",
                ),
            ),
            confidence=0.0,
            invoked=False,
            degraded_reason="some reason",
        )


def test_verifier_output_invoked_false_no_reason_raises() -> None:
    with pytest.raises(ValueError):
        VerifierOutput(
            verdict=VerdictState.HOLD,
            evidence_spans=(),
            confidence=0.0,
            invoked=False,
            degraded_reason=None,
        )


def test_verifier_output_confidence_out_of_range_raises() -> None:
    with pytest.raises(ValueError):
        VerifierOutput(
            verdict=VerdictState.ALLOW,
            evidence_spans=(),
            confidence=1.5,
            invoked=True,
            degraded_reason=None,
        )


def test_verifier_output_invoked_true_with_reason_raises() -> None:
    with pytest.raises(ValueError):
        VerifierOutput(
            verdict=VerdictState.ALLOW,
            evidence_spans=(),
            confidence=0.9,
            invoked=True,
            degraded_reason="should not be here",
        )


def test_untrusted_blob_is_frozen() -> None:
    blob = UntrustedBlob(content="test content", source="test")
    with pytest.raises(FrozenInstanceError):
        blob.content = "modified"  # type: ignore[misc]


def test_degraded_verdict_holds_for_fraudulent_transaction() -> None:
    fraudulent_intent = IntentMandate(
        mandate_id="mandate-fraud",
        principal_id="user-fraud",
        scope=Scope(
            merchants=frozenset({VALID_MERCHANT}),
            categories=frozenset({VALID_MCC}),
            max_amount=Money(1000, "INR"),
        ),
        issued_at=BASE_NOW - timedelta(days=1),
        expires_at=BASE_NOW + timedelta(days=30),
        cart_hash="hash-fraud",
    )
    fraudulent_cart = CartMandate(
        mandate_id="mandate-fraud",
        items=(
            CartItem(
                sku="SKU-FRAUD",
                name="Expensive Item",
                quantity=1,
                unit_price=Money(999999, "INR"),
            ),
        ),
        total=Money(999999, "INR"),
        cart_hash="hash-fraud",
    )
    result = verify(fraudulent_intent, fraudulent_cart, None, None, T2Config())
    assert result.verdict == VerdictState.HOLD


def test_t2_config_defaults() -> None:
    cfg = T2Config()
    assert cfg.t2_enabled is False
    assert 0.0 < cfg.tau_low < cfg.tau_high < 1.0


def test_t2_config_invalid_tau_order_raises() -> None:
    with pytest.raises(ValueError):
        T2Config(t2_enabled=False, tau_low=0.8, tau_high=0.3)


def test_t2_config_frozen() -> None:
    cfg = T2Config()
    with pytest.raises(FrozenInstanceError):
        cfg.t2_enabled = True  # type: ignore[misc]
