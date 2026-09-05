# mypy: disable-error-code=untyped-decorator
"""Contract tests for semantic corpus batch generation in data/generate.py."""

from __future__ import annotations

import importlib.util
import json
import random
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_GENERATE_SPEC = importlib.util.spec_from_file_location(
    "corpus_generate_semantic_batch", PROJECT_ROOT / "data" / "generate.py"
)
assert _GENERATE_SPEC is not None and _GENERATE_SPEC.loader is not None
_corpus_generate = importlib.util.module_from_spec(_GENERATE_SPEC)
sys.modules[_GENERATE_SPEC.name] = _corpus_generate
_GENERATE_SPEC.loader.exec_module(_corpus_generate)

LEAF_BASE_PRICE = _corpus_generate.LEAF_BASE_PRICE
SEMANTIC_PRICE_BANDS_MINOR = _corpus_generate._SEMANTIC_PRICE_BANDS_MINOR
SINGLETON_PARENT_INTENT_LEAVES = _corpus_generate._SINGLETON_PARENT_INTENT_LEAVES
generate_semantic_corpus = _corpus_generate.generate_semantic_corpus

from mandate_guard.eval import _record_to_t0_args
from mandate_guard.t0 import check as t0_check
from mandate_guard.taxonomy import TAXONOMY_LEAVES

_BASE_NOW = datetime(2026, 8, 1, 12, 0, 0)  # noqa: DTZ001


def _is_sibling_pair(intent_leaf: str, cart_leaf: str) -> bool:
    path_a = intent_leaf.split(" > ")
    path_b = cart_leaf.split(" > ")
    return path_a[0] == path_b[0] and path_a[:2] == path_b[:2] and path_a != path_b


@pytest.fixture
def semantic_records() -> list[dict[str, object]]:
    return generate_semantic_corpus(random.Random(271), _BASE_NOW)


def test_generate_semantic_corpus_produces_500_records(
    semantic_records: list[dict[str, object]],
) -> None:
    assert len(semantic_records) == 500


def test_ten_families_with_fifty_records_each(
    semantic_records: list[dict[str, object]],
) -> None:
    by_family = Counter(str(record["family"]) for record in semantic_records)
    assert len(by_family) == 10
    assert all(count == 50 for count in by_family.values())


def test_per_family_label_counts(
    semantic_records: list[dict[str, object]],
) -> None:
    by_family: dict[str, Counter[str]] = {}
    for record in semantic_records:
        family = str(record["family"])
        by_family.setdefault(family, Counter())[str(record["label"])] += 1
    expected = {"ALLOW": 20, "DEVIATION": 19, "UNCERTAIN": 11}
    for family, counts in by_family.items():
        assert dict(counts) == expected, family


def test_all_records_pass_t0(
    semantic_records: list[dict[str, object]],
) -> None:
    for record in semantic_records:
        result = t0_check(**_record_to_t0_args(record))
        assert result.passed is True
        assert result.triggered_rules == ()


def test_sibling_cases_exclude_singleton_parent_intent_leaves(
    semantic_records: list[dict[str, object]],
) -> None:
    for record in semantic_records:
        intent_leaf = str(record["semantic_intent_leaf"])
        cart_leaf = str(record["semantic_cart_leaf"])
        if not _is_sibling_pair(intent_leaf, cart_leaf):
            continue
        assert intent_leaf not in SINGLETON_PARENT_INTENT_LEAVES


def test_generate_semantic_corpus_is_deterministic() -> None:
    first = generate_semantic_corpus(random.Random(271), _BASE_NOW)
    second = generate_semantic_corpus(random.Random(271), _BASE_NOW)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_leaf_base_price_table_covers_all_leaves_with_valid_bands() -> None:
    assert len(LEAF_BASE_PRICE) == len(TAXONOMY_LEAVES) == 129
    assert set(LEAF_BASE_PRICE) == set(TAXONOMY_LEAVES)
    for leaf, price in LEAF_BASE_PRICE.items():
        top_level = leaf.split(" > ", 1)[0]
        lo, hi = SEMANTIC_PRICE_BANDS_MINOR[top_level]
        assert lo <= price <= hi
