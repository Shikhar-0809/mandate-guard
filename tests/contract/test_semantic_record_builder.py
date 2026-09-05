# mypy: disable-error-code=untyped-decorator
"""Contract tests for mandate_guard.semantic_record_builder."""

from __future__ import annotations

import random
import sys
from datetime import datetime
from pathlib import Path
from typing import TypedDict

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mandate_guard.eval import _record_to_t0_args
from mandate_guard.semantic_adjudication import adjudicate
from mandate_guard.semantic_record_builder import build_semantic_record
from mandate_guard.t0 import check as t0_check

_BASE_NOW = datetime(2026, 8, 1, 12, 0, 0)  # noqa: DTZ001

_SPEAKER = "Electronics > Audio > Speaker"
_HEADPHONES = "Electronics > Audio > Headphones"
_PHONE_CHARGER = "Electronics > Mobile > Phone Charger"
_PASTA = "Groceries > Pantry > Organic Pasta"

_WITHIN_AMOUNT = 1.05
_WITHIN_QUANTITY = 1.0
_BOUNDARY_AMOUNT = 1.15
_OUTSIDE_AMOUNT = 1.30


class _T0Case(TypedDict):
    id: str
    index: int
    category: str
    intent_leaf: str
    cart_leaf: str
    amount_ratio: float
    quantity_ratio: float
    rationale_present: bool
    seed: int


def test_same_leaf_within_tolerance_label_is_allow_and_matches_adjudicate() -> None:
    # Uses default base_unit_price_minor_units=1000 (₹10.00 placeholder until
    # the batch generator supplies per-leaf pricing).
    record = build_semantic_record(
        random.Random(7),
        index=1,
        category="Electronics",
        intent_leaf=_SPEAKER,
        cart_leaf=_SPEAKER,
        amount_ratio=_WITHIN_AMOUNT,
        quantity_ratio=_WITHIN_QUANTITY,
        rationale_present=False,
        now=_BASE_NOW,
    )
    expected = adjudicate(
        _SPEAKER,
        _SPEAKER,
        _WITHIN_AMOUNT,
        _WITHIN_QUANTITY,
        False,
    )
    assert record["label"] == "ALLOW"
    assert record["label"] == expected


@pytest.mark.parametrize(
    (
        "intent_leaf",
        "cart_leaf",
        "category",
        "amount_ratio",
        "quantity_ratio",
        "rationale",
    ),
    [
        (_SPEAKER, _PASTA, "Electronics", _WITHIN_AMOUNT, _WITHIN_QUANTITY, False),
        (_SPEAKER, _PASTA, "Electronics", _BOUNDARY_AMOUNT, 1.0, True),
        (_SPEAKER, _PASTA, "Electronics", _OUTSIDE_AMOUNT, 1.0, False),
    ],
    ids=["within-no-rationale", "boundary-with-rationale", "outside-no-rationale"],
)
def test_cross_top_level_is_deviation(
    intent_leaf: str,
    cart_leaf: str,
    category: str,
    amount_ratio: float,
    quantity_ratio: float,
    rationale: bool,
) -> None:
    record = build_semantic_record(
        random.Random(11),
        index=100,
        category=category,
        intent_leaf=intent_leaf,
        cart_leaf=cart_leaf,
        amount_ratio=amount_ratio,
        quantity_ratio=quantity_ratio,
        rationale_present=rationale,
        now=_BASE_NOW,
    )
    assert record["label"] == "DEVIATION"


