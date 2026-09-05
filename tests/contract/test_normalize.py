"""Contract tests for mandate_guard.normalize."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mandate_guard.normalize import normalize_semantic_labels_for_training

_MIXED_RECORDS: list[dict[str, object]] = [
    {"id": "a1", "label": "ALLOW", "nested": {"x": 1}},
    {"id": "a2", "label": "ALLOW", "nested": {"x": 2}},
    {"id": "d1", "label": "DEVIATION", "nested": {"y": 1}},
    {"id": "d2", "label": "DEVIATION", "nested": {"y": 2}},
    {"id": "u1", "label": "UNCERTAIN", "nested": {"z": 1}},
    {"id": "u2", "label": "UNCERTAIN", "nested": {"z": 2}},
]

_ALLOW_RECORDS: list[dict[str, object]] = [
    {"id": "allow-1", "label": "ALLOW"},
    {"id": "allow-2", "label": "ALLOW", "extra": "alpha"},
    {"id": "allow-3", "label": "ALLOW", "nested": {"k": "v"}},
]

_DEVIATION_RECORDS: list[dict[str, object]] = [
    {"id": "dev-1", "label": "DEVIATION"},
    {"id": "dev-2", "label": "DEVIATION", "score": 0.42},
    {"id": "dev-3", "label": "DEVIATION", "nested": {"flag": True}},
]


def test_output_labels_are_binary_allow_or_block_only() -> None:
    output = normalize_semantic_labels_for_training(_MIXED_RECORDS)
    assert output
    for record in output:
        assert record["label"] in {"ALLOW", "BLOCK"}
    assert "UNCERTAIN" not in {record["label"] for record in output}


@pytest.mark.parametrize(
    "record",
    _ALLOW_RECORDS,
    ids=[str(record["id"]) for record in _ALLOW_RECORDS],
)
def test_allow_maps_to_allow_deterministically(record: dict[str, object]) -> None:
    output = normalize_semantic_labels_for_training([record])
    assert len(output) == 1
    assert output[0]["label"] == "ALLOW"
    assert output[0]["id"] == record["id"]


@pytest.mark.parametrize(
    "record",
    _DEVIATION_RECORDS,
    ids=[str(record["id"]) for record in _DEVIATION_RECORDS],
)
def test_deviation_maps_to_block_deterministically(
    record: dict[str, object],
) -> None:
    output = normalize_semantic_labels_for_training([record])
    assert len(output) == 1
    assert output[0]["label"] == "BLOCK"
    assert output[0]["id"] == record["id"]


def test_uncertain_records_dropped_exactly() -> None:
    output = normalize_semantic_labels_for_training(_MIXED_RECORDS)
    uncertain_count = sum(
        1 for record in _MIXED_RECORDS if record["label"] == "UNCERTAIN"
    )
    assert len(_MIXED_RECORDS) - len(output) == uncertain_count
    assert uncertain_count == 2
    assert len(output) == len(_MIXED_RECORDS) - uncertain_count


def test_input_records_are_not_mutated() -> None:
    records: list[dict[str, object]] = [
        {"id": "a1", "label": "ALLOW", "nested": {"x": [1, 2]}},
        {"id": "d1", "label": "DEVIATION", "nested": {"y": [3, 4]}},
        {"id": "u1", "label": "UNCERTAIN", "nested": {"z": [5, 6]}},
    ]
    before = copy.deepcopy(records)
    normalize_semantic_labels_for_training(records)
    assert records == before


def test_unrecognized_label_raises_value_error() -> None:
    records: list[dict[str, object]] = [{"id": "bad-1", "label": "MAYBE"}]
    with pytest.raises(ValueError, match="unrecognized semantic label"):
        normalize_semantic_labels_for_training(records)
