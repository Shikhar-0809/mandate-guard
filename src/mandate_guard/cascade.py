"""Unified T0→T1→T2 cascade producing a frozen Verdict."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from contracts import (
    CartMandate,
    DelegationToken,
    IntentMandate,
    Money,
    T1Result,
    T2Config,
    Verdict,
    VerdictState,
    VerifierOutput,
)

from mandate_guard.t0 import check as t0_check
from mandate_guard.t1 import score as t1_score
from mandate_guard.t2 import UntrustedBlob, verify as t2_verify

POLICY_VERSION = "v1"

REASON_NO_SEMANTIC_EVIDENCE = "NO_SEMANTIC_EVIDENCE"
REASON_T1_SEMANTIC_DEVIATION = "T1_SEMANTIC_DEVIATION"
REASON_T1_ABOVE_THRESHOLD = "T1_ABOVE_THRESHOLD"
REASON_OK = "OK"
REASON_T2_SEMANTIC_BLOCK = "T2_SEMANTIC_BLOCK"
REASON_T2_ALLOW_SUPPRESSED = "T2_ALLOW_SUPPRESSED"
REASON_T2_HOLD = "T2_HOLD"


class _PinningFields(TypedDict):
    agent_request_id: str
    mandate_id: str
    frozen_at: datetime
    policy_version: str
    t1_model_hash: str
    t2_model_id: str


def _t1_model_hash(model_dir: Path) -> str:
    path = model_dir / "t1_model.joblib"
    if not path.exists():
        return "TODO:missing-t1-model"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _t2_model_id() -> str:
    return os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")


def _pinning_fields(
    agent_request_id: str,
    mandate_id: str,
    now: datetime,
    model_dir: Path,
) -> _PinningFields:
    return {
        "agent_request_id": agent_request_id,
        "mandate_id": mandate_id,
        "frozen_at": now,
        "policy_version": POLICY_VERSION,
        "t1_model_hash": _t1_model_hash(model_dir),
        "t2_model_id": _t2_model_id(),
    }


def _typed_to_t1_record(
    intent: IntentMandate,
    cart: CartMandate,
    transaction_amount: Money,
    merchant_id: str,
    mcc: str,
    token: DelegationToken | None = None,
) -> dict[str, object]:
    """Serialize typed mandate inputs into the flat record schema t1.score() expects."""
    record: dict[str, object] = {
        "intent_mandate_id": intent.mandate_id,
        "intent_principal_id": intent.principal_id,
        "intent_scope_merchants": (
            sorted(intent.scope.merchants)
            if intent.scope.merchants is not None
            else None
        ),
        "intent_scope_categories": (
            sorted(intent.scope.categories)
            if intent.scope.categories is not None
            else None
        ),
        "intent_scope_max_amount_minor_units": (
            intent.scope.max_amount.minor_units if intent.scope.max_amount else None
        ),
        "intent_scope_max_amount_currency": (
            intent.scope.max_amount.currency if intent.scope.max_amount else None
        ),
        "intent_issued_at": intent.issued_at.isoformat(),
        "intent_expires_at": intent.expires_at.isoformat(),
        "intent_cart_hash": intent.cart_hash,
        "purchase_intent": intent.purchase_intent,
        "cart_mandate_id": cart.mandate_id,
        "cart_items": [
            {
                "sku": item.sku,
                "name": item.name,
                "quantity": item.quantity,
                "unit_price_minor_units": item.unit_price.minor_units,
                "unit_price_currency": item.unit_price.currency,
            }
            for item in cart.items
        ],
        "cart_total_minor_units": cart.total.minor_units,
        "cart_total_currency": cart.total.currency,
        "cart_hash": cart.cart_hash,
        "transaction_amount_minor_units": transaction_amount.minor_units,
        "transaction_amount_currency": transaction_amount.currency,
        "merchant_id": merchant_id,
        "mcc": mcc,
    }
    if token is not None:
        record["delegation_token_id"] = token.token_id
    return record


def _t2_evidence_text(result: VerifierOutput) -> str | None:
    if not result.evidence_spans:
        return None
    return " | ".join(span.text for span in result.evidence_spans)


def _verdict_from_t2(
    t1_score_value: float,
    result: VerifierOutput,
    pinning: _PinningFields,
) -> Verdict:
    if result.verdict == VerdictState.BLOCK and result.invoked:
        return Verdict(
            verdict=VerdictState.BLOCK,
            reason_code=REASON_T2_SEMANTIC_BLOCK,
            t0_triggered=False,
            t1_score=t1_score_value,
            t2_evidence=_t2_evidence_text(result),
            **pinning,
        )

    if result.verdict == VerdictState.ALLOW:
        return Verdict(
            verdict=VerdictState.HOLD,
            reason_code=REASON_T2_ALLOW_SUPPRESSED,
            t0_triggered=False,
            t1_score=t1_score_value,
            t2_evidence=None,
            **pinning,
        )

    reason_code = result.degraded_reason or REASON_T2_HOLD
    evidence = _t2_evidence_text(result) if result.invoked else None
    return Verdict(
        verdict=VerdictState.HOLD,
        reason_code=reason_code,
        t0_triggered=False,
        t1_score=t1_score_value,
        t2_evidence=evidence,
        **pinning,
    )


def check(
    intent: IntentMandate,
    cart: CartMandate,
    token: DelegationToken | None,
    transaction_amount: Money,
    merchant_id: str,
    mcc: str,
    now: datetime,
    agent_request_id: str,
    model_dir: Path,
    tau: float,
    t2_config: T2Config,
    merchant_catalog_snippet: UntrustedBlob | None = None,
    agent_rationale: UntrustedBlob | None = None,
) -> Verdict:
    """Run T0→T1→T2 and return a frozen Verdict."""
    pinning = _pinning_fields(agent_request_id, intent.mandate_id, now, model_dir)

    t0_result = t0_check(
        intent,
        cart,
        token,
        transaction_amount,
        merchant_id,
        mcc,
        now,
    )
    if not t0_result.passed:
        assert t0_result.reason_code is not None
        return Verdict(
            verdict=VerdictState.BLOCK,
            reason_code=t0_result.reason_code,
            t0_triggered=True,
            t1_score=None,
            t2_evidence=None,
            **pinning,
        )

    record = _typed_to_t1_record(
        intent, cart, transaction_amount, merchant_id, mcc, token
    )
    t1_result: T1Result = t1_score(record, model_dir)

    if not t1_result.intent_present:
        return Verdict(
            verdict=VerdictState.ALLOW,
            reason_code=REASON_NO_SEMANTIC_EVIDENCE,
            t0_triggered=False,
            t1_score=None,
            t2_evidence=None,
            **pinning,
        )

    assert t1_result.score is not None
    score = t1_result.score

    if score == 1.0:
        return Verdict(
            verdict=VerdictState.BLOCK,
            reason_code=REASON_T1_SEMANTIC_DEVIATION,
            t0_triggered=False,
            t1_score=1.0,
            t2_evidence=None,
            **pinning,
        )

    invoke_t2 = (
        t2_config.t2_enabled
        and bool(intent.purchase_intent)
        and score < 1.0
    )
    if invoke_t2:
        t2_result = t2_verify(
            intent,
            cart,
            merchant_catalog_snippet,
            agent_rationale,
            t2_config,
        )
        return _verdict_from_t2(score, t2_result, pinning)

    if score >= tau:
        return Verdict(
            verdict=VerdictState.BLOCK,
            reason_code=REASON_T1_ABOVE_THRESHOLD,
            t0_triggered=False,
            t1_score=score,
            t2_evidence=None,
            **pinning,
        )

    return Verdict(
        verdict=VerdictState.ALLOW,
        reason_code=REASON_OK,
        t0_triggered=False,
        t1_score=score,
        t2_evidence=None,
        **pinning,
    )
