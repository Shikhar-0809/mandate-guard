"""CLI entry point for mandate-guard evaluation.

Loads corpora, scores all baselines and T1, prints a report, writes eval results
to baselines.json and the precision-vs-prevalence curve to
eval_outputs/precision_vs_prevalence.json. Single-threshold eval — HOLD tier not
yet implemented.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mandate_guard.eval import (
    BaselineName,
    _record_to_t0_args,
    _verify_sha256,
    compute_metrics,
    find_cost_optimal_threshold,
    load_sealed_attacks,
    precision_vs_prevalence,
    recall_on_records,
    score_baseline,
    score_t0_t1,
)

BASELINE_NAMES: tuple[BaselineName, ...] = (
    "allow_everything",
    "block_everything",
    "amount_threshold",
    "regex_injection_detector",
    "t0_only",
)


def _load_dev(dev_dir: Path) -> list[dict[str, object]]:
    for line in (dev_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, filename = line.split("  ", 1)
        _verify_sha256(dev_dir, filename, digest)
    records: list[dict[str, object]] = []
    for filename in ("benign.jsonl", "hard_negatives.jsonl", "attacks.jsonl"):
        for line in (dev_dir / filename).read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def _format_metrics_row(name: str, metrics: dict[str, float]) -> str:
    return (
        f"{name:<28} "
        f"{metrics['precision_at_prior']:>9.4f}  "
        f"{metrics['recall']:>6.4f}  "
        f"{metrics['fpr_hard_negatives']:>6.4f}  "
        f"{metrics['pr_auc']:>6.4f}  "
        f"{metrics['net_cost_per_10k']:>8.1f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run mandate-guard evaluation")
    parser.add_argument("--model-dir", type=Path, default=Path("models/"))
    parser.add_argument("--prior", type=float, default=0.008)
    parser.add_argument(
        "--enable-t2",
        action="store_true",
        default=False,
        help="Run T2 Ollama verifier on eligible sealed records",
    )
    args = parser.parse_args()

    dev_dir = PROJECT_ROOT / "data" / "dev"
    sealed_dir = PROJECT_ROOT / "data" / "sealed"
    dev_records = _load_dev(dev_dir)
    sealed_records = load_sealed_attacks(sealed_dir)

    n_benign = sum(1 for record in dev_records if str(record["family"]) == "benign")
    n_hn = sum(1 for record in dev_records if str(record["family"]).startswith("hn_"))
    n_attacks = sum(1 for record in dev_records if str(record["label"]) == "BLOCK")
    n_sealed = len(sealed_records)

    baseline_scores: dict[BaselineName, list[float]] = {}
    for name in BASELINE_NAMES:
        baseline_scores[name] = [score_baseline(name, record) for record in dev_records]

    t1_scores = [score_t0_t1(record, args.model_dir) for record in dev_records]
    tau_star, _ = find_cost_optimal_threshold(dev_records, t1_scores)

    baseline_threshold = 0.5
    baseline_metrics: dict[BaselineName, dict[str, float]] = {}
    for name in BASELINE_NAMES:
        baseline_metrics[name] = compute_metrics(
            dev_records,
            baseline_scores[name],
            baseline_threshold,
            prior=args.prior,
        )

    t1_metrics = compute_metrics(dev_records, t1_scores, tau_star, prior=args.prior)

    dev_attack_records = [
        record for record in dev_records if str(record["label"]) == "BLOCK"
    ]
    dev_attack_scores = [
        score_t0_t1(record, args.model_dir) for record in dev_attack_records
    ]
    recall_seen = recall_on_records(dev_attack_records, dev_attack_scores, tau_star)

    sealed_scores = [score_t0_t1(record, args.model_dir) for record in sealed_records]
    recall_unseen = recall_on_records(sealed_records, sealed_scores, tau_star)

    curve = precision_vs_prevalence(dev_records, t1_scores, tau_star)

    print("=== mandate-guard evaluation report ===")
    print()
    print(
        f"Dev corpus: {n_benign} benign + {n_hn} hard negatives + {n_attacks} attacks"
    )
    print(f"Sealed corpus: {n_sealed} attacks")
    print(
        "Cost model: FP=₹320 FN=₹1470 HOLD=₹45 (three-term objective: fp*320 + fn*1470 + hold*45)"
        "              [ASSUMPTION — see config/cost_model.yaml when built]"
    )
    print()
    print(f"Cost-optimal threshold (τ*): {tau_star:.3f}")
    print()
    print("--- Baseline comparison (dev corpus, τ=0.5 for baselines) ---")
    print(f"{'':28} prec@prior  recall   fpr_hn   pr_auc   cost/10k")
    for name in BASELINE_NAMES:
        print(_format_metrics_row(name, baseline_metrics[name]))
    print(_format_metrics_row("T0+T1 (at τ*)", t1_metrics))
    print()
    print("--- Recall split ---")
    print(f"recall_seen  (dev  families 1-7): {recall_seen:.4f}")
    print(f"recall_unseen (sealed families 8-12): {recall_unseen:.4f}")
    print()
    print("--- T2 kill criterion ---")
    print(
        "T2 must lift recall_unseen by >=2pp over T0+T1 on dev set to "
        "ship enabled. Current T0+T1 recall_unseen: "
        f"{recall_unseen:.4f}"
    )
    print(f"Target: {recall_unseen + 0.02:.4f}")
    print()
    print("===")

    baselines_path = PROJECT_ROOT / "baselines.json"
    existing: dict[str, object] = {}
    if baselines_path.exists():
        existing = json.loads(baselines_path.read_text(encoding="utf-8"))
    existing.update(
        {
            "eval_tau_star": tau_star,
            "eval_recall_seen": recall_seen,
            "eval_recall_unseen": recall_unseen,
            "eval_t1_precision_at_prior": t1_metrics["precision_at_prior"],
            "eval_t1_recall": t1_metrics["recall"],
            "eval_t1_fpr_hard_negatives": t1_metrics["fpr_hard_negatives"],
            "eval_t1_pr_auc": t1_metrics["pr_auc"],
            "eval_t1_net_cost_per_10k": t1_metrics["net_cost_per_10k"],
            "baselines_compared": list(BASELINE_NAMES),
        }
    )
    baselines_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    eval_outputs_dir = PROJECT_ROOT / "eval_outputs"
    eval_outputs_dir.mkdir(parents=True, exist_ok=True)
    curve_path = eval_outputs_dir / "precision_vs_prevalence.json"
    curve_path.write_text(json.dumps(curve, indent=2), encoding="utf-8")

    if args.enable_t2:
        from contracts import T2Config
        from mandate_guard.t2 import verify as t2_verify

        t2_config = T2Config(t2_enabled=True)
        model_dir = args.model_dir

        sealed_records = load_sealed_attacks(sealed_dir)
        sealed_scores_t2: list[float] = []
        t2_invoked = 0
        t2_blocked = 0
        t2_actually_invoked = 0

        for record in sealed_records:
            base_score = score_t0_t1(record, model_dir)
            purchase_intent = str(record.get("purchase_intent", ""))

            if base_score < 1.0 and purchase_intent:
                args_dict = _record_to_t0_args(record)
                intent_obj = args_dict["intent"]
                cart_obj = args_dict["cart"]
                result = t2_verify(
                    intent_obj,
                    cart_obj,
                    None,
                    None,
                    t2_config,
                )
                t2_invoked += 1
                if result.invoked:
                    t2_actually_invoked += 1
                if result.invoked and result.verdict.value == "BLOCK":
                    sealed_scores_t2.append(1.0)
                    t2_blocked += 1
                else:
                    sealed_scores_t2.append(base_score)
            else:
                sealed_scores_t2.append(base_score)

        if t2_invoked > 0 and t2_actually_invoked == 0:
            print("ERROR: T2 was called but Ollama returned no invoked=True results.")
            print("All T2 results were degraded. baselines.json will NOT be updated.")
            sys.exit(1)

        recall_unseen_t2 = recall_on_records(sealed_records, sealed_scores_t2, tau_star)
        lift = recall_unseen_t2 - recall_unseen
        criterion_met = lift >= 0.02

        print("\n--- T2 evaluation (Ollama: qwen2.5:7b) ---")
        print(f"T2 gate invocations: {t2_invoked}")
        print(f"T2 blocked:          {t2_blocked}")
        print(f"recall_unseen T0+T1:     {recall_unseen:.4f}")
        print(f"recall_unseen T0+T1+T2:  {recall_unseen_t2:.4f}")
        print(f"Lift:                    {lift:+.4f}")
        print(f"Kill criterion (>=+0.02): {'MET' if criterion_met else 'NOT MET'}")
        if criterion_met:
            print("T2 EARNS ITS PLACE — update T2Config default to enabled.")
        else:
            print("T2 stays degraded — D008 stands.")

        bl_path = PROJECT_ROOT / "baselines.json"
        bl = json.loads(bl_path.read_text(encoding="utf-8"))
        bl["eval_recall_unseen_t2"] = recall_unseen_t2
        bl["eval_t2_lift"] = lift
        bl["eval_t2_kill_criterion_met"] = criterion_met
        bl["eval_t2_invocations"] = t2_invoked
        bl["eval_t2_blocked"] = t2_blocked
        bl_path.write_text(json.dumps(bl, indent=2), encoding="utf-8")
        print("\nbaselines.json updated with T2 results.")


if __name__ == "__main__":
    main()
