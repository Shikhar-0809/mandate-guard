"""T2 candidate model benchmark on dev hard negatives with intent.

Experimental comparison of qwen3:8b against the qwen2.5:7b baseline documented
in EVAL.md section B9. Does not modify production code or baselines.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
SCRIPTS = PROJECT_ROOT / "scripts"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from contracts import T2Config
from mandate_guard.t2 import verify
from run_eval import _record_to_t0_args

CORPUS_PATH = PROJECT_ROOT / "data" / "dev" / "hard_negatives_with_intent.jsonl"
RESULTS_DIR = PROJECT_ROOT / "experiments" / "t2_model_selection"


def _model_tag(model: str) -> str:
    return model.replace(":", "-")


def _output_path(model: str) -> Path:
    return RESULTS_DIR / f"results_{_model_tag(model)}.json"


def _load_records(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _empty_verdict_counts() -> dict[str, int]:
    return {"ALLOW": 0, "HOLD": 0, "BLOCK": 0}


def _increment(
    counts: dict[str, dict[str, int]],
    family: str,
    verdict: str,
) -> None:
    if family not in counts:
        counts[family] = _empty_verdict_counts()
    counts[family][verdict] = counts[family].get(verdict, 0) + 1


def _print_table(
    title: str,
    overall: dict[str, int],
    per_family: dict[str, dict[str, int]],
    total: int,
) -> None:
    print(f"\n{title}")
    print()
    print("| Verdict | Count |")
    print("|---------|-------|")
    for verdict in ("ALLOW", "HOLD", "BLOCK"):
        print(f"| {verdict} | {overall.get(verdict, 0)} |")
    print(f"| TOTAL | {total} |")
    print()
    print("| Family | ALLOW | HOLD | BLOCK |")
    print("|--------|-------|------|-------|")
    for family in sorted(per_family.keys()):
        family_counts = per_family[family]
        print(
            f"| {family} | {family_counts.get('ALLOW', 0)} | "
            f"{family_counts.get('HOLD', 0)} | {family_counts.get('BLOCK', 0)} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="T2 candidate model benchmark")
    parser.add_argument("--model", required=True, help="Ollama model tag (e.g. qwen3:8b)")
    args = parser.parse_args()
    model = args.model
    output_path = _output_path(model)

    os.environ["OLLAMA_MODEL"] = model
    t2_config = T2Config(t2_enabled=True)

    records = _load_records(CORPUS_PATH)
    n = len(records)

    overall_all = _empty_verdict_counts()
    overall_genuine = _empty_verdict_counts()
    per_family_all: dict[str, dict[str, int]] = {}
    per_family_genuine: dict[str, dict[str, int]] = {}
    degraded_reasons: dict[str, int] = defaultdict(int)
    results: list[dict[str, object]] = []

    invoked_count = 0
    degraded_count = 0

    for index, record in enumerate(records, 1):
        family = str(record["family"])
        args_dict = _record_to_t0_args(record)
        output = verify(
            args_dict["intent"],
            args_dict["cart"],
            None,
            None,
            t2_config,
        )
        verdict = output.verdict.value

        results.append(
            {
                "family": family,
                "verdict": verdict,
                "invoked": output.invoked,
                "degraded_reason": output.degraded_reason,
                "confidence": output.confidence,
            }
        )

        overall_all[verdict] = overall_all.get(verdict, 0) + 1
        _increment(per_family_all, family, verdict)

        if output.invoked:
            invoked_count += 1
            overall_genuine[verdict] = overall_genuine.get(verdict, 0) + 1
            _increment(per_family_genuine, family, verdict)
        else:
            degraded_count += 1
            reason = output.degraded_reason or "UNKNOWN"
            degraded_reasons[reason] += 1

        if index % 10 == 0 or index == n:
            print(f"Processed {index}/{n}...", flush=True)

    if invoked_count == 0:
        print("ERROR: T2 was called but Ollama returned no invoked=True results.")
        print("All T2 results were degraded. Output file will NOT be written.")
        sys.exit(1)

    timestamp = datetime.now(timezone.utc).isoformat()
    report = {
        "model": model,
        "timestamp": timestamp,
        "corpus_file": str(CORPUS_PATH.relative_to(PROJECT_ROOT)),
        "record_count": n,
        "overall_all_verdicts": overall_all,
        "overall_genuine_model_verdicts": overall_genuine,
        "per_family_all_verdicts": per_family_all,
        "per_family_genuine_model_verdicts": per_family_genuine,
        "invoked_count": invoked_count,
        "degraded_count": degraded_count,
        "degraded_reasons": dict(degraded_reasons),
        "records": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\n=== T2 candidate benchmark ({model}) ===")
    print(f"Corpus: {CORPUS_PATH.name} ({n} records)")
    print(f"Invoked (genuine): {invoked_count}")
    print(f"Degraded/failed:   {degraded_count}")
    if degraded_reasons:
        print("\nDegraded reason breakdown:")
        for reason, count in sorted(degraded_reasons.items()):
            print(f"  {reason}: {count}")

    _print_table(
        "--- Overall T2 verdicts on hard negatives (all records) ---",
        overall_all,
        per_family_all,
        n,
    )
    _print_table(
        "--- Genuine model verdicts (invoked=True only) ---",
        overall_genuine,
        per_family_genuine,
        invoked_count,
    )

    print(f"\nResults written to {output_path}")


if __name__ == "__main__":
    main()
