"""
Future retraining gate. NEVER trains. NEVER deploys. NEVER mutates model weights.

candidate → review → gold → min-count → leakage → license → approval
→ (human) training → frozen eval → comparison → versioning → manual deploy

Exit 0 = gates documented (not an approval to train).
Exit 2 = gold set is not ready; training remains forbidden.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from gold_policy import (
    FORBIDDEN_GOLD_LABELS,
    GOLD_VERDICTS,
    LICENSE_OK_ALL,
    TARGET_DISTRESS,
    TARGET_HARD_NEGATIVE,
    leakage_pairs,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STAGE6_GOLD = DATA / "training_logs" / "stage6_gold"
REALWORLD_GOLD = DATA / "training_logs" / "realworld_gold"
OUT = DATA / "training_logs" / "retraining_gate_status.json"

PIPELINE = [
    "candidate data",
    "human review",
    "gold dataset",
    "minimum-count checks",
    "leakage checks",
    "license checks",
    "retraining approval",
    "training",
    "frozen evaluation",
    "model comparison",
    "model versioning",
    "manual approval",
    "deployment",
]


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _forbidden_in(rows: list[dict]) -> list[str]:
    bad = []
    for r in rows:
        verdict = (r.get("manual_verdict") or r.get("label") or "").strip()
        if not verdict:
            continue
        if verdict in FORBIDDEN_GOLD_LABELS or verdict not in GOLD_VERDICTS:
            bad.append(f"{r.get('event_id') or r.get('queue_id') or r.get('source_id')}:{verdict}")
    return bad


def evaluate() -> dict:
    s6_distress = _read_csv(STAGE6_GOLD / "confirmed_distress.csv")
    s6_hn = _read_csv(STAGE6_GOLD / "verified_hard_negative.csv")
    rw_distress = _read_csv(REALWORLD_GOLD / "confirmed_distress.csv")
    rw_hn = _read_csv(REALWORLD_GOLD / "verified_hard_negative.csv")

    gold_rows = s6_distress + s6_hn + rw_distress + rw_hn
    forbidden = _forbidden_in(gold_rows)
    leaks = leakage_pairs(gold_rows, id_key="event_id") + leakage_pairs(gold_rows, id_key="source_id")

    license_bad = [
        r for r in gold_rows
        if (r.get("license_status") or "") not in LICENSE_OK_ALL
    ]

    distress_n = len(s6_distress) + len(rw_distress)
    hn_n = len(s6_hn) + len(rw_hn)

    gates = {
        "min_distress": distress_n >= TARGET_DISTRESS,
        "min_hard_negative": hn_n >= TARGET_HARD_NEGATIVE,
        "no_forbidden_labels": len(forbidden) == 0,
        "no_leakage": len(leaks) == 0,
        "license_ok": len(license_bad) == 0,
        "human_retrain_approval": False,
        "training_executed": False,
        "frozen_eval_passed": False,
        "model_comparison_passed": False,
        "manual_deploy_approval": False,
    }
    ready_to_consider_training = all(
        [
            gates["min_distress"],
            gates["min_hard_negative"],
            gates["no_forbidden_labels"],
            gates["no_leakage"],
            gates["license_ok"],
        ]
    )
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "automatic_retrain": False,
        "training_forbidden_this_run": True,
        "pipeline": PIPELINE,
        "counts": {
            "stage6_confirmed_DISTRESS": len(s6_distress),
            "stage6_verified_HARD_NEGATIVE": len(s6_hn),
            "realworld_confirmed_DISTRESS": len(rw_distress),
            "realworld_verified_HARD_NEGATIVE": len(rw_hn),
            "total_DISTRESS": distress_n,
            "total_HARD_NEGATIVE": hn_n,
            "targets": {
                "DISTRESS": TARGET_DISTRESS,
                "HARD_NEGATIVE": TARGET_HARD_NEGATIVE,
            },
        },
        "gates": gates,
        "ready_to_consider_training": ready_to_consider_training,
        "approved_to_train": False,
        "forbidden_label_hits": forbidden[:50],
        "leakage_hits": [list(x) for x in leaks[:50]],
        "rollback_note": "Existing production model artifacts must remain on disk for rollback.",
        "eligible_for_future_training": (
            "Only dual-reviewed DISTRESS and reviewed HARD_NEGATIVE rows in gold CSVs "
            "with license SAFE, ATTRIBUTION_REQUIRED, or USER_CONSENT_OPT_IN. "
            "Currently none of the real-world candidates are gold until humans review them."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="SafeHer retraining gate (no training)")
    parser.add_argument("--approve-train", action="store_true", help="Ignored. Training is never started.")
    args = parser.parse_args()
    report = evaluate()
    print(json.dumps(report, indent=2))
    if args.approve_train:
        print("REFUSED: --approve-train does not start training. Manual offline job required after gates pass.", file=sys.stderr)
    if not report["ready_to_consider_training"]:
        print("TRAINING FORBIDDEN: gold gates not met.", file=sys.stderr)
        return 2
    print("Gold count/leakage/license gates passed on paper. Training still NOT started.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
