"""
Score Balanced-v1 on HUMAN_VERIFIED Gold samples only.

Does NOT retrain, export TFLite, or change production thresholds.

Usage (from safeher_ai/):
    python training/evaluate_gold_thresholds_v1.py
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_gold_eval_v1 import OUT  # noqa: E402
from train_audio_balanced_v1 import (  # noqa: E402
    CHUNK_SAMPLES,
    MODEL_DIR,
    embed_wav,
    get_yamnet,
)

THRESHOLDS = [round(x, 2) for x in np.arange(0.10, 0.91, 0.05)]
VERIFIED_VERDICTS = {"DISTRESS", "NORMAL"}
log = logging.getLogger("gold_eval_v1_eval")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def latest_reviews(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty:
        return df
    df = df.sort_values("review_timestamp")
    return df.groupby("gold_id", as_index=False).tail(1)


def metrics_at(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    preds = (scores >= threshold).astype(int)
    cm = confusion_matrix(y_true, preds, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    spec = float(tn / (tn + fp)) if (tn + fp) else 0.0
    rec = float(tp / (tp + fn)) if (tp + fn) else 0.0
    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y_true, preds)),
        "precision": float(precision_score(y_true, preds, zero_division=0)),
        "distress_recall": rec,
        "f1": float(f1_score(y_true, preds, zero_division=0)),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "specificity": spec,
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "n": int(len(y_true)),
        "n_distress": int((y_true == 1).sum()),
        "n_normal": int((y_true == 0).sum()),
    }


def recommend(rows: list[dict]) -> dict:
    """Report-only. Does not change production threshold."""
    if not rows:
        return {
            "production_threshold_changed": False,
            "note": "No verified samples; no recommendation.",
            "candidates": [],
        }
    # Safety-first: high distress recall, then fewer FPs.
    ranked = sorted(
        rows,
        key=lambda r: (-r["distress_recall"], r["false_positives"], -r["f1"], -r["specificity"]),
    )
    high_recall = [r for r in rows if r["distress_recall"] >= 0.90]
    safer = sorted(
        high_recall,
        key=lambda r: (r["false_positives"], -r["specificity"], -r["f1"]),
    )
    tradeoff = []
    if high_recall:
        best_safe = safer[0]
        tradeoff.append(
            {
                "role": "high_recall_fewer_fp",
                "threshold": best_safe["threshold"],
                "distress_recall": best_safe["distress_recall"],
                "false_positives": best_safe["false_positives"],
                "specificity": best_safe["specificity"],
                "f1": best_safe["f1"],
            }
        )
    rec85 = [r for r in rows if r["distress_recall"] >= 0.85]
    if rec85:
        alt = sorted(rec85, key=lambda r: (r["false_positives"], -r["f1"]))[0]
        tradeoff.append(
            {
                "role": "recall_ge_0.85_fewer_fp",
                "threshold": alt["threshold"],
                "distress_recall": alt["distress_recall"],
                "false_positives": alt["false_positives"],
                "specificity": alt["specificity"],
                "f1": alt["f1"],
            }
        )
    return {
        "production_threshold_changed": False,
        "highest_recall": {
            "threshold": ranked[0]["threshold"],
            "distress_recall": ranked[0]["distress_recall"],
            "false_positives": ranked[0]["false_positives"],
        },
        "candidates": tradeoff,
        "note": (
            "Recommendation only. Production DecisionContract / on-device "
            "threshold must not be changed from this script."
        ),
    }


def write_chart(table: pd.DataFrame, dest: Path) -> None:
    if table.empty:
        return
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(table["threshold"], table["distress_recall"], label="Distress recall", color="#b42318")
    ax1.plot(table["threshold"], table["precision"], label="Precision", color="#175cd3")
    ax1.plot(table["threshold"], table["f1"], label="F1", color="#087443")
    ax1.plot(table["threshold"], table["specificity"], label="Specificity", color="#6941c6")
    ax1.set_xlabel("Decision threshold (Balanced-v1 sigmoid score)")
    ax1.set_ylabel("Rate")
    ax1.set_ylim(0, 1.05)
    ax1.set_xlim(0.10, 0.90)
    ax2 = ax1.twinx()
    ax2.plot(table["threshold"], table["false_positives"], label="False positives", color="#b54708", linestyle="--")
    ax2.plot(table["threshold"], table["false_negatives"], label="False negatives", color="#667085", linestyle="--")
    ax2.set_ylabel("Count")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="center right")
    ax1.set_title("Balanced-v1 threshold sweep on HUMAN_VERIFIED Gold samples")
    fig.tight_layout()
    fig.savefig(dest, dpi=140)
    plt.close(fig)


def evaluate() -> dict:
    cand_path = OUT / "gold_candidates.csv"
    reviews_path = OUT / "gold_reviews.csv"
    if not cand_path.is_file():
        payload = {"status": "NOT_RUN", "reason": "gold_candidates.csv missing", "n_verified": 0}
        (OUT / "threshold_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    candidates = pd.read_csv(cand_path)
    reviews = latest_reviews(reviews_path)
    if reviews.empty:
        payload = {
            "status": "NOT_RUN",
            "reason": "No HUMAN_VERIFIED samples. Official scoring uses reviewed DISTRESS/NORMAL only.",
            "n_verified": 0,
            "n_uncertain": 0,
            "generated_at": utc_now(),
            "production_threshold_changed": False,
        }
        (OUT / "threshold_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        pd.DataFrame(
            columns=[
                "threshold",
                "accuracy",
                "precision",
                "distress_recall",
                "f1",
                "false_positives",
                "false_negatives",
                "specificity",
                "tp",
                "tn",
                "fp",
                "fn",
            ]
        ).to_csv(OUT / "threshold_table.csv", index=False)
        return payload

    merged = candidates.merge(reviews, on="gold_id", how="left")
    merged["HUMAN_VERIFIED"] = merged["manual_verdict"].isin(VERIFIED_VERDICTS)
    merged["human_verification_status"] = merged["manual_verdict"].fillna("UNREVIEWED")
    verified = merged[merged["HUMAN_VERIFIED"]].copy()
    uncertain_n = int((merged["manual_verdict"] == "UNCERTAIN").sum())

    if verified.empty:
        payload = {
            "status": "NOT_RUN",
            "reason": "Reviews exist but none are DISTRESS/NORMAL (UNCERTAIN is not a verified gold label).",
            "n_verified": 0,
            "n_uncertain": uncertain_n,
            "generated_at": utc_now(),
            "production_threshold_changed": False,
        }
        (OUT / "threshold_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    yamnet = get_yamnet()
    import tensorflow as tf

    model_path = MODEL_DIR / "audio_distress_classifier.keras"
    model = tf.keras.models.load_model(str(model_path))
    scores = []
    y_true = []
    scored_rows = []
    for rec in verified.itertuples(index=False):
        path = Path(str(rec.file_path))
        if not path.is_file():
            log.warning("missing verified file %s", path)
            continue
        emb = embed_wav(yamnet, str(path))
        score = float(model.predict(emb.reshape(1, -1), verbose=0).flatten()[0])
        label = 1 if rec.manual_verdict == "DISTRESS" else 0
        scores.append(score)
        y_true.append(label)
        scored_rows.append(
            {
                "gold_id": rec.gold_id,
                "file_path": rec.file_path,
                "source_key": rec.source_key,
                "manual_verdict": rec.manual_verdict,
                "HUMAN_VERIFIED": True,
                "y_true": label,
                "model_score": score,
                "model": "audio_balanced_v1",
                "chunk_samples": CHUNK_SAMPLES,
            }
        )

    if not scored_rows:
        payload = {
            "status": "NOT_RUN",
            "reason": "Verified rows had missing audio files.",
            "n_verified": 0,
            "generated_at": utc_now(),
        }
        (OUT / "threshold_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    scores_a = np.asarray(scores, dtype=np.float32)
    y_a = np.asarray(y_true, dtype=np.int32)
    pd.DataFrame(scored_rows).to_csv(OUT / "verified_scores.csv", index=False)

    table = [metrics_at(y_a, scores_a, t) for t in THRESHOLDS]
    table_df = pd.DataFrame(table)
    table_df.to_csv(OUT / "threshold_table.csv", index=False)
    write_chart(table_df, OUT / "threshold_chart.png")
    rec = recommend(table)
    payload = {
        "status": "OK",
        "generated_at": utc_now(),
        "n_verified": int(len(scored_rows)),
        "n_verified_distress": int((y_a == 1).sum()),
        "n_verified_normal": int((y_a == 0).sum()),
        "n_uncertain": uncertain_n,
        "thresholds": table,
        "recommendation": rec,
        "production_threshold_changed": False,
        "model_path": str(model_path),
        "tflite_exported": False,
        "inference_behavior_changed": False,
    }
    (OUT / "threshold_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(json.dumps(evaluate(), indent=2))


if __name__ == "__main__":
    main()
