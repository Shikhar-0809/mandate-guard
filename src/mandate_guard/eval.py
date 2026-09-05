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
from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import average_precision_score  # type: ignore[import-untyped]
from sklearn.metrics.pairwise import cosine_similarity  # type: ignore[import-untyped]

from contracts import (
    CartItem,
    CartMandate,
    DelegationToken,
    IntentMandate,
    Money,
    Scope,
    T2Config,
)
from contracts.verdict import Verdict, VerdictState
from mandate_guard.cascade import check as cascade_check

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

_SEMANTIC_BASELINES: dict[str, object] = {}


def _regex_baseline_text(record: dict[str, object]) -> str:
    """Text fields a regex injection detector would scan at PSP inference time."""
    parts = [
        str(record.get("purchase_intent") or ""),
        str(record.get("note") or ""),
        str(record.get("merchant_id") or ""),
        str(record.get("mcc") or ""),
    ]
    cart_items = record.get("cart_items") or []
    for item in cart_items:
        if isinstance(item, dict):
            parts.append(str(item.get("name") or ""))
    return " ".join(parts).lower()


BaselineName = Literal[
    "allow_everything",
    "block_everything",
    "amount_threshold",
    "regex_injection_detector",
    "tfidf_cosine_baseline",
    "logreg_baseline",
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


def _record_semantic_text(record: dict[str, object]) -> tuple[str, str]:
    intent = str(record.get("purchase_intent") or "")
    cart_items = record.get("cart_items") or []
    cart_text = " ".join(
        str(item.get("name") or "") for item in cart_items if isinstance(item, dict)
    )
    return intent, cart_text


def _build_semantic_baselines() -> None:
    dev_dir = Path(__file__).resolve().parents[2] / "data" / "dev"
    records: list[dict[str, object]] = []
    for filename in (
        "attacks_with_intent.jsonl",
        "benign_with_intent.jsonl",
        "hard_negatives_with_intent.jsonl",
    ):
        for line in (dev_dir / filename).read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))

    texts: list[str] = []
    labels: list[int] = []
    for record in records:
        intent, cart_text = _record_semantic_text(record)
        texts.append(intent + " " + cart_text)
        labels.append(1 if str(record["label"]) == "BLOCK" else 0)

    vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=2,
        sublinear_tf=True,
    )
    features = vectorizer.fit_transform(texts)
    classifier = LogisticRegression(max_iter=1000, random_state=42)
    classifier.fit(features, labels)

    _SEMANTIC_BASELINES["tfidf_vec"] = vectorizer
    _SEMANTIC_BASELINES["tfidf_threshold"] = 0.3
    _SEMANTIC_BASELINES["logreg"] = classifier


def score_baseline(name: BaselineName, record: dict[str, object]) -> float:
    if name == "allow_everything":
        return 0.0
    if name == "block_everything":
        return 1.0
    if name == "amount_threshold":
        amount = int(cast(int, record["transaction_amount_minor_units"]))
        return 1.0 if amount > AMOUNT_THRESHOLD_MINOR_UNITS else 0.0
    if name == "regex_injection_detector":
        text = _regex_baseline_text(record)
        return 1.0 if any(pattern in text for pattern in INJECTION_PATTERNS) else 0.0
    if name == "tfidf_cosine_baseline":
        if not _SEMANTIC_BASELINES:
            _build_semantic_baselines()
        intent, cart_text = _record_semantic_text(record)
        if not intent or not cart_text:
            return 0.0
        vectorizer = cast(TfidfVectorizer, _SEMANTIC_BASELINES["tfidf_vec"])
        try:
            vectors = vectorizer.transform([intent, cart_text])
            similarity = float(cosine_similarity(vectors[0], vectors[1])[0][0])
        except Exception:
            return 0.0
        threshold = float(cast(float, _SEMANTIC_BASELINES["tfidf_threshold"]))
        return 1.0 if similarity < threshold else 0.0
    if name == "logreg_baseline":
        if not _SEMANTIC_BASELINES:
            _build_semantic_baselines()
        intent, cart_text = _record_semantic_text(record)
        combined = intent + " " + cart_text
        vectorizer = cast(TfidfVectorizer, _SEMANTIC_BASELINES["tfidf_vec"])
        classifier = cast(LogisticRegression, _SEMANTIC_BASELINES["logreg"])
        try:
            features = vectorizer.transform([combined])
            probability = float(classifier.predict_proba(features)[0][1])
        except Exception:
            return 0.0
        return probability
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
    result = t1_score(record, model_dir)
    if not result.intent_present:
        return 0.0
    assert result.score is not None  # guaranteed by T1Result when intent_present
    return result.score


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


