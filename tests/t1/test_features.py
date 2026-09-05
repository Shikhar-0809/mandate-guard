"""Tests for mandate_guard.features."""

from __future__ import annotations

import math
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mandate_guard.features import FEATURE_NAMES, extract_features


def _base_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "purchase_intent": "",
        "cart_items": [{"name": "USB Cable", "quantity": 2}],
        "amount_minor_units": 1000,
        "per_txn_cap_minor_units": 10000,
    }
    record.update(overrides)
    return record


def test_feature_count() -> None:
    features = extract_features(_base_record())
    assert len(features) == len(FEATURE_NAMES) == 7


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
