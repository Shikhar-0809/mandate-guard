"""Normalize native 3-way semantic labels to binary ALLOW/BLOCK schema."""

from __future__ import annotations

import copy

_VALID_SEMANTIC_LABELS = frozenset({"ALLOW", "DEVIATION", "UNCERTAIN"})

_LABEL_MAP: dict[str, str] = {
    "ALLOW": "ALLOW",
    "DEVIATION": "BLOCK",
}


def normalize_semantic_labels_for_training(
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    """
    Normalize native 3-way semantic labels (ALLOW/DEVIATION/UNCERTAIN)
    to the project-wide binary schema (ALLOW/BLOCK) before records
    enter any shared pipeline (t1.train, compute_metrics, etc.).

    - ALLOW -> ALLOW
    - DEVIATION -> BLOCK
    - UNCERTAIN -> dropped entirely (not included in output)

    Input records are never mutated. Returns a new list of new dicts
    (deep-copy the label field's container, do not just reassign into
    the caller's dict objects).

    Raises ValueError if any record's "label" is not one of
    {"ALLOW", "DEVIATION", "UNCERTAIN"} — do not silently pass through
    or default an unrecognized label.
    """
    normalized: list[dict[str, object]] = []
    for record in records:
        label = record["label"]
        if label not in _VALID_SEMANTIC_LABELS:
            raise ValueError(f"unrecognized semantic label: {label!r}")
        if label == "UNCERTAIN":
            continue
        out = copy.deepcopy(record)
        out["label"] = _LABEL_MAP[str(label)]
        normalized.append(out)
    return normalized
