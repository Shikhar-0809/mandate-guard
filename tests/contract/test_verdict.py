"""Tests for contracts.verdict.Verdict and VerdictState."""

from __future__ import annotations

from datetime import datetime

import pytest

from contracts.verdict import Verdict, VerdictState

FROZEN_AT = datetime(2026, 6, 15, 10, 30, 0)  # noqa: DTZ001


def _verdict(**overrides: object) -> Verdict:
    defaults: dict[str, object] = {
        "verdict": VerdictState.ALLOW,
        "reason_code": "OK",
        "agent_request_id": "req-001",
        "mandate_id": "mandate-001",
        "t0_triggered": False,
        "frozen_at": FROZEN_AT,
    }
    defaults.update(overrides)
    return Verdict(**defaults)  # type: ignore[arg-type]


def test_valid_allow_verdict() -> None:
    verdict = _verdict()
    assert verdict.verdict == VerdictState.ALLOW


def test_valid_hold_verdict() -> None:
    verdict = _verdict(verdict=VerdictState.HOLD, reason_code="REVIEW")
    assert verdict.verdict == VerdictState.HOLD


def test_valid_block_verdict() -> None:
    verdict = _verdict(verdict=VerdictState.BLOCK, reason_code="DENIED")
    assert verdict.verdict == VerdictState.BLOCK


def test_allow_with_t0_triggered_raises() -> None:
    with pytest.raises(
        ValueError,
        match="ALLOW verdict is inconsistent with a triggered T0 rule",
    ):
        _verdict(t0_triggered=True)


def test_block_with_t0_triggered_is_valid() -> None:
    verdict = _verdict(
        verdict=VerdictState.BLOCK,
        reason_code="T0_VIOLATION",
        t0_triggered=True,
    )
    assert verdict.t0_triggered is True


def test_empty_reason_code_raises() -> None:
    with pytest.raises(ValueError):
        _verdict(reason_code="")


def test_t1_score_in_range_is_valid() -> None:
    verdict = _verdict(t1_score=0.95)
    assert verdict.t1_score == 0.95


def test_t1_score_above_range_raises() -> None:
    with pytest.raises(ValueError, match="t1_score must be in"):
        _verdict(t1_score=1.1)


def test_t1_score_below_range_raises() -> None:
    with pytest.raises(ValueError, match="t1_score must be in"):
        _verdict(t1_score=-0.1)


def test_t1_score_none_is_valid() -> None:
    verdict = _verdict(t1_score=None)
    assert verdict.t1_score is None


def test_t2_evidence_set_is_valid() -> None:
    verdict = _verdict(t2_evidence="semantic mismatch on SKU")
    assert verdict.t2_evidence == "semantic mismatch on SKU"


def test_t2_evidence_none_is_valid() -> None:
    verdict = _verdict(t2_evidence=None)
    assert verdict.t2_evidence is None


def test_verdict_state_serialises_to_plain_strings() -> None:
    assert VerdictState.ALLOW.value == "ALLOW"
    assert VerdictState.HOLD.value == "HOLD"
    assert VerdictState.BLOCK.value == "BLOCK"
