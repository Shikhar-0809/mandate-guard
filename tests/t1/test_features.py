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
    assert len(features) == len(FEATURE_NAMES) == 10


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


def test_brand_conflict() -> None:
    record = _base_record(
        purchase_intent="renew Zoom subscription",
        cart_items=[{"name": "Microsoft Teams", "quantity": 1}],
    )
    features = extract_features(record)
    index = FEATURE_NAMES.index("brand_conflict")
    assert features[index] == 1.0


def test_tfidf_cosine_sim_none() -> None:
    record = _base_record(purchase_intent="buy Zoom license")
    features = extract_features(record, tfidf_vectorizer=None)
    index = FEATURE_NAMES.index("tfidf_cosine_sim")
    assert features[index] == 0.0


def test_amount_to_cap_ratio() -> None:
    record = _base_record(
        amount_minor_units=10000,
        per_txn_cap_minor_units=10000,
    )
    features = extract_features(record)
    index = FEATURE_NAMES.index("amount_to_cap_ratio")
    assert features[index] == 1.0


def test_deterministic() -> None:
    record = _base_record()
    assert extract_features(record) == extract_features(record)
