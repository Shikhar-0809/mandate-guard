"""Original hierarchical product taxonomy for category-semantic T1 features."""

from __future__ import annotations

from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]
from sklearn.metrics.pairwise import cosine_similarity  # type: ignore[import-untyped]

TAXONOMY_LEAVES: list[str] = [
    "Electronics > Computer Accessories > Wireless Mouse",
    "Electronics > Computer Accessories > USB-C Hub",
    "Electronics > Computer Accessories > Webcam",
    "Electronics > Computer Accessories > Mechanical Keyboard",
    "Electronics > Computer Accessories > Laptop Stand",
    "Electronics > Audio > Bluetooth Speaker",
    "Electronics > Audio > Wireless Earbuds",
    "Electronics > Audio > Speaker",
    "Electronics > Audio > Headphones",
    "Electronics > Mobile > Phone Charger",
    "Electronics > Mobile > Power Bank",
    "Electronics > Mobile > Tablet Stylus",
    "Electronics > Displays > Monitor Arm",
    "Electronics > Displays > Monitor",
    "Electronics > Cables > HDMI Cable",
    "Electronics > Storage > SD Card Reader",
    "Electronics > Storage > USB Flash Drive",
    "Electronics > Office > Desk Lamp",
    "Groceries > Pantry > Organic Pasta",
    "Groceries > Pantry > Rice Noodles",
    "Groceries > Pantry > Olive Oil",
    "Groceries > Pantry > Brown Rice",
    "Groceries > Pantry > Honey Jar",
    "Groceries > Snacks > Granola Bars",
    "Groceries > Snacks > Trail Mix",
    "Groceries > Snacks > Dried Fruit Mix",
    "Groceries > Beverages > Coffee Beans",
    "Groceries > Beverages > Herbal Tea",
    "Groceries > Beverages > Green Tea",
    "Groceries > Beverages > Sparkling Water",
    "Groceries > Beverages > Oat Milk",
    "Groceries > Spreads > Almond Butter",
    "Groceries > Spreads > Peanut Butter",
    "Home Goods > Organization > Storage Bin",
    "Apparel > Outerwear > Jacket",
    "Apparel > Footwear > Sneakers",
]


def build_taxonomy_vectorizer() -> TfidfVectorizer:
    vec = TfidfVectorizer(analyzer="word", ngram_range=(1, 1))
    vec.fit([leaf.replace(">", " ").lower() for leaf in TAXONOMY_LEAVES])
    return vec


def taxonomy_leaf_matrix(vec: TfidfVectorizer) -> Any:
    return vec.transform([leaf.replace(">", " ").lower() for leaf in TAXONOMY_LEAVES])


def best_matching_leaf_index(
    text: str,
    vec: TfidfVectorizer,
    leaf_matrix: Any,
) -> int:
    if not text.strip():
        return 0
    query = vec.transform([text.lower()])
    scores = cosine_similarity(query, leaf_matrix)[0]
    return int(scores.argmax())


def hierarchy_distance(leaf_index_a: int, leaf_index_b: int) -> float:
    path_a = TAXONOMY_LEAVES[leaf_index_a].split(" > ")
    path_b = TAXONOMY_LEAVES[leaf_index_b].split(" > ")
    shared = 0
    for segment_a, segment_b in zip(path_a, path_b, strict=False):
        if segment_a == segment_b:
            shared += 1
        else:
            break
    max_depth = max(len(path_a), len(path_b))
    if max_depth == 0:
        return 1.0
    return 1.0 - (shared / max_depth)
