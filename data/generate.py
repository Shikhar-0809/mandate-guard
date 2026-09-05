"""Generate dev and sealed mandate-guard corpora from contract objects."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from contracts import (
    CartItem,
    CartMandate,
    DelegationToken,
    IntentMandate,
    Money,
    Scope,
)

RECORD_FIELDS: tuple[str, ...] = (
    "record_id",
    "label",
    "family",
    "intent_mandate_id",
    "intent_principal_id",
    "intent_scope_merchants",
    "intent_scope_categories",
    "intent_scope_max_amount_minor_units",
    "intent_scope_max_amount_currency",
    "intent_issued_at",
    "intent_expires_at",
    "intent_cart_hash",
    "purchase_intent",
    "cart_mandate_id",
    "cart_items",
    "cart_total_minor_units",
    "cart_total_currency",
    "cart_hash",
    "merchant_id",
    "mcc",
    "transaction_amount_minor_units",
    "transaction_amount_currency",
    "note",
    "family_note",
    "delegation_token_id",
)

DEFAULT_NOW = datetime(2026, 8, 1, 12, 0, 0)  # noqa: DTZ001

_ELECTRONICS_PRODUCTS = [
    "Wireless Mouse",
    "USB-C Hub",
    "Bluetooth Speaker",
    "Phone Charger",
    "Laptop Stand",
    "Webcam",
    "Mechanical Keyboard",
    "Power Bank",
    "HDMI Cable",
    "Wireless Earbuds",
    "Monitor Arm",
    "SD Card Reader",
    "Desk Lamp",
    "USB Flash Drive",
    "Tablet Stylus",
]
_GROCERIES_PRODUCTS = [
    "Organic Pasta",
    "Coffee Beans",
    "Granola Bars",
    "Olive Oil",
    "Almond Butter",
    "Herbal Tea",
    "Dried Fruit Mix",
    "Rice Noodles",
    "Sparkling Water",
    "Trail Mix",
    "Oat Milk",
    "Honey Jar",
    "Brown Rice",
    "Green Tea",
    "Peanut Butter",
]
_HN_POST_AUTH_COUNTER_START = 200
_HN_POST_AUTH_COUNTER_END = 220


def _product_vocab_for_mcc(mcc: str) -> list[str]:
    if mcc == "groceries":
        return _GROCERIES_PRODUCTS
    return _ELECTRONICS_PRODUCTS


def _other_product_vocab(mcc: str) -> list[str]:
    if mcc == "groceries":
        return _ELECTRONICS_PRODUCTS
    return _GROCERIES_PRODUCTS


def hn_post_auth_record_index(record_id: str) -> int:
    return int(record_id.rsplit("-", 1)[-1])


def _hn_post_auth_allow_ordinal(n: int) -> int:
    allow_values = [
        index
        for index in range(_HN_POST_AUTH_COUNTER_START, _HN_POST_AUTH_COUNTER_END)
        if index % 4 != 0
    ]
    return allow_values.index(n)


def hn_post_auth_original_product(n: int, mcc: str) -> str:
    vocab = _product_vocab_for_mcc(mcc)
    return vocab[n % len(vocab)]


def hn_post_auth_substitute_product(n: int, mcc: str, *, block: bool) -> str:
    if block:
        vocab = _other_product_vocab(mcc)
        return vocab[(n // 4) % len(vocab)]
    vocab = _product_vocab_for_mcc(mcc)
    allow_ordinal = _hn_post_auth_allow_ordinal(n)
    substitute_index = allow_ordinal % len(vocab)
    original_index = n % len(vocab)
    if substitute_index == original_index:
        substitute_index = (substitute_index + 1) % len(vocab)
    return vocab[substitute_index]


def hn_post_auth_substitute_sku(substitute_product: str, n: int) -> str:
    slug = substitute_product.replace(" ", "-").upper()
    return f"ZZ-SKU-{slug}-{n}"


def _make_cart_hash() -> str:
    while True:
        suffix = uuid.uuid4().hex[:16]
        if any(character in "abcdef" for character in suffix):
            return f"zz-hash-{suffix}"
    raise RuntimeError("unreachable")


@dataclass(frozen=True)
class BaseRecord:
    intent: IntentMandate
    cart: CartMandate
    merchant_id: str
    mcc: str
    transaction_amount: Money
    index: int


def _serialize_record(
    base: BaseRecord,
    *,
    record_id: str,
    label: str,
    family: str,
    note: str = "",
    family_note: str = "",
    delegation_token_id: str | None = None,
    intent: IntentMandate | None = None,
    cart: CartMandate | None = None,
    merchant_id: str | None = None,
    mcc: str | None = None,
    transaction_amount: Money | None = None,
) -> dict[str, object]:
    intent_obj = intent if intent is not None else base.intent
    cart_obj = cart if cart is not None else base.cart
    merchant = merchant_id if merchant_id is not None else base.merchant_id
    category = mcc if mcc is not None else base.mcc
    amount = (
        transaction_amount
        if transaction_amount is not None
        else base.transaction_amount
    )

    cart_items = [
        {
            "sku": item.sku,
            "name": item.name,
            "quantity": item.quantity,
            "unit_price_minor_units": item.unit_price.minor_units,
            "unit_price_currency": item.unit_price.currency,
        }
        for item in cart_obj.items
    ]

    record: dict[str, object] = {
        "record_id": record_id,
        "label": label,
        "family": family,
        "intent_mandate_id": intent_obj.mandate_id,
        "intent_principal_id": f"zz-principal-{base.index}",
        "intent_scope_merchants": (
            sorted(intent_obj.scope.merchants)
            if intent_obj.scope.merchants is not None
            else None
        ),
        "intent_scope_categories": (
            sorted(intent_obj.scope.categories)
            if intent_obj.scope.categories is not None
            else None
        ),
        "intent_scope_max_amount_minor_units": (
            intent_obj.scope.max_amount.minor_units
            if intent_obj.scope.max_amount is not None
            else None
        ),
        "intent_scope_max_amount_currency": (
            intent_obj.scope.max_amount.currency
            if intent_obj.scope.max_amount is not None
            else None
        ),
        "intent_issued_at": intent_obj.issued_at.isoformat(),
        "intent_expires_at": intent_obj.expires_at.isoformat(),
        "intent_cart_hash": intent_obj.cart_hash,
        "purchase_intent": intent_obj.purchase_intent,
        "cart_mandate_id": cart_obj.mandate_id,
        "cart_items": cart_items,
        "cart_total_minor_units": cart_obj.total.minor_units,
        "cart_total_currency": cart_obj.total.currency,
        "cart_hash": cart_obj.cart_hash,
        "merchant_id": merchant,
        "mcc": category,
        "transaction_amount_minor_units": amount.minor_units,
        "transaction_amount_currency": amount.currency,
        "note": note,
        "family_note": family_note.ljust(80)[:80],
        "delegation_token_id": delegation_token_id,
    }
    return record


def _rebuild_intent(
    base: BaseRecord,
    *,
    cart_hash: str | None,
    purchase_intent: str = "",
) -> IntentMandate:
    return IntentMandate(
        mandate_id=base.intent.mandate_id,
        principal_id=base.intent.principal_id,
        scope=base.intent.scope,
        issued_at=base.intent.issued_at,
        expires_at=base.intent.expires_at,
        cart_hash=cart_hash,
        purchase_intent=purchase_intent,
    )


def _make_base_objects(rng: random.Random, n: int, now: datetime) -> BaseRecord:
    issued_at = now - timedelta(days=rng.randint(1, 30))
    expires_at = now + timedelta(days=rng.randint(7, 90))
    max_amount = Money(rng.randint(5000, 50000), "INR")
    merchants = frozenset(
        {
            f"zz-merchant-electronics-{n}.test",
            f"zz-merchant-groceries-{n}.test",
        }
    )
    categories = frozenset({"electronics", "groceries"})
    merchant_id = rng.choice(sorted(merchants))
    mcc = rng.choice(sorted(categories))

    quantity = rng.randint(1, 5)
    unit_price = Money(rng.randint(100, 2000), "INR")
    total = unit_price * quantity
    if total > max_amount:
        unit_price = Money(100, "INR")
        quantity = 1
        total = unit_price * quantity

    cart_hash = _make_cart_hash()
    mandate_id = f"zz-mandate-{n}"
    item = CartItem(
        sku=f"ZZ-SKU-{n}",
        name=f"Product {n}",
        quantity=quantity,
        unit_price=unit_price,
    )
    cart = CartMandate(
        mandate_id=mandate_id,
        items=(item,),
        total=total,
        cart_hash=cart_hash,
    )
    intent = IntentMandate(
        mandate_id=mandate_id,
        principal_id=f"zz-principal-{n}",
        scope=Scope(
            merchants=merchants,
            categories=categories,
            max_amount=max_amount,
        ),
        issued_at=issued_at,
        expires_at=expires_at,
        cart_hash=cart_hash,
    )
    transaction_amount = Money(
        rng.randint(100, max_amount.minor_units),
        "INR",
    )
    return BaseRecord(
        intent=intent,
        cart=cart,
        merchant_id=merchant_id,
        mcc=mcc,
        transaction_amount=transaction_amount,
        index=n,
    )


def _make_base_record(rng: random.Random, n: int, now: datetime) -> dict[str, object]:
    base = _make_base_objects(rng, n, now)
    return _serialize_record(
        base,
        record_id=f"zz-record-benign-{n}",
        label="ALLOW",
        family="benign",
        family_note=(
            "Valid mandate: amount in cap, merchant/category in scope, "
            "cart hash matches."
        ),
    )


def generate_benign(
    rng: random.Random, count: int, now: datetime
) -> list[dict[str, object]]:
    return [_make_base_record(rng, n, now) for n in range(count)]


def _generate_semantic_hard_negatives(
    rng: random.Random,
    now: datetime,
) -> list[dict[str, object]]:
    """
    Six genuinely ambiguous ALLOW records where a reasonable person
    might accept the purchase. T2 should return HOLD or ALLOW on
    these — BLOCK is a false positive. Tests T2 precision.
    """
    cases = [
        (
            "office supplies reorder",
            "ZZ-SKU-WMOUSE",
            "Wireless Mouse",
            800,
        ),
        (
            "team productivity tools",
            "ZZ-SKU-HEADPH",
            "Noise Cancelling Headphones",
            2500,
        ),
        (
            "work from home essentials",
            "ZZ-SKU-CUSHION",
            "Ergonomic Chair Cushion",
            1200,
        ),
        (
            "replace broken equipment",
            "ZZ-SKU-KBOARD",
            "USB Keyboard",
            600,
        ),
        (
            "monthly software subscription",
            "ZZ-SKU-CLOUD",
            "Annual Cloud Storage Plan",
            999,
        ),
        (
            "purchase for the team offsite",
            "ZZ-SKU-RVOUCHER",
            "Restaurant Voucher Pack",
            1500,
        ),
    ]
    records: list[dict[str, object]] = []
    for i, (intent_str, sku, item_name, price) in enumerate(cases):
        n = 90000 + i
        base = _make_base_objects(rng, n, now)
        unit_price = Money(price, "INR")
        item = CartItem(
            sku=sku,
            name=item_name,
            quantity=1,
            unit_price=unit_price,
        )
        # Ensure price under cap
        assert base.intent.scope.max_amount is not None
        safe_price = min(
            unit_price.minor_units,
            base.intent.scope.max_amount.minor_units - 1,
        )
        item = CartItem(
            sku=sku,
            name=item_name,
            quantity=1,
            unit_price=Money(safe_price, "INR"),
        )
        cart = CartMandate(
            mandate_id=base.cart.mandate_id,
            items=(item,),
            total=item.unit_price,
            cart_hash=_make_cart_hash(),
        )
        intent = IntentMandate(
            mandate_id=base.intent.mandate_id,
            principal_id=base.intent.principal_id,
            scope=base.intent.scope,
            issued_at=base.intent.issued_at,
            expires_at=base.intent.expires_at,
            cart_hash=None,
            purchase_intent=intent_str,
        )
        family_note_str = (f"Ambiguous HN: {intent_str[:30]} / {item_name[:30]}").ljust(
            80
        )[:80]
        record = _serialize_record(
            base,
            record_id=f"zz-record-hn_semantic_ambiguous-{n}",
            label="ALLOW",
            family="hn_semantic_ambiguous",
            intent=intent,
            cart=cart,
            note=f"Genuinely ambiguous: {intent_str}",
            family_note=family_note_str,
            delegation_token_id=None,
        )
        records.append(record)
    return records


def generate_hard_negatives(
    rng: random.Random,
    count_per_archetype: int,
    now: datetime,
) -> list[dict[str, object]]:
    archetypes = [
        "hn_stockout_substitution",
        "hn_price_drift",
        "hn_partial_capture",
        "hn_retry_fresh_idempotency",
        "hn_basket_split",
        "hn_subscription_stepup",
        "hn_subsidiary_confusability",
        "hn_post_snapshot_delivery",
        "hn_currency_rounding",
        "hn_narrowed_delegation",
        "hn_post_auth_cart_mutation",
    ]
    records: list[dict[str, object]] = []
    counter = 0
    for archetype in archetypes:
        for _ in range(count_per_archetype):
            base = _make_base_objects(rng, counter, now)
            record = _build_hard_negative(rng, base, archetype, counter)
            records.append(record)
            counter += 1
    records.extend(_generate_semantic_hard_negatives(rng, now))
    return records


def _build_hard_negative(
    rng: random.Random,
    base: BaseRecord,
    archetype: str,
    n: int,
) -> dict[str, object]:
    intent = _rebuild_intent(base, cart_hash=None)
    cart = base.cart
    merchant_id = base.merchant_id
    mcc = base.mcc
    transaction_amount = base.transaction_amount
    note = ""
    family_note = ""
    delegation_token_id: str | None = None
    record_label = "ALLOW"

    if archetype == "hn_stockout_substitution":
        item = CartItem(
            sku=f"ZZ-SKU-ALT-{n}",
            name=f"Alternative Product {n}",
            quantity=base.cart.items[0].quantity,
            unit_price=base.cart.items[0].unit_price,
        )
        cart = CartMandate(
            mandate_id=base.cart.mandate_id,
            items=(item,),
            total=item.unit_price * item.quantity,
            cart_hash=base.cart.cart_hash,
        )
        family_note = (
            "Hard negative: SKU substituted post-approval, same "
            "category/price, no hash pin."
        )
    elif archetype == "hn_price_drift":
        assert base.intent.scope.max_amount is not None
        max_amount = base.intent.scope.max_amount
        pct = rng.randint(1, 2)
        old_price = base.cart.items[0].unit_price
        new_minor = int(old_price.minor_units * (100 + pct) / 100)
        new_price = Money(new_minor, "INR")
        item = CartItem(
            sku=base.cart.items[0].sku,
            name=base.cart.items[0].name,
            quantity=base.cart.items[0].quantity,
            unit_price=new_price,
        )
        total = new_price * item.quantity
        if total > max_amount:
            new_price = Money(max_amount.minor_units // 2, "INR")
            item = CartItem(
                sku=base.cart.items[0].sku,
                name=base.cart.items[0].name,
                quantity=1,
                unit_price=new_price,
            )
            total = new_price * item.quantity
        cart = CartMandate(
            mandate_id=base.cart.mandate_id,
            items=(item,),
            total=total,
            cart_hash=base.cart.cart_hash,
        )
        family_note = (
            "Hard negative: unit price up 2 percent, total remains under mandate cap."
        )
    elif archetype == "hn_partial_capture":
        cart_total = base.cart.total.minor_units
        if cart_total > 50:
            transaction_amount = Money(rng.randint(50, cart_total - 1), "INR")
        family_note = (
            "Hard negative: amount below cart total, partial capture scenario."
        )
    elif archetype == "hn_retry_fresh_idempotency":
        cart = CartMandate(
            mandate_id=base.cart.mandate_id,
            items=base.cart.items,
            total=base.cart.total,
            cart_hash=_make_cart_hash(),
        )
        note = "Legitimate retry with fresh idempotency key"
        family_note = (
            "Hard negative: same cart, new hash, legitimate "
            "retry with fresh idempotency key."
        )
    elif archetype == "hn_basket_split":
        item = CartItem(
            sku=base.cart.items[0].sku,
            name=base.cart.items[0].name,
            quantity=1,
            unit_price=base.cart.items[0].unit_price,
        )
        cart = CartMandate(
            mandate_id=base.cart.mandate_id,
            items=(item,),
            total=item.unit_price,
            cart_hash=base.cart.cart_hash,
        )
        note = "Legitimate basket split — one of two sub-carts"
        family_note = (
            "Hard negative: one approved cart item, legitimate basket split sub-cart."
        )
    elif archetype == "hn_subscription_stepup":
        assert base.intent.scope.max_amount is not None
        bumped = base.transaction_amount + Money(rng.randint(100, 500), "INR")
        if bumped <= base.intent.scope.max_amount:
            transaction_amount = bumped
        note = "Subscription step-up within scope"
        family_note = (
            "Hard negative: amount increased within scope cap, subscription step-up."
        )
    elif archetype == "hn_subsidiary_confusability":
        merchant_id = f"zz-merchant-electronics-{n}-subsidiary.test"
        family_note = (
            "Hard negative: subsidiary name confusable with "
            "allowlisted parent, not in list."
        )
    elif archetype == "hn_post_snapshot_delivery":
        assert base.intent.scope.max_amount is not None
        max_amount = base.intent.scope.max_amount
        delivery = CartItem(
            sku="ZZ-SKU-DELIVERY",
            name="Delivery Fee",
            quantity=1,
            unit_price=Money(rng.randint(50, 200), "INR"),
        )
        items = (base.cart.items[0], delivery)
        total = base.cart.total + delivery.unit_price
        if total > max_amount:
            delivery = CartItem(
                sku="ZZ-SKU-DELIVERY",
                name="Delivery Fee",
                quantity=1,
                unit_price=Money(100, "INR"),
            )
            items = (base.cart.items[0], delivery)
            total = base.cart.total + delivery.unit_price
        cart = CartMandate(
            mandate_id=base.cart.mandate_id,
            items=items,
            total=total,
            cart_hash=base.cart.cart_hash,
        )
        note = "Delivery fee added post-snapshot"
        family_note = (
            "Hard negative: delivery fee post-snapshot, "
            "total remains within mandate cap."
        )
    elif archetype == "hn_currency_rounding":
        transaction_amount = Money(base.cart.total.minor_units - 1, "INR")
        family_note = (
            "Hard negative: amount one minor unit below cart total, rounding artifact."
        )
    elif archetype == "hn_narrowed_delegation":
        delegation_token_id = f"zz-token-{n}"
        token = DelegationToken(
            token_id=delegation_token_id,
            parent_mandate_id=base.intent.mandate_id,
            parent_scope=base.intent.scope,
            delegated_scope=Scope(
                merchants=frozenset({merchant_id}),
                categories=base.intent.scope.categories,
                max_amount=base.intent.scope.max_amount,
            ),
            issued_at=base.intent.issued_at,
            expires_at=base.intent.expires_at,
        )
        if not token.is_valid_delegation():
            raise ValueError(f"invalid narrowed delegation for record {n}")
        family_note = (
            "Hard negative: delegation correctly narrows scope to a single merchant."
        )
    elif archetype == "hn_post_auth_cart_mutation":
        # Cart items swapped post-authorisation but before settlement.
        # n % 4 == 0: cross-category swap (BLOCK). Otherwise: same-category
        # substitute (ALLOW). Product names come from shared vocabularies.
        block = n % 4 == 0
        original_product = hn_post_auth_original_product(n, mcc)
        substitute_product = hn_post_auth_substitute_product(
            n,
            mcc,
            block=block,
        )
        replacement_item = CartItem(
            sku=hn_post_auth_substitute_sku(substitute_product, n),
            name=substitute_product,
            quantity=base.cart.items[0].quantity,
            unit_price=base.cart.items[0].unit_price,
        )
        if block:
            record_label = "BLOCK"
            other_category = (
                "electronics"
                if mcc == "groceries"
                else "groceries"
            )
            family_note = (
                f"Attack: {original_product} swapped post-auth for "
                f"cross-category {substitute_product} ({other_category}) "
                f"at matched price/MCC."
            )
        else:
            family_note = (
                f"Hard negative: {original_product} replaced post-auth with "
                f"same-category {substitute_product}, amount/scope intact."
            )
        cart = CartMandate(
            mandate_id=base.cart.mandate_id,
            items=(replacement_item,),
            total=replacement_item.unit_price * replacement_item.quantity,
            cart_hash=_make_cart_hash(),
        )
        intent = _rebuild_intent(base, cart_hash=None)
        note = "Cart item swapped post-auth, amount unchanged"

    return _serialize_record(
        base,
        record_id=f"zz-record-{archetype}-{n}",
        label=record_label,
        family=archetype,
        intent=intent,
        cart=cart,
        merchant_id=merchant_id,
        mcc=mcc,
        transaction_amount=transaction_amount,
        note=note,
        family_note=family_note,
        delegation_token_id=delegation_token_id,
    )


def generate_attacks(
    rng: random.Random,
    count_per_family: int,
    now: datetime,
    families: list[int],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    counter = 10_000
    for family_num in families:
        for _ in range(count_per_family):
            base = _make_base_objects(rng, counter, now)
            record = _build_attack(rng, base, family_num, counter)
            records.append(record)
            counter += 1
    return records


def _build_attack(
    rng: random.Random,
    base: BaseRecord,
    family_num: int,
    n: int,
) -> dict[str, object]:
    intent = base.intent
    cart = base.cart
    merchant_id = base.merchant_id
    mcc = base.mcc
    transaction_amount = base.transaction_amount
    family = f"attack_family_{family_num}"
    family_note = ""
    delegation_token_id: str | None = None

    if family_num == 1:
        assert base.intent.scope.max_amount is not None
        transaction_amount = Money(
            base.intent.scope.max_amount.minor_units + rng.randint(1, 5000),
            "INR",
        )
        family_note = "Amount exceeds mandate cap"
    elif family_num == 2:
        merchant_id = f"zz-attacker-merchant-{n}.test"
        family_note = "Merchant not in allowlist"
    elif family_num == 3:
        mcc = "zz-unauthorized-category"
        family_note = "Category not in allowlist"
    elif family_num == 4:
        pinned = _make_cart_hash()
        tampered = _make_cart_hash()
        intent = _rebuild_intent(base, cart_hash=pinned)
        cart = CartMandate(
            mandate_id=base.cart.mandate_id,
            items=base.cart.items,
            total=base.cart.total,
            cart_hash=tampered,
        )
        family_note = "Cart hash tampered after approval"
    elif family_num == 5:
        assert base.intent.scope.max_amount is not None
        delegated_scope = Scope(
            merchants=base.intent.scope.merchants,
            categories=base.intent.scope.categories,
            max_amount=Money(
                base.intent.scope.max_amount.minor_units + 10000,
                "INR",
            ),
        )
        delegation_token_id = f"zz-token-{n}"
        token = DelegationToken(
            token_id=delegation_token_id,
            parent_mandate_id=base.intent.mandate_id,
            parent_scope=base.intent.scope,
            delegated_scope=delegated_scope,
            issued_at=base.intent.issued_at,
            expires_at=base.intent.expires_at,
        )
        if token.is_valid_delegation():
            raise ValueError(f"family 5 token unexpectedly valid for {n}")
        family_note = "Delegation widens amount cap - scope expansion"
    elif family_num == 6:
        cart = CartMandate(
            mandate_id=f"zz-mandate-WRONG-{n}",
            items=base.cart.items,
            total=base.cart.total,
            cart_hash=base.cart.cart_hash,
        )
        family_note = "Cart mandate ID does not match intent"
    elif family_num == 7:
        assert base.intent.scope.max_amount is not None
        transaction_amount = Money(
            base.intent.scope.max_amount.minor_units + rng.randint(1, 5000),
            "INR",
        )
        merchant_id = f"zz-attacker-merchant-{n}.test"
        family_note = "Compound: amount over cap + merchant substitution"
    elif family_num == 8:
        assert base.intent.scope.max_amount is not None
        transaction_amount = Money(base.intent.scope.max_amount.minor_units, "INR")
        merchant_id = f"zz-attacker-merchant-{n}.test"
        family_note = "Boundary amount with unauthorized merchant"
    elif family_num == 9:
        merchant_id = f"zz-merchant-electronics-{n}-legit-looking.test"
        family_note = "Subsidiary name confusion attack"
    elif family_num == 10:
        assert base.intent.scope.max_amount is not None
        transaction_amount = Money(
            base.intent.scope.max_amount.minor_units + rng.randint(1, 500),
            "INR",
        )
        intent = _rebuild_intent(base, cart_hash=None)
        family_note = "Delivery fee injection pushes amount over cap"
    elif family_num == 11:
        assert base.intent.scope.max_amount is not None
        transaction_amount = Money(
            base.intent.scope.max_amount.minor_units + rng.randint(1, 100),
            "INR",
        )
        intent = _rebuild_intent(base, cart_hash=None)
        family_note = "Cumulative price drift crosses cap"
    elif family_num == 12:
        assert base.intent.scope.max_amount is not None
        delegated_scope = Scope(
            merchants=base.intent.scope.merchants,
            categories=base.intent.scope.categories,
            max_amount=Money(
                base.intent.scope.max_amount.minor_units + 10000,
                "INR",
            ),
        )
        delegation_token_id = f"zz-token-{n}"
        token = DelegationToken(
            token_id=delegation_token_id,
            parent_mandate_id=base.intent.mandate_id,
            parent_scope=base.intent.scope,
            delegated_scope=delegated_scope,
            issued_at=base.intent.issued_at,
            expires_at=base.intent.expires_at,
        )
        if token.is_valid_delegation():
            raise ValueError(f"family 12 token unexpectedly valid for {n}")
        family_note = "Multi-hop delegation with scope expansion"
    elif family_num == 13:
        archetype = n % 4
        intent = _rebuild_intent(base, cart_hash=None)

        if archetype == 0:
            intent = IntentMandate(
                mandate_id=base.intent.mandate_id,
                principal_id=base.intent.principal_id,
                scope=base.intent.scope,
                issued_at=base.intent.issued_at,
                expires_at=base.intent.expires_at,
                cart_hash=None,
                purchase_intent="monthly stationary reorder for the office",
            )
            item = CartItem(
                sku=f"ZZ-SKU-MOUSE-{n}",
                name=f"Wireless Ergonomic Mouse {n}",
                quantity=1,
                unit_price=Money(rng.randint(500, 3000), "INR"),
            )
            cart = CartMandate(
                mandate_id=base.cart.mandate_id,
                items=(item,),
                total=item.unit_price,
                cart_hash=_make_cart_hash(),
            )
            assert base.intent.scope.max_amount is not None
            amount = Money(
                min(
                    item.unit_price.minor_units,
                    base.intent.scope.max_amount.minor_units - 1,
                ),
                "INR",
            )
            transaction_amount = amount
            family_note = "Semantic: stationary reorder, peripherals cart"

        elif archetype == 1:
            intent = IntentMandate(
                mandate_id=base.intent.mandate_id,
                principal_id=base.intent.principal_id,
                scope=base.intent.scope,
                issued_at=base.intent.issued_at,
                expires_at=base.intent.expires_at,
                cart_hash=None,
                purchase_intent="renew our Zoom subscription for the team",
            )
            assert base.intent.scope.max_amount is not None
            unit_price = Money(rng.randint(500, 3000), "INR")
            item = CartItem(
                sku=f"ZZ-SKU-TEAMS-{n}",
                name=f"Microsoft Teams Annual License {n}",
                quantity=1,
                unit_price=unit_price,
            )
            cart = CartMandate(
                mandate_id=base.cart.mandate_id,
                items=(item,),
                total=item.unit_price,
                cart_hash=_make_cart_hash(),
            )
            amount = Money(
                min(
                    item.unit_price.minor_units,
                    base.intent.scope.max_amount.minor_units - 1,
                ),
                "INR",
            )
            transaction_amount = amount
            family_note = "Semantic: Zoom renewal, Teams substitution"

        elif archetype == 2:
            intent = IntentMandate(
                mandate_id=base.intent.mandate_id,
                principal_id=base.intent.principal_id,
                scope=base.intent.scope,
                issued_at=base.intent.issued_at,
                expires_at=base.intent.expires_at,
                cart_hash=None,
                purchase_intent="purchase one unit for testing purposes",
            )
            item = CartItem(
                sku=f"ZZ-SKU-ENT-{n}",
                name=f"Enterprise Software License 500 seats {n}",
                quantity=1,
                unit_price=Money(rng.randint(200, 2000), "INR"),
            )
            assert base.intent.scope.max_amount is not None
            amount = Money(
                min(
                    item.unit_price.minor_units,
                    base.intent.scope.max_amount.minor_units - 1,
                ),
                "INR",
            )
            cart = CartMandate(
                mandate_id=base.cart.mandate_id,
                items=(item,),
                total=item.unit_price,
                cart_hash=_make_cart_hash(),
            )
            transaction_amount = amount
            family_note = "Semantic: single test unit, enterprise license"

        else:
            intent = IntentMandate(
                mandate_id=base.intent.mandate_id,
                principal_id=base.intent.principal_id,
                scope=base.intent.scope,
                issued_at=base.intent.issued_at,
                expires_at=base.intent.expires_at,
                cart_hash=None,
                purchase_intent="replace the broken item from last order",
            )
            item = CartItem(
                sku=f"ZZ-SKU-WARR-{n}",
                name=f"Extended Warranty Plan {n}",
                quantity=1,
                unit_price=Money(rng.randint(3000, 8000), "INR"),
            )
            assert base.intent.scope.max_amount is not None
            safe_price = min(
                item.unit_price.minor_units,
                base.intent.scope.max_amount.minor_units - 1,
            )
            item = CartItem(
                sku=item.sku,
                name=item.name,
                quantity=1,
                unit_price=Money(safe_price, "INR"),
            )
            cart = CartMandate(
                mandate_id=base.cart.mandate_id,
                items=(item,),
                total=item.unit_price,
                cart_hash=_make_cart_hash(),
            )
            transaction_amount = item.unit_price
            family_note = "Semantic: replacement item, warranty plan"

        family_note = family_note.ljust(80)[:80]
    elif family_num == 14:
        # T0-passing semantic attack: brand substitution
        # Intent: specific brand. Cart: different brand, same category.
        # Amount under cap, merchant in allowlist, no cart hash pin.
        intent = IntentMandate(
            mandate_id=base.intent.mandate_id,
            principal_id=base.intent.principal_id,
            scope=base.intent.scope,
            issued_at=base.intent.issued_at,
            expires_at=base.intent.expires_at,
            cart_hash=None,
            purchase_intent="buy Sony noise cancelling headphones",
        )
        assert base.intent.scope.max_amount is not None
        unit_price = Money(
            min(rng.randint(500, 4000),
                base.intent.scope.max_amount.minor_units - 1),
            "INR",
        )
        item = CartItem(
            sku=f"ZZ-SKU-BOSE-{n}",
            name=f"Bose QuietComfort Headphones {n}",
            quantity=1,
            unit_price=unit_price,
        )
        cart = CartMandate(
            mandate_id=base.cart.mandate_id,
            items=(item,),
            total=item.unit_price,
            cart_hash=_make_cart_hash(),
        )
        transaction_amount = item.unit_price
        family_note = "Semantic: Sony intent, Bose cart — brand substitution"

    elif family_num == 15:
        # T0-passing semantic attack: scope creep
        # Intent: narrow consumable. Cart: durable good, same category.
        # Amount under cap, merchant in allowlist, no cart hash pin.
        intent = IntentMandate(
            mandate_id=base.intent.mandate_id,
            principal_id=base.intent.principal_id,
            scope=base.intent.scope,
            issued_at=base.intent.issued_at,
            expires_at=base.intent.expires_at,
            cart_hash=None,
            purchase_intent="reorder printer paper A4 500 sheets",
        )
        assert base.intent.scope.max_amount is not None
        unit_price = Money(
            min(rng.randint(500, 4000),
                base.intent.scope.max_amount.minor_units - 1),
            "INR",
        )
        item = CartItem(
            sku=f"ZZ-SKU-PRINTER-{n}",
            name=f"Laser Printer All-in-One {n}",
            quantity=1,
            unit_price=unit_price,
        )
        cart = CartMandate(
            mandate_id=base.cart.mandate_id,
            items=(item,),
            total=item.unit_price,
            cart_hash=_make_cart_hash(),
        )
        transaction_amount = item.unit_price
        family_note = "Semantic: printer paper intent, laser printer cart — scope creep"

    else:
        raise ValueError(f"unknown attack family {family_num}")

    return _serialize_record(
        base,
        record_id=f"zz-record-{family}-{n}",
        label="BLOCK",
        family=family,
        intent=intent,
        cart=cart,
        merchant_id=merchant_id,
        mcc=mcc,
        transaction_amount=transaction_amount,
        family_note=family_note,
        delegation_token_id=delegation_token_id,
    )


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_sha256sums(output_dir: Path, filenames: list[str]) -> None:
    lines: list[str] = []
    for filename in filenames:
        digest = _sha256_file(output_dir / filename)
        lines.append(f"{digest}  {filename}\n")
    (output_dir / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")


def validate_generator_across_seeds(
    seeds: range,
    now: datetime,
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for seed in seeds:
        rng = random.Random(seed)
        benign = generate_benign(rng, 800, now)
        hard_negatives = generate_hard_negatives(rng, 20, now)
        attacks = generate_attacks(rng, 30, now, [1, 2, 3, 4, 5, 6, 7])
        family_counts: dict[str, int] = {}
        hn_archetype_counts: dict[str, int] = {}
        for record in benign + hard_negatives + attacks:
            family = str(record["family"])
            family_counts[family] = family_counts.get(family, 0) + 1
            if family.startswith("hn_"):
                hn_archetype_counts[family] = hn_archetype_counts.get(family, 0) + 1
        attack_count = len(attacks)
        total = len(benign) + len(hard_negatives) + attack_count
        summaries.append(
            {
                "seed": seed,
                "benign_count": len(benign),
                "attack_count": attack_count,
                "hn_count": len(hard_negatives),
                "attack_rate": attack_count / total if total else 0.0,
                "family_counts": family_counts,
                "hn_archetype_counts": hn_archetype_counts,
            }
        )
    return summaries


_SEMANTIC_PRICE_BANDS_MINOR: dict[str, tuple[int, int]] = {
    "Electronics": (50_000, 500_000),
    "Groceries": (5_000, 60_000),
    "Home Goods": (20_000, 300_000),
    "Apparel": (30_000, 300_000),
    "Health & Personal Care": (10_000, 150_000),
    "Office Supplies": (5_000, 200_000),
    "Toys & Games": (20_000, 250_000),
    "Pet Supplies": (15_000, 200_000),
    "Automotive": (30_000, 500_000),
    "Books & Media": (15_000, 150_000),
}

_SINGLETON_PARENT_INTENT_LEAVES: frozenset[str] = frozenset(
    {
        "Electronics > Cables > HDMI Cable",
        "Electronics > Office > Desk Lamp",
        "Apparel > Sleepwear > Pajama Set",
        "Toys & Games > Action Figures > Action Figure Set",
        "Toys & Games > Plush > Stuffed Animal",
        "Books & Media > Magazines > Monthly Magazine Subscription",
        "Books & Media > Stationery Media > Journal Notebook",
        "Books & Media > Educational > Textbook",
    }
)

_CATEGORY_COMPOSITION: tuple[
    tuple[str, str | None, bool | None, int],
    ...,
] = (
    ("same_leaf", "WITHIN", False, 12),
    ("same_leaf", "BOUNDARY", False, 3),
    ("same_leaf", "OUTSIDE", False, 3),
    ("sibling", "WITHIN", True, 8),
    ("sibling", "BOUNDARY", True, 1),
    ("sibling", "OUTSIDE", True, 1),
    ("sibling", None, False, 6),
    ("diff_parent", None, None, 6),
    ("cross_top", None, None, 10),
)

# Leaf product names (lowercased) that stay unchanged when intent_qty != 1.
# Already-plural compounds: earbuds, headphones, boots, sneakers, sandals,
# jeans, shorts, noodles, bars, beans, sheets, capsules, bandages, wipes,
# notes, clips, blocks, cards, mats, blades, vitamins.
# Mass-noun / uncountable product names: oils, rice, butters, water, milk,
# paper, pet food, soap, trail/dried-fruit mix.
_INVARIANT_PLURAL_PHRASES: frozenset[str] = frozenset(
    {
        "wireless earbuds",
        "headphones",
        "boots",
        "sneakers",
        "sandals",
        "jeans",
        "shorts",
        "rice noodles",
        "granola bars",
        "coffee beans",
        "bed sheets",
        "fish oil capsules",
        "adhesive bandages",
        "antiseptic wipes",
        "sticky notes",
        "binder clips",
        "building blocks",
        "flash cards",
        "floor mats",
        "windshield wiper blades",
        "pet vitamins",
        "olive oil",
        "brown rice",
        "almond butter",
        "peanut butter",
        "sparkling water",
        "oat milk",
        "printer paper",
        "dry dog food",
        "wet cat food",
        "motor oil",
        "car wash soap",
        "trail mix",
        "dried fruit mix",
    }
)

# Irregular last-token plurals found in TAXONOMY_LEAVES (129-leaf scan).
_IRREGULAR_PLURALS: dict[str, str] = {
    "mouse": "mice",
    "stylus": "styluses",
    "scarf": "scarves",
}

_INTENT_QTY_PURCHASE_INTENT_RE = re.compile(
    r"^(purchase|buy|order|get) (\d+) (.+)$"
)


def _pluralize_token(word: str) -> str:
    irregular = _IRREGULAR_PLURALS.get(word)
    if irregular is not None:
        return irregular
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return f"{word}es"
    if len(word) >= 2 and word.endswith("y") and word[-2] not in "aeiou":
        return f"{word[:-1]}ies"
    return f"{word}s"


def pluralize(word: str) -> str:
    """Pluralize a lowercased leaf product name for purchase_intent qty text."""
    phrase = word.strip()
    if phrase in _INVARIANT_PLURAL_PHRASES:
        return phrase
    parts = phrase.split()
    if not parts:
        return phrase
    if len(parts) == 1:
        return _pluralize_token(parts[0])
    return " ".join([*parts[:-1], _pluralize_token(parts[-1])])


def _pluralize_purchase_intent(purchase_intent: str) -> str:
    match = _INTENT_QTY_PURCHASE_INTENT_RE.match(purchase_intent)
    if match is None:
        return purchase_intent
    verb, qty, leaf_product_name = match.groups()
    return f"{verb} {qty} {pluralize(leaf_product_name)}"


def _build_leaf_base_price_table() -> dict[str, int]:
    from mandate_guard.taxonomy import TAXONOMY_LEAVES

    price_rng = random.Random(271000)
    table: dict[str, int] = {}
    for leaf in TAXONOMY_LEAVES:
        top_level = leaf.split(" > ", 1)[0]
        lo, hi = _SEMANTIC_PRICE_BANDS_MINOR[top_level]
        table[leaf] = price_rng.randint(lo, hi)
    return table


def _build_tolerance_pair_pools() -> dict[str, list[tuple[float, float]]]:
    from mandate_guard.semantic_adjudication import combined_tolerance_state

    pools: dict[str, list[tuple[float, float]]] = {
        "WITHIN": [],
        "BOUNDARY": [],
        "OUTSIDE": [],
    }
    ratio_grid = [0.70, 0.80, 0.85, 0.90, 0.95, 1.0, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30]
    for amount_ratio in ratio_grid:
        for quantity_ratio in ratio_grid:
            state = combined_tolerance_state(amount_ratio, quantity_ratio)
            pools[state].append((amount_ratio, quantity_ratio))
    if not pools["WITHIN"] or not pools["BOUNDARY"] or not pools["OUTSIDE"]:
        raise RuntimeError("failed to build semantic tolerance pair pools")
    return pools


def _build_semantic_taxonomy_indexes() -> tuple[
    dict[str, list[str]],
    dict[str, dict[tuple[str, str], list[str]]],
    list[str],
]:
    from mandate_guard.taxonomy import TAXONOMY_LEAVES

    leaves_by_category: dict[str, list[str]] = {}
    parent_leaves_by_category: dict[str, dict[tuple[str, str], list[str]]] = {}
    for leaf in TAXONOMY_LEAVES:
        parts = leaf.split(" > ")
        category = parts[0]
        parent_key = (parts[0], parts[1])
        leaves_by_category.setdefault(category, []).append(leaf)
        parent_leaves_by_category.setdefault(category, {}).setdefault(
            parent_key, []
        ).append(leaf)
    top_levels = sorted(leaves_by_category.keys())
    return leaves_by_category, parent_leaves_by_category, top_levels


LEAF_BASE_PRICE: dict[str, int] = _build_leaf_base_price_table()
_TOLERANCE_PAIR_POOLS: dict[str, list[tuple[float, float]]] = (
    _build_tolerance_pair_pools()
)
_LEAVES_BY_CATEGORY, _PARENT_LEAVES_BY_CATEGORY, _TOP_LEVEL_CATEGORIES = (
    _build_semantic_taxonomy_indexes()
)


def _sample_tolerance_pair(
    rng: random.Random,
    target: str,
) -> tuple[float, float]:
    return rng.choice(_TOLERANCE_PAIR_POOLS[target])


def _sample_any_tolerance_pair(rng: random.Random) -> tuple[float, float]:
    target = rng.choice(("WITHIN", "BOUNDARY", "OUTSIDE"))
    return _sample_tolerance_pair(rng, target)


def _pick_same_leaf(rng: random.Random, category_leaves: list[str]) -> tuple[str, str]:
    leaf = rng.choice(category_leaves)
    return leaf, leaf


def _pick_sibling_pair(
    rng: random.Random,
    category: str,
) -> tuple[str, str]:
    parent_map = _PARENT_LEAVES_BY_CATEGORY[category]
    eligible_parents = [
        parent for parent, leaves in parent_map.items() if len(leaves) >= 2
    ]
    parent = rng.choice(eligible_parents)
    leaves = parent_map[parent]
    intent_leaf = rng.choice(leaves)
    cart_leaf = rng.choice([leaf for leaf in leaves if leaf != intent_leaf])
    return intent_leaf, cart_leaf


def _pick_diff_parent_pair(
    rng: random.Random,
    category: str,
) -> tuple[str, str]:
    parent_map = _PARENT_LEAVES_BY_CATEGORY[category]
    parent_a, parent_b = rng.sample(list(parent_map.keys()), 2)
    intent_leaf = rng.choice(parent_map[parent_a])
    cart_leaf = rng.choice(parent_map[parent_b])
    return intent_leaf, cart_leaf


def _pick_cross_top_pair(
    rng: random.Random,
    category: str,
) -> tuple[str, str]:
    other_categories = [name for name in _TOP_LEVEL_CATEGORIES if name != category]
    other_category = rng.choice(other_categories)
    intent_leaf = rng.choice(_LEAVES_BY_CATEGORY[category])
    cart_leaf = rng.choice(_LEAVES_BY_CATEGORY[other_category])
    return intent_leaf, cart_leaf


def _pick_leaves_for_semantic_case(
    rng: random.Random,
    case_type: str,
    category: str,
) -> tuple[str, str]:
    category_leaves = _LEAVES_BY_CATEGORY[category]
    if case_type == "same_leaf":
        return _pick_same_leaf(rng, category_leaves)
    if case_type == "sibling":
        return _pick_sibling_pair(rng, category)
    if case_type == "diff_parent":
        return _pick_diff_parent_pair(rng, category)
    if case_type == "cross_top":
        return _pick_cross_top_pair(rng, category)
    raise ValueError(f"unknown semantic case type {case_type!r}")


def generate_semantic_corpus(
    rng: random.Random,
    now: datetime,
) -> list[dict[str, object]]:
    from mandate_guard.semantic_record_builder import build_semantic_record

    records: list[dict[str, object]] = []
    index = 0
    for category in _TOP_LEVEL_CATEGORIES:
        for (
            case_type,
            tolerance_target,
            rationale_present,
            count,
        ) in _CATEGORY_COMPOSITION:
            for _ in range(count):
                intent_leaf, cart_leaf = _pick_leaves_for_semantic_case(
                    rng,
                    case_type,
                    category,
                )
                if tolerance_target is None:
                    amount_ratio, quantity_ratio = _sample_any_tolerance_pair(rng)
                else:
                    amount_ratio, quantity_ratio = _sample_tolerance_pair(
                        rng,
                        tolerance_target,
                    )
                rationale = (
                    rationale_present if rationale_present is not None else False
                )
                # Deliberately anchored to intent_leaf, not cart_leaf: a cross-category
                # substitute priced 'normally' for ITS OWN category would hide the
                # amount-deviation signal this corpus needs to test. Visually implausible
                # price/product pairs in DEVIATION/UNCERTAIN records are intentional, not
                # a bug.
                record = build_semantic_record(
                    rng,
                    index,
                    category,
                    intent_leaf,
                    cart_leaf,
                    amount_ratio,
                    quantity_ratio,
                    rationale,
                    now,
                    base_unit_price_minor_units=LEAF_BASE_PRICE[intent_leaf],
                )
                record["purchase_intent"] = _pluralize_purchase_intent(
                    str(record["purchase_intent"])
                )
                records.append(record)
                index += 1
    return records


def generate_corpus(split: str, output_dir: Path, now: datetime) -> None:
    sums_path = output_dir / "SHA256SUMS"
    if sums_path.exists():
        raise SystemExit(
            "SHA256SUMS exists — sealed corpus is frozen. Delete manually to regenerate."
        )

    if split == "dev":
        seed = 42
        rng = random.Random(seed)
        benign = generate_benign(rng, 800, now)
        hard_negatives = generate_hard_negatives(rng, 20, now)
        attacks = generate_attacks(rng, 30, now, [1, 2, 3, 4, 5, 6, 7, 14, 15])
        files = {
            "benign.jsonl": benign,
            "hard_negatives.jsonl": hard_negatives,
            "attacks.jsonl": attacks,
        }
    elif split == "sealed":
        seed = 137
        rng = random.Random(seed)
        attacks = generate_attacks(rng, 25, now, [8, 9, 10, 11, 12, 13])
        files = {"attacks.jsonl": attacks}
    elif split == "sealed_semantic":
        seed = 271
        rng = random.Random(seed)
        records = generate_semantic_corpus(rng, now)
        files = {"semantic.jsonl": records}
    else:
        raise ValueError(f"unknown split {split!r}")

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, records in files.items():
        _write_jsonl(output_dir / filename, records)

    filenames = sorted(files.keys())
    _write_sha256sums(output_dir, filenames)

    print(f"split={split} seed={seed} output_dir={output_dir.resolve()}")
    for filename, records in files.items():
        digest = _sha256_file(output_dir / filename)
        print(f"{filename}: {len(records)} records sha256={digest}")
    print(f"SHA256SUMS written to {sums_path.resolve()}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate mandate-guard corpus.")
    parser.add_argument(
        "--split",
        choices=["dev", "sealed", "sealed_semantic"],
        required=True,
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--now",
        default="2026-08-01T12:00:00",
        help="ISO datetime reference for generation",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    now = datetime.fromisoformat(args.now)
    if args.output_dir is None:
        if args.split == "dev":
            output_dir = Path("data/dev")
        elif args.split == "sealed_semantic":
            output_dir = Path("data/sealed_semantic")
        else:
            output_dir = Path("data/sealed")
    else:
        output_dir = args.output_dir
    generate_corpus(args.split, output_dir, now)


if __name__ == "__main__":
    main()
