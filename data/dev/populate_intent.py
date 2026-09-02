"""
Populate purchase_intent fields for dev corpus records.

Reads the three dev jsonl files and writes _with_intent variants
alongside the originals. Originals are never modified.

Intent generation rules by family:
  benign.*          : semantically consistent with cart ("purchase <cart_name>")
  hn_stockout_*     : intent matches original product, cart has substitute
  hn_price_drift    : intent consistent with cart (price change, not substitution)
  hn_partial_*      : intent consistent with cart
  hn_retry_*        : intent consistent with cart
  hn_basket_split   : intent consistent with cart
  hn_subscription_* : intent consistent with cart
  hn_subsidiary_*   : intent names parent brand, cart has subsidiary name
  hn_post_snapshot_*: intent consistent with cart (delivery fee added later)
  hn_currency_*     : intent consistent with cart
  hn_narrowed_*     : intent consistent with cart
  hn_semantic_*     : keep existing purchase_intent (already populated)
  attack_family_1   : amount escalation — intent says "buy <cart_name>" at normal price
  attack_family_2   : wrong merchant — intent names authorized merchant
  attack_family_3   : wrong MCC — intent names authorized category
  attack_family_4   : cart hash mismatch — intent matches original approved cart
  attack_family_5   : scope expansion via delegation — intent matches narrow scope
  attack_family_6   : mandate ID mismatch — intent matches correct mandate
  attack_family_7   : idempotency tampering — intent matches original transaction
"""

from __future__ import annotations
import json
import random
from pathlib import Path

random.seed(42)

DEV_DIR = Path(__file__).parent


def _cart_name(record: dict) -> str:
    items = record.get("cart_items") or []
    if items:
        return str(items[0].get("name") or "item")
    return "item"


def _intent_for_record(record: dict) -> str:
    existing = str(record.get("purchase_intent") or "").strip()
    family = str(record.get("family") or "")
    cart_name = _cart_name(record)

    # Keep existing intent if already populated
    if existing:
        return existing

    # Benign traffic: consistent intent
    if family.startswith("benign"):
        verbs = ["purchase", "buy", "order", "get"]
        return f"{random.choice(verbs)} {cart_name}"

    # Hard negatives
    if family == "hn_stockout_substitution":
        # Intent names original product; cart has substitute
        # Cart name is "Alternative Product N" — reconstruct original
        alt = cart_name.replace("Alternative ", "")
        return f"order {alt}"

    if family == "hn_subsidiary_confusability":
        # Intent names parent; cart has subsidiary variant
        # Cart name is something like "Merchant Subsidiary N"
        parent = cart_name.replace(" Subsidiary", "").replace(" subsidiary", "")
        return f"pay {parent}"

    if family in (
        "hn_price_drift",
        "hn_partial_capture",
        "hn_retry_fresh_idempotency",
        "hn_basket_split",
        "hn_subscription_stepup",
        "hn_post_snapshot_delivery",
        "hn_currency_rounding",
        "hn_narrowed_delegation",
    ):
        verbs = ["purchase", "buy", "order"]
        return f"{random.choice(verbs)} {cart_name}"

    # Attack families 1-7: intent is structurally consistent with mandate
    # but does NOT use brand-name substitution (that is family-13's signature)
    if family == "attack_family_1":
        # Amount escalation: intent says normal purchase, attack inflates amount
        return f"buy {cart_name}"

    if family == "attack_family_2":
        # Wrong merchant: intent names authorized merchant scope
        merchants = record.get("intent_scope_merchants") or []
        auth_merchant = str(merchants[0]) if merchants else "authorized merchant"
        return f"purchase from {auth_merchant}"

    if family == "attack_family_3":
        # Wrong MCC: intent names authorized category
        cats = record.get("intent_scope_categories") or []
        auth_cat = str(cats[0]) if cats else "authorized category"
        return f"buy {auth_cat} item"

    if family == "attack_family_4":
        # Cart hash mismatch: intent matches original approved product
        return f"order {cart_name}"

    if family == "attack_family_5":
        # Scope expansion: intent matches narrow delegated scope
        return f"purchase within approved scope"

    if family == "attack_family_6":
        # Mandate ID mismatch: intent references this mandate's product
        return f"buy {cart_name} under mandate"

    if family == "attack_family_7":
        # Idempotency tampering: intent matches original transaction
        return f"retry purchase of {cart_name}"

    # Fallback for any unrecognised family
    return f"purchase {cart_name}"


def populate_file(src: Path, dst: Path) -> int:
    records = []
    for line in src.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        record["purchase_intent"] = _intent_for_record(record)
        records.append(record)

    dst.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )
    return len(records)


def main() -> None:
    pairs = [
        ("attacks.jsonl", "attacks_with_intent.jsonl"),
        ("benign.jsonl", "benign_with_intent.jsonl"),
        ("hard_negatives.jsonl", "hard_negatives_with_intent.jsonl"),
    ]
    for src_name, dst_name in pairs:
        src = DEV_DIR / src_name
        dst = DEV_DIR / dst_name
        n = populate_file(src, dst)
        print(f"{dst_name}: {n} records written")


if __name__ == "__main__":
    main()
