"""Pure evaluation logic for mandate-guard tier scoring and metrics.

No printing, no argparse. All I/O lives in scripts/run_eval.py. The sealed set
is accessed only via load_sealed_attacks(), which verifies SHA256 before reading.
Single-threshold eval only — HOLD tier is a documented gap in docs/LIMITATIONS.md
(not yet built).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, TypedDict, cast

import numpy as np
from sklearn.metrics import average_precision_score  # type: ignore[import-untyped]

from contracts import (
    CartItem,
    CartMandate,
    DelegationToken,
    IntentMandate,
    Money,
    Scope,
)

from .t0 import check as t0_check
from .t1 import score as t1_score

INJECTION_PATTERNS: tuple[str, ...] = (
    "ignore previous",
    "disregard",
    "act as",
    "you are now",
    "jailbreak",
)

AMOUNT_THRESHOLD_MINOR_UNITS: int = 10000  # ASSUMPTION — see baselines

BaselineName = Literal[
    "allow_everything",
    "block_everything",
    "amount_threshold",
    "regex_injection_detector",
    "t0_only",
]


class T0CheckArgs(TypedDict):
    intent: IntentMandate
    cart: CartMandate
    token: DelegationToken | None
    transaction_amount: Money
    merchant_id: str
    mcc: str
    now: datetime


def _record_to_t0_args(record: dict[str, object]) -> T0CheckArgs:
    """Reconstruct t0.check() keyword arguments from a flat corpus record."""
    merchants_raw = record["intent_scope_merchants"]
    categories_raw = record["intent_scope_categories"]
    max_amount = None
    if record["intent_scope_max_amount_minor_units"] is not None:
        max_amount = Money(
            int(cast(int, record["intent_scope_max_amount_minor_units"])),
            str(record["intent_scope_max_amount_currency"]),
        )
    merchants = (
        frozenset(cast(list[str], merchants_raw)) if merchants_raw is not None else None
    )
    categories = (
        frozenset(cast(list[str], categories_raw))
        if categories_raw is not None
        else None
    )
    scope = Scope(
        merchants=merchants,
        categories=categories,
        max_amount=max_amount,
    )
    intent = IntentMandate(
        mandate_id=str(record["intent_mandate_id"]),
        principal_id=str(record["intent_principal_id"]),
        scope=scope,
        issued_at=datetime.fromisoformat(str(record["intent_issued_at"])),
        expires_at=datetime.fromisoformat(str(record["intent_expires_at"])),
        cart_hash=record["intent_cart_hash"],  # type: ignore[arg-type]
        purchase_intent=str(record.get("purchase_intent", "")),
    )
    cart_items = cast(list[dict[str, object]], record["cart_items"])
    items = tuple(
        CartItem(
            sku=str(item["sku"]),
            name=str(item["name"]),
            quantity=int(cast(int, item["quantity"])),
            unit_price=Money(
                int(cast(int, item["unit_price_minor_units"])),
                str(item["unit_price_currency"]),
            ),
        )
        for item in cart_items
    )
    cart = CartMandate(
        mandate_id=str(record["cart_mandate_id"]),
        items=items,
        total=Money(
            int(cast(int, record["cart_total_minor_units"])),
            str(record["cart_total_currency"]),
        ),
        cart_hash=str(record["cart_hash"]),
    )
    token = _delegation_token_from_record(record, scope, intent)
    now = datetime.fromisoformat(str(record["intent_expires_at"])) - timedelta(days=1)
    return {
        "intent": intent,
        "cart": cart,
        "token": token,
        "transaction_amount": Money(
            int(cast(int, record["transaction_amount_minor_units"])),
            str(record["transaction_amount_currency"]),
        ),
        "merchant_id": str(record["merchant_id"]),
        "mcc": str(record["mcc"]),
        "now": now,
    }


def _delegation_token_from_record(
    record: dict[str, object],
    parent_scope: Scope,
    intent: IntentMandate,
) -> DelegationToken | None:
    token_id = record.get("delegation_token_id")
    if not token_id:
        return None
    family = str(record["family"])
    if family == "hn_narrowed_delegation":
        delegated_scope = Scope(
            merchants=frozenset({str(record["merchant_id"])}),
            categories=parent_scope.categories,
            max_amount=parent_scope.max_amount,
        )
    elif family in {"attack_family_5", "attack_family_12"}:
        assert parent_scope.max_amount is not None
        delegated_scope = Scope(
            merchants=parent_scope.merchants,
            categories=parent_scope.categories,
            max_amount=Money(
                parent_scope.max_amount.minor_units + 10000,
                parent_scope.max_amount.currency,
            ),
        )
    else:
        return None
    return DelegationToken(
        token_id=str(token_id),
        parent_mandate_id=intent.mandate_id,
        parent_scope=parent_scope,
        delegated_scope=delegated_scope,
        issued_at=intent.issued_at,
        expires_at=intent.expires_at,
    )


def score_baseline(name: BaselineName, record: dict[str, object]) -> float:
    if name == "allow_everything":
        return 0.0
    if name == "block_everything":
        return 1.0
    if name == "amount_threshold":
        amount = int(cast(int, record["transaction_amount_minor_units"]))
        return 1.0 if amount > AMOUNT_THRESHOLD_MINOR_UNITS else 0.0
    if name == "regex_injection_detector":
        fields = [
            str(record.get("note", "")),
            str(record.get("family_note", "")),
            str(record.get("merchant_id", "")),
            str(record.get("mcc", "")),
        ]
        text = " ".join(fields).lower()
        return 1.0 if any(pattern in text for pattern in INJECTION_PATTERNS) else 0.0
    args = _record_to_t0_args(record)
    result = t0_check(
        args["intent"],
        args["cart"],
        args["token"],
        args["transaction_amount"],
        args["merchant_id"],
        args["mcc"],
        args["now"],
    )
    return 0.0 if result.passed else 1.0


def score_t1(record: dict[str, object], model_dir: Path) -> float:
    args = _record_to_t0_args(record)
    return t1_score(
        args["intent"],
        args["cart"],
        args["token"],
        args["transaction_amount"],
        args["merchant_id"],
        args["mcc"],
        args["now"],
        model_dir,
    )


def score_t0_t1(record: dict[str, object], model_dir: Path) -> float:
    """
    Combined T0+T1 cascade score.

    T0 is a hard gate: if T0 fires, return 1.0 immediately.
    T1 provides signal only when T0 passes.
    This matches the architecture invariant: T0 violations are
    deterministic BLOCK regardless of T1 score.
    """
    t0_score = score_baseline("t0_only", record)
    if t0_score == 1.0:
        return 1.0
    return score_t1(record, model_dir)


def compute_metrics(
    records: list[dict[str, object]],
    scores: list[float],
    threshold: float,
    prior: float = 0.008,
) -> dict[str, float]:
    predictions = [1 if score >= threshold else 0 for score in scores]
    y_true = [1 if str(record["label"]) == "BLOCK" else 0 for record in records]

    tp = sum(
        prediction == 1 and label == 1 for prediction, label in zip(predictions, y_true)
    )
    fp = sum(
        prediction == 1 and label == 0 for prediction, label in zip(predictions, y_true)
    )
    fn = sum(
        prediction == 0 and label == 1 for prediction, label in zip(predictions, y_true)
    )
    tn = sum(
        prediction == 0 and label == 0 for prediction, label in zip(predictions, y_true)
    )

    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr_all = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    if recall == 0.0 and fpr_all == 0.0:
        precision_at_prior = 0.0
    else:
        denom = recall * prior + fpr_all * (1.0 - prior)
        precision_at_prior = 0.0 if denom == 0.0 else (recall * prior) / denom

    hn_indices = [
        index
        for index, record in enumerate(records)
        if str(record["family"]).startswith("hn_")
    ]
    if not hn_indices:
        fpr_hard_negatives = 0.0
    else:
        fpr_hard_negatives = sum(
            1 for index in hn_indices if scores[index] >= threshold
        ) / len(hn_indices)

    y_true_arr = np.array(y_true)
    if len(set(y_true_arr.tolist())) < 2:
        pr_auc = 1.0 if y_true_arr[0] == 1 else 0.0
    else:
        pr_auc = float(average_precision_score(y_true_arr, np.array(scores)))

    total = len(records)
    cost = fp * 320.0 + fn * 1470.0
    net_cost_per_10k = (cost / total) * 10000.0 if total > 0 else 0.0

    return {
        "precision_at_prior": float(precision_at_prior),
        "recall": float(recall),
        "fpr_hard_negatives": float(fpr_hard_negatives),
        "pr_auc": float(pr_auc),
        "net_cost_per_10k": float(net_cost_per_10k),
        "fp_count": float(fp),
        "fn_count": float(fn),
        "tp_count": float(tp),
        "tn_count": float(tn),
    }


def find_cost_optimal_threshold(
    records: list[dict[str, object]],
    scores: list[float],
    fp_cost: float = 320.0,
    fn_cost: float = 1470.0,
) -> tuple[float, float]:
    y_true = [1 if str(record["label"]) == "BLOCK" else 0 for record in records]
    best_tau = 0.0
    best_cost = float("inf")
    for step in range(101):
        tau = step / 100.0
        preds = [1 if score >= tau else 0 for score in scores]
        fp = sum(
            prediction == 1 and label == 0 for prediction, label in zip(preds, y_true)
        )
        fn = sum(
            prediction == 0 and label == 1 for prediction, label in zip(preds, y_true)
        )
        cost = fp * fp_cost + fn * fn_cost
        if cost < best_cost or (cost == best_cost and tau > best_tau):
            best_tau = tau
            best_cost = cost
    return best_tau, best_cost


def recall_on_records(
    records: list[dict[str, object]],
    scores: list[float],
    threshold: float,
) -> float:
    if not records:
        return 0.0
    caught = sum(1 for score in scores if score >= threshold)
    return caught / len(records)


def _verify_sha256(directory: Path, filename: str, expected: str) -> None:
    computed = hashlib.sha256((directory / filename).read_bytes()).hexdigest()
    if computed != expected:
        raise ValueError(
            f"SHA256 mismatch for {filename}: expected={expected} computed={computed}"
        )


def load_sealed_attacks(sealed_dir: Path) -> list[dict[str, object]]:
    sums_path = sealed_dir / "SHA256SUMS"
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, filename = line.split("  ", 1)
        _verify_sha256(sealed_dir, filename, digest)
    records: list[dict[str, object]] = []
    for line in (sealed_dir / "attacks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def precision_vs_prevalence(
    records: list[dict[str, object]],
    scores: list[float],
    threshold: float,
    prior_range: tuple[float, float, float] = (0.001, 0.101, 0.001),
) -> list[dict[str, float]]:
    start, stop, step = prior_range
    prior = start
    curve: list[dict[str, float]] = []
    while prior <= stop + 1e-12:
        metrics = compute_metrics(records, scores, threshold, prior=prior)
        curve.append(
            {
                "prior": float(prior),
                "precision": metrics["precision_at_prior"],
            }
        )
        prior += step
    return curve
