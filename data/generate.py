"""Generate dev and sealed mandate-guard corpora from contract objects."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

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

    return _serialize_record(
        base,
        record_id=f"zz-record-{archetype}-{n}",
        label="ALLOW",
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
        attacks = generate_attacks(rng, 30, now, [1, 2, 3, 4, 5, 6, 7])
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
    parser.add_argument("--split", choices=["dev", "sealed"], required=True)
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
        output_dir = Path("data/dev" if args.split == "dev" else "data/sealed")
    else:
        output_dir = args.output_dir
    generate_corpus(args.split, output_dir, now)


if __name__ == "__main__":
    main()
