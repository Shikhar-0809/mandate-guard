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
