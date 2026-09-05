"""Contract tests for M1 semantic eval helpers (synthetic fixtures only)."""

from __future__ import annotations

import importlib.util
import json
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
from mandate_guard.eval import cascade_verdict_rate
from mandate_guard.normalize import normalize_semantic_labels_for_training

_RUN_EVAL_SEMANTIC_SPEC = importlib.util.spec_from_file_location(
    "run_eval_semantic", PROJECT_ROOT / "scripts" / "run_eval_semantic.py"
)
assert (
    _RUN_EVAL_SEMANTIC_SPEC is not None and _RUN_EVAL_SEMANTIC_SPEC.loader is not None
)
_run_eval_semantic = importlib.util.module_from_spec(_RUN_EVAL_SEMANTIC_SPEC)
sys.modules[_RUN_EVAL_SEMANTIC_SPEC.name] = _run_eval_semantic
_RUN_EVAL_SEMANTIC_SPEC.loader.exec_module(_run_eval_semantic)
evaluate_kill_criterion = _run_eval_semantic.evaluate_kill_criterion
write_baselines_sealed_semantic = _run_eval_semantic.write_baselines_sealed_semantic

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


def test_cascade_verdict_rate_counts_target_verdict_only() -> None:
    records: list[dict[str, object]] = [{"record_id": f"r{i}"} for i in range(4)]
    verdict_sequence = [
        _make_verdict(VerdictState.BLOCK),
        _make_verdict(VerdictState.BLOCK),
        _make_verdict(VerdictState.HOLD),
        _make_verdict(VerdictState.ALLOW),
    ]

    with patch(
        "mandate_guard.eval.run_cascade_on_record",
        side_effect=verdict_sequence * 2,
    ):
        block_rate = cascade_verdict_rate(
            records,
            MODEL_DIR,
            0.5,
            T2Config(t2_enabled=False),
            VerdictState.BLOCK,
        )
        hold_rate = cascade_verdict_rate(
            records,
            MODEL_DIR,
            0.5,
            T2Config(t2_enabled=False),
            VerdictState.HOLD,
        )

    assert block_rate == 0.5
    assert hold_rate == 0.25


def test_cascade_verdict_rate_empty_records_returns_zero() -> None:
    assert (
        cascade_verdict_rate(
            [],
            MODEL_DIR,
            0.5,
            T2Config(t2_enabled=False),
            VerdictState.BLOCK,
        )
        == 0.0
    )


def test_kill_criterion_boundary_inclusive_lower() -> None:
    result = evaluate_kill_criterion(
        recall_t2_off=0.0,
        recall_t2_on=0.05,
        hn_block_rate_t2_off=0.00,
        hn_block_rate_t2_on=0.01,
    )
    assert result["recall_lift"] == pytest.approx(0.05)
    assert result["hn_fpr_delta"] == pytest.approx(0.01)
    assert result["kill_criterion_met"] is True


def test_kill_criterion_boundary_exclusive_upper() -> None:
    result = evaluate_kill_criterion(
        recall_t2_off=0.30,
        recall_t2_on=0.80,
        hn_block_rate_t2_off=0.00,
        hn_block_rate_t2_on=0.02,
    )
    assert result["hn_fpr_delta"] == pytest.approx(0.02)
    assert result["kill_criterion_met"] is False


def test_write_once_guard_refuses_to_overwrite(tmp_path: Path) -> None:
    output_path = tmp_path / "baselines_sealed_semantic.json"
    original_payload = {"tau_star": 0.42, "kill_criterion_met": False}
    output_path.write_text(json.dumps(original_payload), encoding="utf-8")
    before = output_path.read_text(encoding="utf-8")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_baselines_sealed_semantic(
            output_path,
            {"tau_star": 0.99, "kill_criterion_met": True},
        )

    after = output_path.read_text(encoding="utf-8")
    assert after == before


def test_deviation_population_matches_original_deviation_records() -> None:
    raw_records: list[dict[str, object]] = [
        {"record_id": "allow-1", "label": "ALLOW"},
        {"record_id": "dev-1", "label": "DEVIATION"},
        {"record_id": "dev-2", "label": "DEVIATION"},
        {"record_id": "unc-1", "label": "UNCERTAIN"},
        {"record_id": "allow-2", "label": "ALLOW"},
    ]
    original_deviation_ids = {
        str(record["record_id"])
        for record in raw_records
        if str(record["label"]) == "DEVIATION"
    }

    normalized = normalize_semantic_labels_for_training(raw_records)
    deviation_population_ids = {
        str(record["record_id"])
        for record in normalized
        if str(record["label"]) == "BLOCK"
    }

    assert deviation_population_ids == original_deviation_ids
