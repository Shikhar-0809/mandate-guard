"""Contract tests for mandate_guard.taxonomy."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mandate_guard.taxonomy import TAXONOMY_LEAVES


def test_no_duplicate_leaf_paths() -> None:
    assert len(TAXONOMY_LEAVES) == len(set(TAXONOMY_LEAVES))


def test_every_leaf_has_at_least_two_hierarchy_levels() -> None:
    for leaf in TAXONOMY_LEAVES:
        segments = [part.strip() for part in leaf.split(">")]
        assert len(segments) >= 2
        assert all(segments)


def test_at_least_four_distinct_top_level_categories() -> None:
    top_levels = {leaf.split(" > ", 1)[0] for leaf in TAXONOMY_LEAVES}
    assert len(top_levels) >= 4


def test_at_least_twenty_five_total_leaves() -> None:
    assert len(TAXONOMY_LEAVES) >= 25


def test_categories_are_reasonably_balanced() -> None:
    """Guards against a repeat of the 1-leaf-Home-Goods / 18-leaf-Electronics
    imbalance that this test would have caught originally."""
    from collections import Counter
    top_levels = [leaf.split(" > ", 1)[0] for leaf in TAXONOMY_LEAVES]
    counts = Counter(top_levels)
    assert len(counts) >= 10, f"expected >=10 top-level categories, got {len(counts)}"
    min_count = min(counts.values())
    max_count = max(counts.values())
    assert min_count >= 8, f"category {min(counts, key=counts.get)!r} has only {min_count} leaves"
    assert max_count <= 3 * min_count, (
        f"imbalance too large: max={max_count} min={min_count} "
        f"({dict(counts)})"
    )
