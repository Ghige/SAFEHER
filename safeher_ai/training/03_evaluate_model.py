"""
SafeHer — Step 3: Model Evaluation
=====================================

Tests the trained classifier on the held-out test set.
Gives you a full picture before converting to TFLite.

UPDATED for the embedding-based training pipeline (02_train_model.py):
the saved model is now a small classifier that takes a 1024-dim YAMNet
embedding as input, not raw audio. This script extracts embeddings for
the test set the same way 02_train_model.py did (mean-pooled YAMNet
embedding per 1-second chunk), then evaluates the classifier on them.

Outputs:
  - Accuracy, Precision, Recall, F1, AUC
  - Confusion matrix (what it got right/wrong)
  - Per-speaker breakdown (who it failed on)
  - Threshold analysis (what score cutoff works best)

Run AFTER 02_train_model.py:
    python 03_evaluate_model.py --model models/final/safeher_classifier_YYYYMMDD_HHMM.keras
"""

import argparse
import numpy as np
import pandas as pd
import tensorflow as tf
import tensorflow_hub as hub
from pathlib import Path
from tqdm import tqdm
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_auc_score, f1_score, precision_score, recall_score
)

SAMPLE_RATE   = 16000
CHUNK_SAMPLES = SAMPLE_RATE
TEST_CSV      = Path("data/splits/test.csv")
EMBED_DIR     = Path("data/embeddings")
EVAL_DIR      = Path("evaluation")

YAMNET_URL = "https://tfhub.dev/google/yamnet/1"


# ── YAMNet embedding extraction (must match 02_train_model.py exactly) ────────

def get_yamnet():
    print("  Loading YAMNet from TF Hub...")
    return hub.load(YAMNET_URL)


def load_wav(filepath: str) -> np.ndarray:
    audio = tf.io.read_file(filepath)
    audio, _ = tf.audio.decode_wav(audio, desired_channels=1)
    return tf.squeeze(audio, axis=-1).numpy().astype(np.float32)


def embed_file(yamnet, filepath: str) -> np.ndarray:
    waveform = load_wav(filepath)
    if len(waveform) < CHUNK_SAMPLES:
        waveform = np.pad(waveform, (0, CHUNK_SAMPLES - len(waveform)))
    else:
        waveform = waveform[:CHUNK_SAMPLES]
    _, embeddings, _ = yamnet(waveform)
    return embeddings.numpy().mean(axis=0)


def build_or_load_test_embeddings(df: pd.DataFrame) -> np.ndarray:
    cache_path = EMBED_DIR / "test.npz"
    if cache_path.exists():
        print(f"  Loading cached embeddings: {cache_path.name}")
        return np.load(cache_path)["X"]

    yamnet = get_yamnet()
    X = []
    for filepath in tqdm(df["filepath"], desc="  Embedding test set"):
        try:
            X.append(embed_file(yamnet, filepath))
        except Exception as e:
            print(f"  ⚠️  Skipped {filepath}: {e}")
            X.append(np.zeros(1024, dtype=np.float32))

    X = np.array(X, dtype=np.float32)
    EMBED_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(cache_path, X=X, y=df["label"].values)
    print(f"  Cached embeddings → {cache_path}")
    return X


def predict_all(model, X: np.ndarray) -> np.ndarray:
    """Run inference on cached embeddings. Returns raw sigmoid scores."""
    scores = model.predict(X, verbose=0).flatten()
    return scores


def threshold_analysis(labels, scores):
    """Find best threshold balancing precision and recall."""
    print("\n── Threshold Analysis ────────────────────────────────")
    print(f"  {'Threshold':>10}  {'Precision':>10}  {'Recall':>8}  {'F1':>8}")
    print("  " + "-" * 44)

    best_f1, best_threshold = 0, 0.5
    for threshold in np.arange(0.3, 0.8, 0.05):
        preds = (scores >= threshold).astype(int)
        f1    = f1_score(labels, preds, zero_division=0)
        prec  = precision_score(labels, preds, zero_division=0)
        rec   = recall_score(labels, preds, zero_division=0)
        marker = " ← best F1" if f1 > best_f1 else ""
        print(f"  {threshold:>10.2f}  {prec:>10.3f}  {rec:>8.3f}  {f1:>8.3f}{marker}")
        if f1 > best_f1:
            best_f1, best_threshold = f1, threshold

    print(f"\n  Recommended threshold: {best_threshold:.2f}")
    print(f"  (Set DISTRESS_THRESHOLD = {best_threshold * 100:.0f} in inference.py)")
    return best_threshold


