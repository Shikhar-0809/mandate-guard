"""Tests for mandate_guard.cascade.check()."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from contracts import T1Result, T2Config, Verdict, VerdictState, VerifierOutput
from contracts.cart_item import CartItem
from contracts.cart_mandate import CartMandate
from contracts.intent_mandate import IntentMandate
from contracts.money import Money
from contracts.scope import Scope
from contracts.verifier_output import EvidenceSpan
from mandate_guard.cascade import (
    REASON_NO_SEMANTIC_EVIDENCE,
    REASON_OK,
    REASON_T1_ABOVE_THRESHOLD,
    REASON_T1_SEMANTIC_DEVIATION,
    REASON_T2_ALLOW_SUPPRESSED,
    REASON_T2_SEMANTIC_BLOCK,
    check,
)
from mandate_guard.t0 import AMOUNT_EXCEEDS_CAP

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
    purchase_intent="buy USB cable",
)


def _run_check(
    tmp_path: Path,
    *,
    intent: IntentMandate = VALID_INTENT,
    amount: int = 1000,
    tau: float = 0.65,
    t2_enabled: bool = False,
) -> Verdict:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    (model_dir / "t1_model.joblib").write_bytes(b"test-model")
    return check(
        intent=intent,
        cart=VALID_CART,
        token=None,
        transaction_amount=Money(amount, "INR"),
        merchant_id=VALID_MERCHANT,
        mcc=VALID_MCC,
        now=BASE_NOW,
        agent_request_id="req-001",
        model_dir=model_dir,
        tau=tau,
        t2_config=T2Config(t2_enabled=t2_enabled),
    )


def test_t0_failure_returns_block(tmp_path: Path) -> None:
    verdict = _run_check(tmp_path, amount=50000)
    assert verdict.verdict == VerdictState.BLOCK
    assert verdict.t0_triggered is True
    assert verdict.reason_code == AMOUNT_EXCEEDS_CAP
    assert verdict.t1_score is None


def test_empty_intent_returns_allow_no_semantic_evidence(tmp_path: Path) -> None:
    intent = IntentMandate(
        mandate_id="mandate-001",
        principal_id="user-001",
        scope=VALID_INTENT.scope,
        issued_at=VALID_INTENT.issued_at,
        expires_at=VALID_INTENT.expires_at,
        cart_hash="hash-abc",
        purchase_intent="",
    )
    verdict = _run_check(tmp_path, intent=intent)
    assert verdict.verdict == VerdictState.ALLOW
    assert verdict.reason_code == REASON_NO_SEMANTIC_EVIDENCE
    assert verdict.t1_score is None
    assert verdict.t0_triggered is False


@patch("mandate_guard.cascade.t2_verify")
@patch("mandate_guard.cascade.t1_score")
def test_t1_score_one_blocks_without_t2(
    mock_t1_score: object,
    mock_t2_verify: object,
    tmp_path: Path,
) -> None:
    mock_t1_score.return_value = T1Result(score=1.0, intent_present=True)
    verdict = _run_check(tmp_path, t2_enabled=True)
    assert verdict.verdict == VerdictState.BLOCK
    assert verdict.t1_score == 1.0
    assert verdict.reason_code == REASON_T1_SEMANTIC_DEVIATION
    mock_t2_verify.assert_not_called()


@patch("mandate_guard.cascade.t1_score")
def test_t1_threshold_only_when_t2_disabled(
    mock_t1_score: object,
    tmp_path: Path,
) -> None:
    mock_t1_score.return_value = T1Result(score=0.8, intent_present=True)
    verdict = _run_check(tmp_path, tau=0.65, t2_enabled=False)
    assert verdict.verdict == VerdictState.BLOCK
    assert verdict.reason_code == REASON_T1_ABOVE_THRESHOLD
    assert verdict.t1_score == 0.8


@patch("mandate_guard.cascade.t1_score")
def test_t1_below_threshold_allows_when_t2_disabled(
    mock_t1_score: object,
    tmp_path: Path,
) -> None:
    mock_t1_score.return_value = T1Result(score=0.4, intent_present=True)
    verdict = _run_check(tmp_path, tau=0.65, t2_enabled=False)
    assert verdict.verdict == VerdictState.ALLOW
    assert verdict.reason_code == REASON_OK
    assert verdict.t1_score == 0.4


@patch("mandate_guard.cascade.t2_verify")
@patch("mandate_guard.cascade.t1_score")
def test_t2_confidence_floor_demotion_returns_hold(
    mock_t1_score: object,
    mock_t2_verify: object,
    tmp_path: Path,
) -> None:
    mock_t1_score.return_value = T1Result(score=0.5, intent_present=True)
    mock_t2_verify.return_value = VerifierOutput(
        verdict=VerdictState.HOLD,
        evidence_spans=(),
        confidence=0.5,
        invoked=False,
        degraded_reason="DEGRADED_T2_LOW_CONFIDENCE",
    )
    verdict = _run_check(tmp_path, t2_enabled=True)
    assert verdict.verdict == VerdictState.HOLD
    assert verdict.reason_code == "DEGRADED_T2_LOW_CONFIDENCE"
    assert verdict.t1_score == 0.5


@patch("mandate_guard.cascade.t2_verify")
@patch("mandate_guard.cascade.t1_score")
def test_t2_valid_block_returns_block(
    mock_t1_score: object,
    mock_t2_verify: object,
    tmp_path: Path,
) -> None:
    mock_t1_score.return_value = T1Result(score=0.5, intent_present=True)
    mock_t2_verify.return_value = VerifierOutput(
        verdict=VerdictState.BLOCK,
        evidence_spans=(
            EvidenceSpan(
                field="cart_vs_intent",
                text="cart mismatch",
                relevance="LLM semantic analysis",
            ),
        ),
        confidence=0.95,
        invoked=True,
    )
    verdict = _run_check(tmp_path, t2_enabled=True)
    assert verdict.verdict == VerdictState.BLOCK
    assert verdict.reason_code == REASON_T2_SEMANTIC_BLOCK
    assert verdict.t2_evidence == "cart mismatch"


@pytest.mark.parametrize(
    "test_name",
    [
        "t0_failure",
        "empty_intent",
        "t1_one",
        "t1_threshold",
        "t2_hold",
        "t2_block",
    ],
)
@patch("mandate_guard.cascade.t2_verify")
@patch("mandate_guard.cascade.t1_score")
def test_pinning_fields_non_none(
    mock_t1_score: object,
    mock_t2_verify: object,
    tmp_path: Path,
    test_name: str,
) -> None:
    mock_t1_score.return_value = T1Result(score=0.5, intent_present=True)
    mock_t2_verify.return_value = VerifierOutput(
        verdict=VerdictState.BLOCK,
        evidence_spans=(
            EvidenceSpan(field="f", text="t", relevance="r"),
        ),
        confidence=0.9,
        invoked=True,
    )

    if test_name == "t0_failure":
        verdict = _run_check(tmp_path, amount=50000)
    elif test_name == "empty_intent":
        intent = IntentMandate(
            mandate_id="mandate-001",
            principal_id="user-001",
            scope=VALID_INTENT.scope,
            issued_at=VALID_INTENT.issued_at,
            expires_at=VALID_INTENT.expires_at,
            cart_hash="hash-abc",
            purchase_intent="",
        )
        verdict = _run_check(tmp_path, intent=intent)
    elif test_name == "t1_one":
        mock_t1_score.return_value = T1Result(score=1.0, intent_present=True)
        verdict = _run_check(tmp_path)
    elif test_name == "t1_threshold":
        mock_t1_score.return_value = T1Result(score=0.8, intent_present=True)
        verdict = _run_check(tmp_path, tau=0.65, t2_enabled=False)
    elif test_name == "t2_hold":
        mock_t2_verify.return_value = VerifierOutput(
            verdict=VerdictState.HOLD,
            evidence_spans=(),
            confidence=0.5,
            invoked=False,
            degraded_reason="DEGRADED_T2_LOW_CONFIDENCE",
        )
        verdict = _run_check(tmp_path, t2_enabled=True)
    else:
        verdict = _run_check(tmp_path, t2_enabled=True)

    assert verdict.policy_version is not None
    assert verdict.t1_model_hash is not None
    assert verdict.t2_model_id is not None


@patch("mandate_guard.cascade.t2_verify")
@patch("mandate_guard.cascade.t1_score")
def test_t2_allow_suppressed_never_returns_allow(
    mock_t1_score: object,
    mock_t2_verify: object,
    tmp_path: Path,
) -> None:
    mock_t1_score.return_value = T1Result(score=0.5, intent_present=True)
    mock_t2_verify.return_value = VerifierOutput(
        verdict=VerdictState.ALLOW,
        evidence_spans=(
            EvidenceSpan(field="f", text="looks fine", relevance="r"),
        ),
        confidence=0.99,
        invoked=True,
    )
    verdict = _run_check(tmp_path, t2_enabled=True)
    assert verdict.verdict != VerdictState.ALLOW
    assert verdict.verdict == VerdictState.HOLD
    assert verdict.reason_code == REASON_T2_ALLOW_SUPPRESSED