def compute_cost(
    fp: int,
    fn: int,
    hold: int,
    fp_cost: float = 320.0,
    fn_cost: float = 1470.0,
    hold_cost: float = 45.0,
    n_pos: int | None = None,
    n_neg: int | None = None,
    hold_pos: int | None = None,
    hold_neg: int | None = None,
    prior: float | None = None,
) -> float:
    if prior is None:
        return fp * fp_cost + fn * fn_cost + hold * hold_cost

    if n_pos is None or n_neg is None or hold_pos is None or hold_neg is None:
        raise ValueError(
            "n_pos, n_neg, hold_pos, and hold_neg are required when prior is set"
        )

    fn_rate = fn / n_pos if n_pos > 0 else 0.0
    fp_rate = fp / n_neg if n_neg > 0 else 0.0
    hold_rate_pos = hold_pos / n_pos if n_pos > 0 else 0.0
    hold_rate_neg = hold_neg / n_neg if n_neg > 0 else 0.0
    weighted_fn = prior * fn_rate
    weighted_fp = (1.0 - prior) * fp_rate
    weighted_hold = prior * hold_rate_pos + (1.0 - prior) * hold_rate_neg
    return weighted_fn * fn_cost + weighted_fp * fp_cost + weighted_hold * hold_cost


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
        if str(record["family"]).startswith("hn_") and str(record["label"]) == "ALLOW"
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
    hold = sum(1 for s in scores if 0.0 < s < threshold)
    cost = compute_cost(fp, fn, hold)
    net_cost_per_10k = (cost / total) * 10000.0 if total > 0 else 0.0

    return {
        "precision_at_prior": float(precision_at_prior),
        "recall": float(recall),
        "fpr_all": float(fpr_all),
        "fpr_hard_negatives": float(fpr_hard_negatives),
        "pr_auc": float(pr_auc),
        "net_cost_per_10k": float(net_cost_per_10k),
        "fp_count": float(fp),
        "fn_count": float(fn),
        "tp_count": float(tp),
        "tn_count": float(tn),
        "hold_count": float(hold),
    }


def _cost_partition_at_tau(
    records: list[dict[str, object]],
    scores: list[float],
    tau: float,
) -> tuple[int, int, int, int]:
    fp = fn = hold_pos = hold_neg = 0
    for record, score in zip(records, scores):
        label = str(record["label"])
        if score == 0.0:
            if label == "BLOCK":
                fn += 1
        elif score < tau:
            if label == "BLOCK":
                hold_pos += 1
            else:
                hold_neg += 1
        elif label == "ALLOW":
            fp += 1
    return fp, fn, hold_pos, hold_neg


def find_cost_optimal_threshold(
    records: list[dict[str, object]],
    scores: list[float],
    fp_cost: float = 320.0,
    fn_cost: float = 1470.0,
    hold_cost: float = 45.0,
    prior: float | None = None,
    max_hold_rate: float | None = None,
) -> tuple[float, float]:
    n_pos = sum(1 for record in records if str(record["label"]) == "BLOCK")
    n_neg = sum(1 for record in records if str(record["label"]) == "ALLOW")
    best_tau = 0.0
    best_cost = float("inf")
    for step in range(101):
        tau = step / 100.0
        fp, fn, hold_pos, hold_neg = _cost_partition_at_tau(records, scores, tau)
        hold = hold_pos + hold_neg
        hold_rate = (hold_pos + hold_neg) / len(records) if records else 0.0
        if max_hold_rate is not None and hold_rate > max_hold_rate:
            continue
        if prior is None:
            cost = compute_cost(fp, fn, hold, fp_cost, fn_cost, hold_cost)
        else:
            cost = compute_cost(
                fp,
                fn,
                hold,
                fp_cost,
                fn_cost,
                hold_cost,
                n_pos=n_pos,
                n_neg=n_neg,
                hold_pos=hold_pos,
                hold_neg=hold_neg,
                prior=prior,
            )
        if cost < best_cost or (cost == best_cost and tau > best_tau):
            best_tau = tau
            best_cost = cost
    if max_hold_rate is not None and best_cost == float("inf"):
        raise ValueError(
            f"No tau in [0,1] satisfies max_hold_rate={max_hold_rate} "
            f"on this corpus (n={len(records)}); every threshold exceeds the "
            f"stated HOLD capacity. Raise max_hold_rate or accept lower recall."
        )
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


