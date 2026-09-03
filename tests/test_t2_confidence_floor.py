"""Tests for T2 confidence floor demotion of low-confidence BLOCK verdicts."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from contracts import (
    CartItem,
    CartMandate,
    IntentMandate,
    Money,
    Scope,
    T2Config,
    VerdictState,
)
from mandate_guard.t2 import T2_CONFIDENCE_FLOOR, verify

BASE_NOW = datetime(2026, 8, 1, 12, 0, 0)  # noqa: DTZ001

VALID_INTENT = IntentMandate(
    mandate_id="mandate-001",
    principal_id="user-001",
    scope=Scope(
        merchants=frozenset({"amazon.in"}),
        categories=frozenset({"electronics"}),
        max_amount=Money(10000, "INR"),
    ),
    issued_at=BASE_NOW - timedelta(days=1),
    expires_at=BASE_NOW + timedelta(days=30),
    cart_hash="hash-abc",
    purchase_intent="USB cable",
)
VALID_CART = CartMandate(
    mandate_id="mandate-001",
    items=(
        CartItem(
            sku="SKU001",
            name="USB Cable",
            quantity=2,
            unit_price=Money(500, "INR"),
        ),
    ),
    total=Money(1000, "INR"),
    cart_hash="hash-abc",
)


def _mock_ollama_response(verdict: str, confidence: float | None) -> MagicMock:
    payload: dict[str, object] = {
        "verdict": verdict,
        "evidence": "cart does not match intent",
    }
    if confidence is not None:
        payload["confidence"] = confidence
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "message": {"content": json.dumps(payload)},
    }
    return response


@pytest.mark.parametrize(
    ("confidence", "expected_verdict", "expected_degraded_reason"),
    [
        (0.90, VerdictState.BLOCK, None),
        (T2_CONFIDENCE_FLOOR, VerdictState.BLOCK, None),
        (0.69, VerdictState.HOLD, "DEGRADED_T2_LOW_CONFIDENCE"),
        (None, VerdictState.HOLD, "DEGRADED_T2_LOW_CONFIDENCE"),
    ],
)
def test_block_confidence_floor(
    confidence: float | None,
    expected_verdict: VerdictState,
    expected_degraded_reason: str | None,
) -> None:
    with patch("mandate_guard.t2._requests.post") as mock_post:
        mock_post.return_value = _mock_ollama_response("BLOCK", confidence)
        result = verify(
            VALID_INTENT,
            VALID_CART,
            None,
            None,
            T2Config(t2_enabled=True),
        )

    assert result.verdict == expected_verdict
    assert result.degraded_reason == expected_degraded_reason
    if expected_degraded_reason is None:
        assert result.invoked is True
    else:
        assert result.invoked is False


@pytest.mark.parametrize(
    ("verdict", "confidence"),
    [
        ("HOLD", 0.50),
        ("ALLOW", 0.50),
    ],
)
def test_non_block_verdicts_ignore_confidence_floor(
    verdict: str,
    confidence: float,
) -> None:
    with patch("mandate_guard.t2._requests.post") as mock_post:
        mock_post.return_value = _mock_ollama_response(verdict, confidence)
        result = verify(
            VALID_INTENT,
            VALID_CART,
            None,
            None,
            T2Config(t2_enabled=True),
        )

    assert result.verdict == VerdictState(verdict)
    assert result.degraded_reason is None
    assert result.invoked is True
