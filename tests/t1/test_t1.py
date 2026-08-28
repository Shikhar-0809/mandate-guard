"""Tests for mandate_guard.t1."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from contracts import CartItem, CartMandate, IntentMandate, Money, Scope
from mandate_guard.t1 import _load_model, score, train

_DATA_DEV = Path(__file__).resolve().parents[2] / "data" / "dev"
DEV_RECORDS = (
    [
        json.loads(line)
        for line in (_DATA_DEV / "benign.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    + [
        json.loads(line)
        for line in (_DATA_DEV / "hard_negatives.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    + [
        json.loads(line)
        for line in (_DATA_DEV / "attacks.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
)

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


@pytest.fixture(scope="module")
def trained_model_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    model_dir = tmp_path_factory.mktemp("model")
    train(DEV_RECORDS, model_dir)
    yield model_dir
    _load_model.cache_clear()


def test_train_returns_metrics(tmp_path: Path) -> None:
    metrics = train(DEV_RECORDS, tmp_path)
    assert set(metrics.keys()) >= {"auc", "precision", "recall", "ece"}
    for value in metrics.values():
        assert isinstance(value, float)


def test_metrics_in_range(tmp_path: Path) -> None:
    metrics = train(DEV_RECORDS, tmp_path)
    assert 0.0 <= metrics["auc"] <= 1.0
    assert 0.0 <= metrics["precision"] <= 1.0
    assert 0.0 <= metrics["recall"] <= 1.0
    assert 0.0 <= metrics["ece"] <= 1.0


def test_baselines_written(tmp_path: Path) -> None:
    train(DEV_RECORDS, tmp_path)
    baselines_path = Path(__file__).resolve().parents[2] / "baselines.json"
    assert baselines_path.exists()
    baselines = json.loads(baselines_path.read_text(encoding="utf-8"))
    assert "t1_auc" in baselines


def test_score_valid_transaction(trained_model_dir: Path) -> None:
    _load_model.cache_clear()
    prob = score(
        VALID_INTENT,
        VALID_CART,
        None,
        Money(1000, "INR"),
        VALID_MERCHANT,
        VALID_MCC,
        BASE_NOW,
        trained_model_dir,
    )
    assert 0.0 <= prob <= 1.0


def test_score_attack_transaction(trained_model_dir: Path) -> None:
    _load_model.cache_clear()
    prob = score(
        VALID_INTENT,
        VALID_CART,
        None,
        Money(20000, "INR"),
        VALID_MERCHANT,
        VALID_MCC,
        BASE_NOW,
        trained_model_dir,
    )
    assert 0.0 <= prob <= 1.0


def test_score_deterministic(trained_model_dir: Path) -> None:
    _load_model.cache_clear()
    prob1 = score(
        VALID_INTENT,
        VALID_CART,
        None,
        Money(1000, "INR"),
        VALID_MERCHANT,
        VALID_MCC,
        BASE_NOW,
        trained_model_dir,
    )
    prob2 = score(
        VALID_INTENT,
        VALID_CART,
        None,
        Money(1000, "INR"),
        VALID_MERCHANT,
        VALID_MCC,
        BASE_NOW,
        trained_model_dir,
    )
    assert prob1 == prob2
