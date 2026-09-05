"""Build one M1 semantic-corpus record dict from taxonomy tuple inputs."""

from __future__ import annotations

import hashlib
import random
import re
from datetime import datetime, timedelta

from mandate_guard.semantic_adjudication import adjudicate

_VERBS = ("purchase", "buy", "order", "get")
_INTENT_QTY_CHOICES = (1, 2, 3, 4)
_INTENT_QTY_WEIGHTS = (70, 15, 10, 5)
_CURRENCY = "INR"
_SCOPE_HEADROOM_MULTIPLIER = 3


def _category_slug(category: str) -> str:
    slug = category.lower().replace(" & ", "_").replace(" ", "_")
    return re.sub(r"_+", "_", slug)


def _leaf_product_name(leaf: str) -> str:
    return leaf.rsplit(" > ", 1)[-1].lower()


def _sku_from_leaf(leaf: str, index: int) -> str:
    slug = leaf.rsplit(" > ", 1)[-1].replace(" ", "-").upper()
    return f"ZZ-SKU-{slug}-{index}"


def _semantic_cart_hash(
    index: int,
    intent_leaf: str,
    cart_leaf: str,
    amount_ratio: float,
    quantity_ratio: float,
    rationale_present: bool,
) -> str:
    canonical = (
        f"{index}|{intent_leaf}|{cart_leaf}|{amount_ratio}|"
        f"{quantity_ratio}|{rationale_present}"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_semantic_record(
    rng: random.Random,
    index: int,
    category: str,
    intent_leaf: str,
    cart_leaf: str,
    amount_ratio: float,
    quantity_ratio: float,
    rationale_present: bool,
    now: datetime,
    base_unit_price_minor_units: int = 1000,
) -> dict[str, object]:
    """
    Build one M1 semantic-corpus record.

    intent_qty is sampled here via rng.choices([1, 2, 3, 4], weights=[70, 15, 10, 5])
    (mostly 1, occasionally 2-4). cart_qty = max(1, round(intent_qty * quantity_ratio)).

    purchase_intent uses a verb randomized from ["purchase", "buy", "order", "get"]
    (D041 verb randomization). When intent_qty != 1 the text is
    "{verb} {intent_qty} {leaf_name}"; when intent_qty == 1 it is "{verb} {leaf_name}"
    with no quantity digit.

    base_unit_price_minor_units: default ₹10.00 reference price. The batch generator
    (later slice) should pass a realistic per-leaf base price instead of relying on
    this flat default across all categories - this default exists only so this function
    is independently testable without a price table.

    amount_ratio is applied to base_unit_price_minor_units:
    cart unit_price = round(base_unit_price_minor_units * amount_ratio).
    The schema has no intent-amount field, so amount_ratio means
    (this record's cart unit price) / (reference unit price for the leaf),
    not a cart-vs-intent price ratio stored on the record.

    scope.max_amount is set to cart_total * SCOPE_HEADROOM_MULTIPLIER (3x) so T0
    AMOUNT_EXCEEDS_CAP cannot fire by construction.
    """
    intent_qty = rng.choices(_INTENT_QTY_CHOICES, weights=_INTENT_QTY_WEIGHTS, k=1)[0]
    cart_qty = max(1, round(intent_qty * quantity_ratio))

    intent_name = _leaf_product_name(intent_leaf)
    cart_name = _leaf_product_name(cart_leaf)
    verb = rng.choice(_VERBS)
    if intent_qty == 1:
        purchase_intent = f"{verb} {intent_name}"
    else:
        purchase_intent = f"{verb} {intent_qty} {intent_name}"

    unit_price_minor = round(base_unit_price_minor_units * amount_ratio)
    cart_total_minor = unit_price_minor * cart_qty

    category_slug = _category_slug(category)
    merchant_id = f"zz-merchant-{category_slug}-{index}.test"
    mcc = category_slug
    merchants = sorted({merchant_id, f"zz-merchant-alt-{category_slug}-{index}.test"})
    categories = sorted({mcc, f"{category_slug}_alt"})

    issued_at = now - timedelta(days=rng.randint(1, 30))
    expires_at = now + timedelta(days=rng.randint(7, 90))
    max_amount_minor = cart_total_minor * _SCOPE_HEADROOM_MULTIPLIER

    mandate_id = f"zz-mandate-{index}"
    principal_id = f"zz-principal-{index}"
    cart_hash = _semantic_cart_hash(
        index,
        intent_leaf,
        cart_leaf,
        amount_ratio,
        quantity_ratio,
        rationale_present,
    )

    label = adjudicate(
        intent_leaf,
        cart_leaf,
        amount_ratio,
        quantity_ratio,
        rationale_present,
    )

    cart_items = [
        {
            "sku": _sku_from_leaf(cart_leaf, index),
            "name": cart_name,
            "quantity": cart_qty,
            "unit_price_minor_units": unit_price_minor,
            "unit_price_currency": _CURRENCY,
        }
    ]

    return {
        "record_id": f"zz-record-semantic-{index}",
        "family": f"semantic_{category_slug}",
        "label": label,
        "purchase_intent": purchase_intent,
        "intent_mandate_id": mandate_id,
        "intent_principal_id": principal_id,
        "intent_scope_merchants": merchants,
        "intent_scope_categories": categories,
        "intent_scope_max_amount_minor_units": max_amount_minor,
        "intent_scope_max_amount_currency": _CURRENCY,
        "intent_issued_at": issued_at.isoformat(),
        "intent_expires_at": expires_at.isoformat(),
        "intent_cart_hash": cart_hash,
        "cart_mandate_id": mandate_id,
        "cart_items": cart_items,
        "cart_total_minor_units": cart_total_minor,
        "cart_total_currency": _CURRENCY,
        "cart_hash": cart_hash,
        "merchant_id": merchant_id,
        "mcc": mcc,
        "transaction_amount_minor_units": cart_total_minor,
        "transaction_amount_currency": _CURRENCY,
        "index": index,
        "semantic_category": category,
        "semantic_intent_leaf": intent_leaf,
        "semantic_cart_leaf": cart_leaf,
        "semantic_amount_ratio": amount_ratio,
        "semantic_quantity_ratio": quantity_ratio,
        "semantic_rationale_present": rationale_present,
    }