def load_sealed_semantic(semantic_dir: Path) -> list[dict[str, object]]:
    sums_path = semantic_dir / "SHA256SUMS"
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, filename = line.split("  ", 1)
        _verify_sha256(semantic_dir, filename, digest)
    records: list[dict[str, object]] = []
    for line in (
        (semantic_dir / "semantic.jsonl").read_text(encoding="utf-8").splitlines()
    ):
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


def threshold_sweep(
    records: list[dict[str, object]],
    scores: list[float],
    tau_values: list[float] | None = None,
) -> list[dict[str, float]]:
    if tau_values is None:
        tau_values = [step / 100.0 for step in range(0, 101, 5)]
    rows: list[dict[str, float]] = []
    for tau in tau_values:
        metrics = compute_metrics(records, scores, tau)
        rows.append(
            {
                "tau": float(tau),
                "recall": metrics["recall"],
                "fpr_all": metrics["fpr_all"],
                "fpr_hard_negatives": metrics["fpr_hard_negatives"],
                "fp_count": metrics["fp_count"],
                "fn_count": metrics["fn_count"],
                "hold_count": metrics["hold_count"],
                "net_cost_per_10k": metrics["net_cost_per_10k"],
            }
        )
    return rows


def cost_ratio_sensitivity(
    records: list[dict[str, object]],
    scores: list[float],
    fn_fp_ratios: list[float] | None = None,
    fp_cost: float = 320.0,
) -> list[dict[str, float]]:
    if fn_fp_ratios is None:
        fn_fp_ratios = [1.0, 3.0, 5.0, 10.0, 1470.0 / 320.0]
    rows: list[dict[str, float]] = []
    for ratio in fn_fp_ratios:
        fn_cost = ratio * fp_cost
        tau_star, cost_at_tau_star = find_cost_optimal_threshold(
            records,
            scores,
            fp_cost=fp_cost,
            fn_cost=fn_cost,
        )
        metrics = compute_metrics(records, scores, tau_star)
        rows.append(
            {
                "fn_fp_ratio": float(ratio),
                "fn_cost": float(fn_cost),
                "fp_cost": float(fp_cost),
                "tau_star": float(tau_star),
                "recall": metrics["recall"],
                "fp_count": metrics["fp_count"],
                "fn_count": metrics["fn_count"],
                "cost_at_tau_star": float(cost_at_tau_star),
            }
        )
    return rows


def run_cascade_on_record(
    record: dict[str, object],
    model_dir: Path,
    tau: float,
    t2_config: T2Config,
) -> Verdict:
    args = _record_to_t0_args(record)
    return cascade_check(
        intent=args["intent"],
        cart=args["cart"],
        token=args["token"],
        transaction_amount=args["transaction_amount"],
        merchant_id=args["merchant_id"],
        mcc=args["mcc"],
        now=args["now"],
        agent_request_id=str(record.get("record_id", "eval")),
        model_dir=model_dir,
        tau=tau,
        t2_config=t2_config,
    )


def cascade_verdict_rate(
    records: list[dict[str, object]],
    model_dir: Path,
    tau: float,
    t2_config: T2Config,
    target_verdict: VerdictState,
) -> float:
    if not records:
        return 0.0
    verdicts = [
        run_cascade_on_record(record, model_dir, tau, t2_config) for record in records
    ]
    return sum(1 for v in verdicts if v.verdict == target_verdict) / len(records)


def recall_by_family(
    records: list[dict[str, object]],
    model_dir: Path,
    tau: float,
    t2_config: T2Config,
) -> dict[str, float]:
    """Recall (BLOCK rate on BLOCK-labeled records) grouped by family."""
    families: dict[str, list[dict[str, object]]] = {}
    for record in records:
        families.setdefault(str(record["family"]), []).append(record)
    result: dict[str, float] = {}
    for family, family_records in families.items():
        block_records = [r for r in family_records if str(r["label"]) == "BLOCK"]
        if not block_records:
            result[family] = 0.0
            continue
        verdicts = [
            run_cascade_on_record(r, model_dir, tau, t2_config) for r in block_records
        ]
        caught = sum(1 for v in verdicts if v.verdict == VerdictState.BLOCK)
        result[family] = caught / len(block_records)
    return result
