"""Contract tests for mandate_guard.semantic_adjudication."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mandate_guard.semantic_adjudication import (
    adjudicate,
    combined_tolerance_state,
    tolerance_state,
)
from mandate_guard.taxonomy import TAXONOMY_LEAVES

_SPEAKER = "Electronics > Audio > Speaker"
_HEADPHONES = "Electronics > Audio > Headphones"
_PHONE_CHARGER = "Electronics > Mobile > Phone Charger"
_PASTA = "Groceries > Pantry > Organic Pasta"

_WITHIN_AMOUNT = 1.05
_WITHIN_QUANTITY = 1.0
_BOUNDARY_AMOUNT = 1.15
_BOUNDARY_QUANTITY = 1.0
_OUTSIDE_AMOUNT = 1.30
_OUTSIDE_QUANTITY = 1.0


@pytest.mark.parametrize(
    ("amount_ratio", "quantity_ratio", "rationale_present"),
    [
        (_WITHIN_AMOUNT, _WITHIN_QUANTITY, False),
        (_BOUNDARY_AMOUNT, _BOUNDARY_QUANTITY, True),
        (_OUTSIDE_AMOUNT, _OUTSIDE_QUANTITY, True),
    ],
    ids=["within-no-rationale", "boundary-with-rationale", "outside-with-rationale"],
)
def test_cross_top_level_is_deviation_regardless_of_tolerance_or_rationale(
    amount_ratio: float,
    quantity_ratio: float,
    rationale_present: bool,
) -> None:
    assert (
        adjudicate(
            _SPEAKER,
            _PASTA,
            amount_ratio,
            quantity_ratio,
            rationale_present,
        )
        == "DEVIATION"
    )


@pytest.mark.parametrize(
    ("amount_ratio", "quantity_ratio", "expected"),
    [
        (_WITHIN_AMOUNT, _WITHIN_QUANTITY, "ALLOW"),
        (_BOUNDARY_AMOUNT, _BOUNDARY_QUANTITY, "UNCERTAIN"),
        (_OUTSIDE_AMOUNT, _OUTSIDE_QUANTITY, "DEVIATION"),
    ],
    ids=["within", "boundary", "outside"],
)
def test_same_leaf_maps_tolerance_to_label(
    amount_ratio: float,
    quantity_ratio: float,
    expected: str,
) -> None:
    assert (
        adjudicate(
            _SPEAKER,
            _SPEAKER,
            amount_ratio,
            quantity_ratio,
            rationale_present=False,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("amount_ratio", "quantity_ratio"),
    [
        (_WITHIN_AMOUNT, _WITHIN_QUANTITY),
        (_BOUNDARY_AMOUNT, _BOUNDARY_QUANTITY),
        (_OUTSIDE_AMOUNT, _OUTSIDE_QUANTITY),
    ],
    ids=["within", "boundary", "outside"],
)
def test_sibling_without_rationale_is_always_deviation(
    amount_ratio: float,
    quantity_ratio: float,
) -> None:
    assert (
        adjudicate(
            _SPEAKER,
            _HEADPHONES,
            amount_ratio,
            quantity_ratio,
            rationale_present=False,
        )
        == "DEVIATION"
    )


@pytest.mark.parametrize(
    ("amount_ratio", "quantity_ratio", "expected"),
    [
        (_WITHIN_AMOUNT, _WITHIN_QUANTITY, "ALLOW"),
        (_BOUNDARY_AMOUNT, _BOUNDARY_QUANTITY, "UNCERTAIN"),
        (_OUTSIDE_AMOUNT, _OUTSIDE_QUANTITY, "UNCERTAIN"),
    ],
    ids=["within", "boundary", "outside"],
)
def test_sibling_with_rationale_maps_tolerance_to_label(
    amount_ratio: float,
    quantity_ratio: float,
    expected: str,
) -> None:
    assert (
        adjudicate(
            _SPEAKER,
            _HEADPHONES,
            amount_ratio,
            quantity_ratio,
            rationale_present=True,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("amount_ratio", "quantity_ratio", "rationale_present"),
    [
        (_WITHIN_AMOUNT, _WITHIN_QUANTITY, False),
        (_BOUNDARY_AMOUNT, _BOUNDARY_QUANTITY, True),
        (_OUTSIDE_AMOUNT, _OUTSIDE_QUANTITY, False),
    ],
    ids=["within-no-rationale", "boundary-with-rationale", "outside-no-rationale"],
)
def test_same_top_level_different_parent_is_always_uncertain(
    amount_ratio: float,
    quantity_ratio: float,
    rationale_present: bool,
) -> None:
    assert (
        adjudicate(
            _SPEAKER,
            _PHONE_CHARGER,
            amount_ratio,
            quantity_ratio,
            rationale_present,
        )
        == "UNCERTAIN"
    )


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [
        (1.10, "WITHIN"),
        (0.90, "WITHIN"),
        (1.20, "BOUNDARY"),
        (0.80, "BOUNDARY"),
        (1.21, "OUTSIDE"),
        (0.79, "OUTSIDE"),
    ],
    ids=[
        "upper-within-edge",
        "lower-within-edge",
        "upper-boundary-edge",
        "lower-boundary-edge",
        "upper-outside",
        "lower-outside",
    ],
)
def test_tolerance_state_boundary_edges(ratio: float, expected: str) -> None:
    assert tolerance_state(ratio) == expected


def test_combined_tolerance_state_takes_worse_state() -> None:
    assert combined_tolerance_state(1.05, 1.30) == "OUTSIDE"
    assert combined_tolerance_state(1.15, 1.05) == "BOUNDARY"
    assert combined_tolerance_state(1.05, 1.0) == "WITHIN"


def _structural_branch(intent_leaf: str, cart_leaf: str) -> int:
    path_a = intent_leaf.split(" > ")
    path_b = cart_leaf.split(" > ")
    if path_a[0] != path_b[0]:
        return 1
    if path_a == path_b:
        return 2
    if path_a[:2] == path_b[:2]:
        return 3
    return 4


def test_taxonomy_pair_coverage_requirements() -> None:
    branch_1_exists = False
    branch_3_exists = False
    branch_4_by_top_level: dict[str, bool] = {}

    for intent_leaf in TAXONOMY_LEAVES:
        top_level = intent_leaf.split(" > ", 1)[0]
        branch_4_by_top_level.setdefault(top_level, False)

    for intent_leaf in TAXONOMY_LEAVES:
        for cart_leaf in TAXONOMY_LEAVES:
            branch = _structural_branch(intent_leaf, cart_leaf)
            if branch == 1:
                branch_1_exists = True
            elif branch == 3:
                branch_3_exists = True
            elif branch == 4:
                top_level = intent_leaf.split(" > ", 1)[0]
                branch_4_by_top_level[top_level] = True

    assert branch_1_exists, "expected at least one cross-top-level leaf pair"
    assert branch_3_exists, "expected at least one same-parent sibling pair"
    assert len(branch_4_by_top_level) == 10
    missing = [
        category for category, covered in branch_4_by_top_level.items() if not covered
    ]
    assert not missing, (
        "every top-level category must have a same-top-level-different-parent "
        f"leaf pair; missing: {missing}"
    )
