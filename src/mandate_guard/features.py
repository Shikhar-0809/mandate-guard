"""Semantic feature extraction for T1.

Features operate in the intent-cart comparison space only.
Structural mandate features (amount caps, merchant scope, etc.) are T0's domain.
T0-derived features are excluded — see D011.
"""

from __future__ import annotations

import math
import re
from typing import Any

STOPWORDS = {
    "buy", "get", "order", "please", "the", "our", "team", "a", "an",
    "for", "to", "of", "and", "or", "in", "on", "with", "some", "new",
    "same", "last", "next", "this", "that", "from", "just", "need",
    "want", "renew", "renewal", "subscription", "upgrade", "purchase",
}

_INTENT_VERB_STOPWORDS = frozenset({"order", "buy", "purchase", "get"})

FEATURE_NAMES = [
    "jaccard_token_overlap",
    "char_trigram_overlap",
    "tfidf_cosine_sim",
    "intent_has_brand",
    "intent_specificity",
    "cart_category_match",
    "quantity_mismatch",
    "category_hierarchy_distance",
]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def _intent_text_for_overlap(intent: str) -> str:
    """Drop leading intent-verb template tokens before overlap features."""
    tokens = _tokenize(intent)
    while tokens and tokens[0] in _INTENT_VERB_STOPWORDS:
        tokens.pop(0)
    return " ".join(tokens)


def _trigrams(text: str) -> set[str]:
    t = text.lower()
    return {t[i : i + 3] for i in range(len(t) - 2)}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    u = a | b
    if not u:
        return 0.0
    return len(a & b) / len(u)


def _has_brand(text: str) -> float:
    tokens = re.findall(r"[A-Za-z0-9]+", text)
    for tok in tokens:
        if (
            tok[0].isupper()
            and len(tok) > 3
            and tok.lower() not in STOPWORDS
        ):
            return 1.0
    return 0.0


def _extract_first_int(text: str) -> int | None:
    m = re.search(r"\b(\d+)\b", text)
    return int(m.group(1)) if m else None


def extract_features(
    record: dict[str, Any],
    tfidf_vectorizer=None,
    taxonomy_vectorizer=None,
    taxonomy_leaf_matrix=None,
) -> list[float]:
    intent: str = str(record.get("purchase_intent") or "")
    cart_items: list = record.get("cart_items") or []
    cart_text: str = " ".join(
        str(item.get("name") or "") for item in cart_items
    )

    # 1. jaccard_token_overlap
    intent_overlap_text = _intent_text_for_overlap(intent)
    intent_tokens = set(_tokenize(intent_overlap_text))
    cart_tokens = set(_tokenize(cart_text))
    jaccard = _jaccard(intent_tokens, cart_tokens)

    # 2. char_trigram_overlap
    trigram_sim = _jaccard(
        _trigrams(intent_overlap_text),
        _trigrams(cart_text),
    )

    # 3. tfidf_cosine_sim
    if tfidf_vectorizer is not None and intent and cart_text:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            vecs = tfidf_vectorizer.transform([intent, cart_text])
            tfidf_sim = float(cosine_similarity(vecs[0], vecs[1])[0][0])
        except Exception:
            tfidf_sim = 0.0
    else:
        tfidf_sim = 0.0

    # 4. intent_has_brand
    intent_has_brand = _has_brand(intent)

    # 5. intent_specificity
    intent_words = _tokenize(intent)
    content_words = [w for w in intent_words if w not in STOPWORDS]
    intent_specificity = (
        len(content_words) / max(1, len(intent_words)) if intent_words else 0.0
    )

    # 6. cart_category_match
    first_content = next(
        (w for w in _tokenize(intent) if w not in STOPWORDS), None
    )
    cart_category_match = (
        1.0
        if first_content and first_content in _tokenize(cart_text)
        else 0.0
    )

    # 7. quantity_mismatch
    intent_qty = _extract_first_int(intent)
    cart_qty = None
    if cart_items:
        raw = cart_items[0].get("quantity")
        try:
            cart_qty = int(raw) if raw is not None else None
        except (ValueError, TypeError):
            cart_qty = None
    if intent_qty is not None and cart_qty is not None and cart_qty > 0:
        ratio = intent_qty / cart_qty
        quantity_mismatch = 1.0 if ratio > 2.0 or ratio < 0.5 else 0.0
    else:
        quantity_mismatch = 0.0

    # 8. category_hierarchy_distance
    if (
        taxonomy_vectorizer is not None
        and taxonomy_leaf_matrix is not None
        and (intent or cart_text)
    ):
        from .taxonomy import best_matching_leaf_index, hierarchy_distance

        intent_leaf = best_matching_leaf_index(
            intent_overlap_text or intent,
            taxonomy_vectorizer,
            taxonomy_leaf_matrix,
        )
        cart_leaf = best_matching_leaf_index(
            cart_text,
            taxonomy_vectorizer,
            taxonomy_leaf_matrix,
        )
        category_hierarchy_distance = hierarchy_distance(intent_leaf, cart_leaf)
    else:
        # Graceful degradation: models without taxonomy_vectorizer.joblib emit 0.0
        # (no signal) rather than failing at load or score time.
        category_hierarchy_distance = 0.0

    return [
        jaccard,
        trigram_sim,
        tfidf_sim,
        intent_has_brand,
        intent_specificity,
        cart_category_match,
        quantity_mismatch,
        category_hierarchy_distance,
    ]