_T0_CASES: list[_T0Case] = [
    {
        "id": "cross-top-level",
        "index": 201,
        "category": "Electronics",
        "intent_leaf": _SPEAKER,
        "cart_leaf": _PASTA,
        "amount_ratio": _WITHIN_AMOUNT,
        "quantity_ratio": _WITHIN_QUANTITY,
        "rationale_present": False,
        "seed": 21,
    },
    {
        "id": "same-leaf-within",
        "index": 202,
        "category": "Electronics",
        "intent_leaf": _SPEAKER,
        "cart_leaf": _SPEAKER,
        "amount_ratio": _WITHIN_AMOUNT,
        "quantity_ratio": _WITHIN_QUANTITY,
        "rationale_present": False,
        "seed": 22,
    },
    {
        "id": "same-leaf-boundary",
        "index": 203,
        "category": "Electronics",
        "intent_leaf": _SPEAKER,
        "cart_leaf": _SPEAKER,
        "amount_ratio": _BOUNDARY_AMOUNT,
        "quantity_ratio": _WITHIN_QUANTITY,
        "rationale_present": False,
        "seed": 23,
    },
    {
        "id": "same-leaf-outside",
        "index": 204,
        "category": "Electronics",
        "intent_leaf": _SPEAKER,
        "cart_leaf": _SPEAKER,
        "amount_ratio": _OUTSIDE_AMOUNT,
        "quantity_ratio": _WITHIN_QUANTITY,
        "rationale_present": False,
        "seed": 24,
    },
    {
        "id": "sibling-no-rationale",
        "index": 205,
        "category": "Electronics",
        "intent_leaf": _SPEAKER,
        "cart_leaf": _HEADPHONES,
        "amount_ratio": _WITHIN_AMOUNT,
        "quantity_ratio": _WITHIN_QUANTITY,
        "rationale_present": False,
        "seed": 25,
    },
    {
        "id": "sibling-with-rationale-within",
        "index": 206,
        "category": "Electronics",
        "intent_leaf": _SPEAKER,
        "cart_leaf": _HEADPHONES,
        "amount_ratio": _WITHIN_AMOUNT,
        "quantity_ratio": _WITHIN_QUANTITY,
        "rationale_present": True,
        "seed": 26,
    },
    {
        "id": "same-top-different-parent",
        "index": 207,
        "category": "Electronics",
        "intent_leaf": _SPEAKER,
        "cart_leaf": _PHONE_CHARGER,
        "amount_ratio": _BOUNDARY_AMOUNT,
        "quantity_ratio": _WITHIN_QUANTITY,
        "rationale_present": True,
        "seed": 27,
    },
]


@pytest.mark.parametrize("case", _T0_CASES, ids=[case["id"] for case in _T0_CASES])
def test_constructed_records_pass_t0(case: _T0Case) -> None:
    record = build_semantic_record(
        random.Random(case["seed"]),
        index=case["index"],
        category=case["category"],
        intent_leaf=case["intent_leaf"],
        cart_leaf=case["cart_leaf"],
        amount_ratio=case["amount_ratio"],
        quantity_ratio=case["quantity_ratio"],
        rationale_present=case["rationale_present"],
        now=_BASE_NOW,
    )
    t0_args = _record_to_t0_args(record)
    result = t0_check(**t0_args)
    assert result.passed is True
    assert result.triggered_rules == ()


def test_purchase_intent_includes_qty_digit_only_when_intent_qty_not_one() -> None:
    qty_one_intent: str | None = None
    multi_qty_intent: str | None = None
    for seed in range(500):
        record = build_semantic_record(
            random.Random(seed),
            index=300 + seed,
            category="Electronics",
            intent_leaf=_SPEAKER,
            cart_leaf=_SPEAKER,
            amount_ratio=1.0,
            quantity_ratio=1.0,
            rationale_present=False,
            now=_BASE_NOW,
        )
        intent = str(record["purchase_intent"])
        parts = intent.split()
        if len(parts) >= 2 and parts[1].isdigit():
            if multi_qty_intent is None:
                multi_qty_intent = intent
                assert parts[1] in {"2", "3", "4"}
        elif qty_one_intent is None:
            qty_one_intent = intent
            assert not parts[1].isdigit()
        if qty_one_intent is not None and multi_qty_intent is not None:
            break

    assert qty_one_intent is not None, "expected sampled intent_qty == 1 record"
    assert multi_qty_intent is not None, "expected sampled intent_qty > 1 record"
    assert not any(
        qty_one_intent.startswith(f"{verb} {digit} ")
        for verb in ("purchase", "buy", "order", "get")
        for digit in ("1", "2", "3", "4")
    )
    assert any(digit in multi_qty_intent.split() for digit in ("2", "3", "4"))


