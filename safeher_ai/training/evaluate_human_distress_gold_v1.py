"""
Evaluate Balanced-v1 on HUMAN_VERIFIED Human Distress Gold v1 samples only.

Does NOT retrain, export TFLite, or change the production threshold.

Usage (from safeher_ai/):
    python training/evaluate_human_distress_gold_v1.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_gold_thresholds_v1 import THRESHOLDS, metrics_at, recommend, write_chart  # noqa: E402
from human_distress_gold_v1 import OUT, PRIMARY_EVAL_CATEGORIES, utc_now  # noqa: E402
from train_audio_balanced_v1 import CHUNK_SAMPLES, MODEL_DIR, embed_wav, get_yamnet  # noqa: E402

VERIFIED = {"DISTRESS", "NORMAL"}
log = logging.getLogger("human_distress_gold_v1_eval")


def latest_reviews(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty or "sample_id" not in df.columns:
        return pd.DataFrame()
    return df.sort_values("review_timestamp").groupby("sample_id", as_index=False).tail(1)


def empty_table() -> None:
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


def per_category_recall(verified: pd.DataFrame, scores: np.ndarray, threshold: float) -> dict:
    out = {}
    for cat in PRIMARY_EVAL_CATEGORIES + sorted(
        {c for c in verified.get("eval_category", pd.Series(dtype=str)).astype(str) if c and c not in PRIMARY_EVAL_CATEGORIES}
    ):
        mask = verified["eval_category"].astype(str) == cat
        y = (verified.loc[mask, "manual_verdict"] == "DISTRESS").to_numpy(dtype=int)
        if y.size == 0:
            out[cat] = {"n": 0, "n_distress": 0, "recall": None, "note": "no verified samples"}
            continue
        s = scores[mask.to_numpy()]
        pred = (s >= threshold).astype(int)
        tp = int(((y == 1) & (pred == 1)).sum())
        fn = int(((y == 1) & (pred == 0)).sum())
        n_pos = int((y == 1).sum())
        out[cat] = {
            "n": int(y.size),
            "n_distress": n_pos,
            "recall": float(tp / n_pos) if n_pos else None,
            "false_negatives": fn,
            "enough_for_language_breakout": n_pos >= 5,
        }
    return out


def per_language(verified: pd.DataFrame, scores: np.ndarray, threshold: float) -> dict:
    out = {}
    for lang, part in verified.groupby(verified["language"].fillna("").astype(str)):
        y = (part["manual_verdict"] == "DISTRESS").to_numpy(dtype=int)
        if y.size < 5:
            out[lang or "UNKNOWN"] = {"n": int(y.size), "note": "fewer than 5 verified samples"}
            continue
        s = scores[verified.index.get_indexer(part.index)]
        pred = (s >= threshold).astype(int)
        tp = int(((y == 1) & (pred == 1)).sum())
        fn = int(((y == 1) & (pred == 0)).sum())
        n_pos = int((y == 1).sum())
        out[lang or "UNKNOWN"] = {
            "n": int(y.size),
            "n_distress": n_pos,
            "recall": float(tp / n_pos) if n_pos else None,
            "false_negatives": fn,
        }
    return out


def evaluate() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    cand_path = OUT / "candidates.csv"
    reviews_path = OUT / "reviews.csv"
    if not cand_path.is_file():
        payload = {"status": "NOT_RUN", "reason": "candidates.csv missing", "n_verified": 0}
        (OUT / "threshold_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        empty_table()
        return payload

    candidates = pd.read_csv(cand_path)
    reviews = latest_reviews(reviews_path)
    if reviews.empty:
        payload = {
            "status": "NOT_RUN",
            "reason": "No HUMAN_VERIFIED samples. Official scoring uses reviewed DISTRESS/NORMAL only.",
            "n_verified": 0,
            "generated_at": utc_now(),
            "production_threshold_changed": False,
        }
        (OUT / "threshold_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        empty_table()
        return payload

    merged = candidates.merge(reviews, on="sample_id", how="left")
    merged["HUMAN_VERIFIED"] = merged["manual_verdict"].isin(VERIFIED)
    verified = merged[merged["HUMAN_VERIFIED"]].copy()
    if verified.empty:
        payload = {
            "status": "NOT_RUN",
            "reason": "Reviews exist but none are DISTRESS/NORMAL.",
            "n_verified": 0,
            "n_uncertain": int((merged["manual_verdict"] == "UNCERTAIN").sum()),
            "generated_at": utc_now(),
            "production_threshold_changed": False,
        }
        (OUT / "threshold_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        empty_table()
        return payload

    verified["eval_category"] = verified["confirmed_category"].fillna("").replace("", pd.NA)
    verified["eval_category"] = verified["eval_category"].fillna(verified["phrase_category"])
    verified = verified.reset_index(drop=True)

    yamnet = get_yamnet()
    import tensorflow as tf

    model = tf.keras.models.load_model(str(MODEL_DIR / "audio_distress_classifier.keras"))
    scores = []
    scored_rows = []
    keep_idx = []
    for i, rec in enumerate(verified.itertuples(index=False)):
        path = Path(str(rec.file_path))
        if not path.is_file():
            log.warning("missing %s", path)
            continue
        emb = embed_wav(yamnet, str(path))
        score = float(model.predict(emb.reshape(1, -1), verbose=0).flatten()[0])
        scores.append(score)
        keep_idx.append(i)
        scored_rows.append(
            {
                "sample_id": rec.sample_id,
                "file_path": rec.file_path,
                "manual_verdict": rec.manual_verdict,
                "eval_category": rec.eval_category,
                "language": rec.language,
                "HUMAN_VERIFIED": True,
                "y_true": 1 if rec.manual_verdict == "DISTRESS" else 0,
                "model_score": score,
                "model": "audio_balanced_v1",
                "chunk_samples": CHUNK_SAMPLES,
            }
        )

    if not scored_rows:
        payload = {"status": "NOT_RUN", "reason": "Verified rows had missing audio.", "n_verified": 0}
        (OUT / "threshold_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        empty_table()
        return payload

    verified = verified.iloc[keep_idx].reset_index(drop=True)
    scores_a = np.asarray(scores, dtype=np.float32)
    y_a = np.asarray([1 if v == "DISTRESS" else 0 for v in verified["manual_verdict"]], dtype=np.int32)
    pd.DataFrame(scored_rows).to_csv(OUT / "verified_scores.csv", index=False)

    table = [metrics_at(y_a, scores_a, t) for t in THRESHOLDS]
    table_df = pd.DataFrame(table)
    table_df.to_csv(OUT / "threshold_table.csv", index=False)
    write_chart(table_df, OUT / "threshold_chart.png")

    mid = next((r for r in table if abs(r["threshold"] - 0.50) < 1e-9), table[0])
    payload = {
        "status": "OK",
        "generated_at": utc_now(),
        "n_verified": int(len(scored_rows)),
        "n_verified_distress": int((y_a == 1).sum()),
        "n_verified_normal": int((y_a == 0).sum()),
        "thresholds": table,
        "per_category_recall_at_0_50": per_category_recall(verified, scores_a, 0.50),
        "per_language_at_0_50": per_language(verified, scores_a, 0.50),
        "recommendation": recommend(table),
        "reference_threshold_row": mid,
        "production_threshold_changed": False,
        "tflite_exported": False,
        "combined_with_training": False,
        "model_path": str(MODEL_DIR / "audio_distress_classifier.keras"),
    }
    (OUT / "threshold_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(json.dumps(evaluate(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
