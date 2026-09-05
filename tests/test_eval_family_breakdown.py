"""Tests for recall_by_family (synthetic fixtures, mocked cascade)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from contracts import T2Config
from contracts.verdict import Verdict, VerdictState
from mandate_guard.eval import recall_by_family

MODEL_DIR = PROJECT_ROOT / "models"


def _make_verdict(state: VerdictState) -> Verdict:
    return Verdict(
        verdict=state,
        reason_code="TEST",
        agent_request_id="test-agent",
        mandate_id="test-mandate",
        t0_triggered=False,
        frozen_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _record(family: str, label: str, record_id: str) -> dict[str, object]:
    return {"family": family, "label": label, "record_id": record_id}


def test_recall_by_family_groups_correctly() -> None:
    records = [
        _record("a", "BLOCK", "a0"),
        _record("a", "BLOCK", "a1"),
        _record("a", "BLOCK", "a2"),
        _record("b", "BLOCK", "b0"),
        _record("b", "BLOCK", "b1"),
    ]
    block_by_id = {
        "a0": VerdictState.BLOCK,
        "a1": VerdictState.BLOCK,
        "a2": VerdictState.ALLOW,
        "b0": VerdictState.BLOCK,
        "b1": VerdictState.BLOCK,
    }

    def mock_cascade(
        record: dict[str, object],
        model_dir: Path,
        tau: float,
        t2_config: T2Config,
    ) -> Verdict:
        return _make_verdict(block_by_id[str(record["record_id"])])

    with patch("mandate_guard.eval.run_cascade_on_record", side_effect=mock_cascade):
        result = recall_by_family(
            records,
            MODEL_DIR,
            1.0,
            T2Config(t2_enabled=False),
        )

    assert result == {"a": pytest.approx(2 / 3), "b": 1.0}


def test_recall_by_family_family_with_no_block_records_returns_zero() -> None:
    records = [
        _record("allow_only", "ALLOW", "x0"),
        _record("allow_only", "ALLOW", "x1"),
    ]

    with patch(
        "mandate_guard.eval.run_cascade_on_record",
        side_effect=AssertionError("cascade must not run"),
    ):
        result = recall_by_family(
            records,
            MODEL_DIR,
            1.0,
            T2Config(t2_enabled=False),
        )

    assert result == {"allow_only": 0.0}


def test_recall_by_family_ignores_allow_records_in_denominator() -> None:
    records = [
        _record("mixed", "BLOCK", "m0"),
        _record("mixed", "BLOCK", "m1"),
        _record("mixed", "ALLOW", "m2"),
        _record("mixed", "ALLOW", "m3"),
        _record("mixed", "ALLOW", "m4"),
    ]

    with patch(
        "mandate_guard.eval.run_cascade_on_record",
        return_value=_make_verdict(VerdictState.BLOCK),
    ) as mock_cascade:
        result = recall_by_family(
            records,
            MODEL_DIR,
            1.0,
            T2Config(t2_enabled=False),
        )

    assert result == {"mixed": 1.0}
    assert mock_cascade.call_count == 2