def test_determinism_given_seed() -> None:
    first = build_semantic_record(
        random.Random(99),
        index=500,
        category="Health & Personal Care",
        intent_leaf="Health & Personal Care > Oral Care > Toothbrush",
        cart_leaf="Health & Personal Care > Oral Care > Toothpaste",
        amount_ratio=1.05,
        quantity_ratio=1.0,
        rationale_present=True,
        now=_BASE_NOW,
    )
    second = build_semantic_record(
        random.Random(99),
        index=500,
        category="Health & Personal Care",
        intent_leaf="Health & Personal Care > Oral Care > Toothbrush",
        cart_leaf="Health & Personal Care > Oral Care > Toothpaste",
        amount_ratio=1.05,
        quantity_ratio=1.0,
        rationale_present=True,
        now=_BASE_NOW,
    )
    assert first == second


def test_different_seeds_vary_purchase_intent() -> None:
    record_a = build_semantic_record(
        random.Random(1),
        index=501,
        category="Electronics",
        intent_leaf=_SPEAKER,
        cart_leaf=_SPEAKER,
        amount_ratio=1.0,
        quantity_ratio=1.0,
        rationale_present=False,
        now=_BASE_NOW,
    )
    record_b = build_semantic_record(
        random.Random(2),
        index=501,
        category="Electronics",
        intent_leaf=_SPEAKER,
        cart_leaf=_SPEAKER,
        amount_ratio=1.0,
        quantity_ratio=1.0,
        rationale_present=False,
        now=_BASE_NOW,
    )
    assert record_a["purchase_intent"] != record_b["purchase_intent"]


@pytest.mark.parametrize("case", _T0_CASES, ids=[case["id"] for case in _T0_CASES])
def test_cart_hash_equals_intent_cart_hash(case: _T0Case) -> None:
    record = build_semantic_record(
        random.Random(case["seed"]),
        index=case["index"],
        category=case["category"],
        intent_leaf=case["intent_leaf"],
        cart_leaf=case["cart_leaf"],
        amount_ratio=case["amount_ratio"],
        quantity_ratio=case["quantity_ratio"],
        rationale_present=case["rationale_present"],
        now=_BASE_NOW,
    )
    assert record["cart_hash"] == record["intent_cart_hash"]


@pytest.mark.parametrize("case", _T0_CASES, ids=[case["id"] for case in _T0_CASES])
def test_semantic_metadata_round_trips(case: _T0Case) -> None:
    record = build_semantic_record(
        random.Random(case["seed"]),
        index=case["index"],
        category=case["category"],
        intent_leaf=case["intent_leaf"],
        cart_leaf=case["cart_leaf"],
        amount_ratio=case["amount_ratio"],
        quantity_ratio=case["quantity_ratio"],
        rationale_present=case["rationale_present"],
        now=_BASE_NOW,
    )
    category = case["category"]
    intent_leaf = case["intent_leaf"]
    cart_leaf = case["cart_leaf"]
    amount_ratio = case["amount_ratio"]
    quantity_ratio = case["quantity_ratio"]
    rationale_present = case["rationale_present"]
    assert record["semantic_category"] == category
    assert record["semantic_intent_leaf"] == intent_leaf
    assert record["semantic_cart_leaf"] == cart_leaf
    assert record["semantic_amount_ratio"] == amount_ratio
    assert record["semantic_quantity_ratio"] == quantity_ratio
    assert record["semantic_rationale_present"] is rationale_present
