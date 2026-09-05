"""Tests for contracts.t1_result.T1Result."""

from __future__ import annotations

import pytest

from contracts.t1_result import T1Result


def test_valid_present() -> None:
    result = T1Result(score=0.5, intent_present=True)
    assert result.score == 0.5
    assert result.intent_present is True
    assert result.reason is None


def test_invalid_present_score_none_raises() -> None:
    with pytest.raises(ValueError, match="score must not be None"):
        T1Result(score=None, intent_present=True)


def test_invalid_absent_with_score_raises() -> None:
    with pytest.raises(ValueError, match="score must be None"):
        T1Result(score=0.5, intent_present=False)


def test_invalid_absent_reason_none_raises() -> None:
    with pytest.raises(ValueError, match='reason must be "INTENT_ABSENT"'):
        T1Result(score=None, intent_present=False, reason=None)


def test_valid_absent() -> None:
    result = T1Result(score=None, intent_present=False, reason="INTENT_ABSENT")
    assert result.score is None
    assert result.intent_present is False
    assert result.reason == "INTENT_ABSENT"


def test_invalid_present_score_above_range_raises() -> None:
    with pytest.raises(ValueError, match="score must be in"):
        T1Result(score=1.5, intent_present=True, reason=None)


def test_invalid_present_score_below_range_raises() -> None:
    with pytest.raises(ValueError, match="score must be in"):
        T1Result(score=-0.1, intent_present=True, reason=None)