def speaker_breakdown(df, scores, threshold):
    """Show per-speaker performance to spot who the model struggles with."""
    preds = (scores >= threshold).astype(int)
    df = df.copy()
    df["score"] = scores
    df["pred"]  = preds

    print("\n── Per-Speaker Breakdown ─────────────────────────────")
    print(f"  {'Speaker':>10}  {'Samples':>8}  {'Distress':>9}  {'Recall':>8}")
    print("  " + "-" * 42)

    for speaker, grp in df.groupby("speaker"):
        if grp["label"].sum() == 0:
            continue   # skip speakers with no distress samples in test set
        distress_grp = grp[grp["label"] == 1]
        recall = (distress_grp["pred"] == 1).mean()
        print(f"  {speaker:>10}  {len(grp):>8}  {len(distress_grp):>9}  {recall:>8.2f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Path to .keras classifier file")
    args = parser.parse_args()

    EVAL_DIR.mkdir(exist_ok=True)

    print("=" * 55)
    print("  SafeHer — Model Evaluation")
    print("=" * 55)

    # Load test data
    df = pd.read_csv(TEST_CSV)
    labels = df["label"].values
    print(f"\n  Test samples : {len(df)}")
    print(f"  Distress     : {labels.sum()}")
    print(f"  Normal       : {(labels == 0).sum()}")

    # Embeddings
    print("\n  Preparing embeddings...")
    X_test = build_or_load_test_embeddings(df)

    # Load classifier
    print(f"\n  Loading model: {args.model}")
    model = tf.keras.models.load_model(args.model)

    # Run inference
    print("\n  Running inference...")
    scores = predict_all(model, X_test)

    # Default threshold = 50
    threshold = 0.50
    preds     = (scores >= threshold).astype(int)

    # ── Core metrics ──────────────────────────────────────────────────────────
    print("\n── Core Metrics (threshold = 0.50) ───────────────────")
    print(classification_report(
        labels, preds,
        target_names=["normal", "distress"],
        digits=3
    ))

    cm  = confusion_matrix(labels, preds)
    auc = roc_auc_score(labels, scores)
    tn, fp, fn, tp = cm.ravel()

    print(f"  AUC           : {auc:.3f}")
    print(f"  True Positives : {tp}  (real distress correctly caught)")
    print(f"  False Negatives: {fn}  (real distress MISSED ← most dangerous)")
    print(f"  False Positives: {fp}  (false alarms)")
    print(f"  True Negatives : {tn}  (correctly quiet)")

    # ── Threshold analysis ────────────────────────────────────────────────────
    best_threshold = threshold_analysis(labels, scores)

    # ── Per-speaker breakdown ─────────────────────────────────────────────────
    speaker_breakdown(df, scores, best_threshold)

    # ── Guidance ──────────────────────────────────────────────────────────────
    best_preds  = (scores >= best_threshold).astype(int)
    best_recall = (best_preds[labels == 1] == 1).mean()
    best_prec   = (best_preds[best_preds == 1] == labels[best_preds == 1]).mean() if best_preds.sum() > 0 else 0

    print("\n── Guidance ──────────────────────────────────────────")
    if best_recall >= 0.90:
        print(f"  ✅ Recall {best_recall:.2f} — model catches 90%+ of real distress")
    elif best_recall >= 0.80:
        print(f"  ⚠️  Recall {best_recall:.2f} — acceptable but collect more distress data")
    else:
        print(f"  ❌ Recall {best_recall:.2f} — too low. Do NOT ship. Collect more data.")

    if best_prec >= 0.85:
        print(f"  ✅ Precision {best_prec:.2f} — low false alarm rate")
    elif best_prec >= 0.70:
        print(f"  ⚠️  Precision {best_prec:.2f} — some false alarms, confirmation window will help")
    else:
        print(f"  ❌ Precision {best_prec:.2f} — too many false alarms. Add more hard negatives.")

    if auc >= 0.92:
        print(f"  ✅ AUC {auc:.3f} — excellent separation")
    elif auc >= 0.85:
        print(f"  ⚠️  AUC {auc:.3f} — good but more data would help")
    else:
        print(f"  ❌ AUC {auc:.3f} — model not separating well. Retrain.")

    print("\n  ▶  Next: python 04_export_tflite.py --model", args.model)
    print("=" * 55)


if __name__ == "__main__":
    main()