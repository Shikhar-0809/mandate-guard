"""CLI entry point for M1 semantic sealed-set evaluation (D053/D057)."""

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

from contracts import T2Config
from contracts.verdict import VerdictState
from mandate_guard.eval import (
    _verify_sha256,
    cascade_verdict_rate,
    find_cost_optimal_threshold,
    load_sealed_semantic,
    score_t0_t1,
)
from mandate_guard.normalize import normalize_semantic_labels_for_training

BASELINES_SEMANTIC_FILENAME = "baselines_sealed_semantic.json"

# Verified inline, not via data/dev/SHA256SUMS: hard_negatives_with_intent.jsonl
# is not listed there (pre-existing project-wide gap affecting all
# *_with_intent.jsonl readers, not fixed here — out of scope for this script).
_HARD_NEGATIVES_WITH_INTENT_SHA256 = (
    "9e73421f24ce4c0504c793551489313fe317f84c320186a4a1f4056b24a5d0a4"
)


def _load_dev_hard_negatives(dev_dir: Path) -> list[dict[str, object]]:
    print("Loading hard_negatives_with_intent...")
    filename = "hard_negatives_with_intent.jsonl"
    _verify_sha256(dev_dir, filename, _HARD_NEGATIVES_WITH_INTENT_SHA256)
    records: list[dict[str, object]] = []
    for line in (dev_dir / filename).read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def evaluate_kill_criterion(
    recall_t2_off: float,
    recall_t2_on: float,
    hn_block_rate_t2_off: float,
    hn_block_rate_t2_on: float,
) -> dict[str, float | bool]:
    recall_lift = recall_t2_on - recall_t2_off
    hn_fpr_delta = hn_block_rate_t2_on - hn_block_rate_t2_off
    kill_criterion_met = (recall_lift >= 0.05) and (hn_fpr_delta < 0.02)
    return {
        "recall_t2_off": recall_t2_off,
        "recall_t2_on": recall_t2_on,
        "recall_lift": recall_lift,
        "hn_block_rate_t2_off": hn_block_rate_t2_off,
        "hn_block_rate_t2_on": hn_block_rate_t2_on,
        "hn_fpr_delta": hn_fpr_delta,
        "kill_criterion_met": kill_criterion_met,
    }


def compute_semantic_kill_metrics(
    deviation_records: list[dict[str, object]],
    hard_negative_records: list[dict[str, object]],
    model_dir: Path,
    tau_star: float,
) -> dict[str, float | bool]:
    t2_off = T2Config(t2_enabled=False)
    t2_on = T2Config(t2_enabled=True)
    print(f"Scoring DEVIATION population, T2 OFF (n={len(deviation_records)})...")
    recall_t2_off = cascade_verdict_rate(
        deviation_records,
        model_dir,
        tau_star,
        t2_off,
        VerdictState.BLOCK,
    )
    print(f"  recall_t2_off: {recall_t2_off:.4f}")
    print(f"Scoring DEVIATION population, T2 ON (n={len(deviation_records)})...")
    recall_t2_on = cascade_verdict_rate(
        deviation_records,
        model_dir,
        tau_star,
        t2_on,
        VerdictState.BLOCK,
    )
    print(f"  recall_t2_on: {recall_t2_on:.4f}")
    print(f"Scoring hard negatives, T2 OFF (n={len(hard_negative_records)})...")
    hn_block_rate_t2_off = cascade_verdict_rate(
        hard_negative_records,
        model_dir,
        tau_star,
        t2_off,
        VerdictState.BLOCK,
    )
    print(f"  hn_block_rate_t2_off: {hn_block_rate_t2_off:.4f}")
    print(f"Scoring hard negatives, T2 ON (n={len(hard_negative_records)})...")
    hn_block_rate_t2_on = cascade_verdict_rate(
        hard_negative_records,
        model_dir,
        tau_star,
        t2_on,
        VerdictState.BLOCK,
    )
    print(f"  hn_block_rate_t2_on: {hn_block_rate_t2_on:.4f}")
    return evaluate_kill_criterion(
        recall_t2_off,
        recall_t2_on,
        hn_block_rate_t2_off,
        hn_block_rate_t2_on,
    )


def write_baselines_sealed_semantic(
    output_path: Path,
    results: dict[str, object],
) -> None:
    if output_path.exists():
        raise FileExistsError(
            f"{output_path} already exists; refusing to overwrite "
            "(D053 run-exactly-once guard)"
        )
    print("Writing baselines_sealed_semantic.json...")
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")


def run_semantic_eval(model_dir: Path, project_root: Path) -> dict[str, object]:
    semantic_dir = project_root / "data" / "sealed_semantic"
    dev_dir = project_root / "data" / "dev"

    print("Loading sealed_semantic...")
    raw_records = load_sealed_semantic(semantic_dir)
    uncertain_dropped_n = sum(
        1 for record in raw_records if str(record["label"]) == "UNCERTAIN"
    )
    normalized = normalize_semantic_labels_for_training(raw_records)

    t1_scores = [score_t0_t1(record, model_dir) for record in normalized]
    tau_star, _cost_at_tau_star = find_cost_optimal_threshold(normalized, t1_scores)

    deviation_records = [
        record for record in normalized if str(record["label"]) == "BLOCK"
    ]
    hard_negative_records = _load_dev_hard_negatives(dev_dir)

    kill_metrics = compute_semantic_kill_metrics(
        deviation_records,
        hard_negative_records,
        model_dir,
        tau_star,
    )

    return {
        "tau_star": tau_star,
        "deviation_population_n": len(deviation_records),
        "hard_negative_population_n": len(hard_negative_records),
        "uncertain_dropped_n": uncertain_dropped_n,
        **kill_metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run M1 semantic sealed-set evaluation (D053/D057)"
    )
    parser.add_argument("--model-dir", type=Path, default=Path("models/"))
    args = parser.parse_args()

    results = run_semantic_eval(args.model_dir, PROJECT_ROOT)
    output_path = PROJECT_ROOT / BASELINES_SEMANTIC_FILENAME
    write_baselines_sealed_semantic(output_path, results)

    print("=== mandate-guard semantic evaluation report ===")
    print()
    print(f"tau_star:                  {results['tau_star']:.3f}")
    print(f"deviation_population_n:    {results['deviation_population_n']}")
    print(f"hard_negative_population_n:{results['hard_negative_population_n']}")
    print(f"uncertain_dropped_n:       {results['uncertain_dropped_n']}")
    print()
    print(f"recall_t2_off:             {results['recall_t2_off']:.4f}")
    print(f"recall_t2_on:              {results['recall_t2_on']:.4f}")
    print(f"recall_lift:               {results['recall_lift']:+.4f}")
    print(f"hn_block_rate_t2_off:      {results['hn_block_rate_t2_off']:.4f}")
    print(f"hn_block_rate_t2_on:       {results['hn_block_rate_t2_on']:.4f}")
    print(f"hn_fpr_delta:              {results['hn_fpr_delta']:+.4f}")
    print(
        "kill_criterion_met:        "
        f"{results['kill_criterion_met']} (>=0.05 recall lift, <0.02 hn FPR delta)"
    )
    print()
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
