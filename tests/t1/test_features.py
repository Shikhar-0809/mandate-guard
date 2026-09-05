"""Tests for mandate_guard.features."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mandate_guard.features import FEATURE_NAMES, extract_features
from mandate_guard.taxonomy import build_taxonomy_vectorizer, taxonomy_leaf_matrix


@pytest.fixture(scope="module")
def taxonomy_artifacts() -> tuple[object, object]:
    vec = build_taxonomy_vectorizer()
    return vec, taxonomy_leaf_matrix(vec)


def _base_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "purchase_intent": "",
        "cart_items": [{"name": "USB Cable", "quantity": 2}],
        "amount_minor_units": 1000,
        "per_txn_cap_minor_units": 10000,
    }
    record.update(overrides)
    return record


def _category_distance(
    record: dict[str, object],
    taxonomy_artifacts: tuple[object, object],
) -> float:
    vec, leaves = taxonomy_artifacts
    features = extract_features(
        record,
        taxonomy_vectorizer=vec,
        taxonomy_leaf_matrix=leaves,
    )
    return features[FEATURE_NAMES.index("category_hierarchy_distance")]


def test_feature_count() -> None:
    features = extract_features(_base_record())
    assert len(features) == len(FEATURE_NAMES) == 8


def test_all_finite() -> None:
    features = extract_features(_base_record())
    assert all(math.isfinite(value) for value in features)


def test_jaccard_token_overlap() -> None:
    record = _base_record(
        purchase_intent="buy Zoom license",
        cart_items=[{"name": "Zoom Annual License", "quantity": 1}],
    )
    features = extract_features(record)
    index = FEATURE_NAMES.index("jaccard_token_overlap")
    assert features[index] > 0.3


def test_tfidf_cosine_sim_none() -> None:
    record = _base_record(purchase_intent="buy Zoom license")
    features = extract_features(record, tfidf_vectorizer=None)
    index = FEATURE_NAMES.index("tfidf_cosine_sim")
    assert features[index] == 0.0


def test_deterministic() -> None:
    record = _base_record()
    assert extract_features(record) == extract_features(record)


def test_jaccard_and_trigram_preserve_genuine_overlap_after_verb_strip() -> None:
    """Corpus -217 pair: shared content token must survive leading 'order' strip."""
    record = _base_record(
        purchase_intent="order Rice Noodles",
        cart_items=[{"name": "Brown Rice", "quantity": 1}],
    )
    features = extract_features(record)
    jaccard_index = FEATURE_NAMES.index("jaccard_token_overlap")
    trigram_index = FEATURE_NAMES.index("char_trigram_overlap")
    assert features[jaccard_index] > 0.0
    assert features[trigram_index] > 0.0


def test_char_trigram_eliminates_order_power_spurious_collision() -> None:
    """Corpus -208 pair: 'order'/'power' must not share trigram 'er ' after strip."""
    record = _base_record(
        purchase_intent="order Green Tea",
        cart_items=[{"name": "Power Bank", "quantity": 1}],
    )
    features = extract_features(record)
    trigram_index = FEATURE_NAMES.index("char_trigram_overlap")
    assert features[trigram_index] == 0.0


def test_category_hierarchy_distance_same_product_zero(
    taxonomy_artifacts: tuple[object, object],
) -> None:
    record = _base_record(
        purchase_intent="buy Wireless Mouse",
        cart_items=[{"name": "Wireless Mouse", "quantity": 1}],
    )
    assert _category_distance(record, taxonomy_artifacts) == 0.0


def test_category_hierarchy_distance_same_parent_small(
    taxonomy_artifacts: tuple[object, object],
) -> None:
    record = _base_record(
        purchase_intent="buy Wireless Mouse",
        cart_items=[{"name": "Mechanical Keyboard", "quantity": 1}],
    )
    distance = _category_distance(record, taxonomy_artifacts)
    assert 0.0 < distance < 1.0


def test_category_hierarchy_distance_different_top_level_large(
    taxonomy_artifacts: tuple[object, object],
) -> None:
    record = _base_record(
        purchase_intent="buy Green Tea",
        cart_items=[{"name": "Monitor Arm", "quantity": 1}],
    )
    distance = _category_distance(record, taxonomy_artifacts)
    assert distance == 1.0


def test_block_208_category_hierarchy_distance_large(
    taxonomy_artifacts: tuple[object, object],
) -> None:
    """Green Tea (Groceries) vs Power Bank (Electronics) — lexical overlap is 0."""
    record = _base_record(
        purchase_intent="order Green Tea",
        cart_items=[{"name": "Power Bank", "quantity": 1}],
    )
    distance = _category_distance(record, taxonomy_artifacts)
    assert distance == 1.0
