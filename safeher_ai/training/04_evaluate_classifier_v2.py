import numpy as np
import tensorflow as tf
from pathlib import Path

from sklearn.metrics import (
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
)

BASE = Path("safeher_ai")

MODEL_PATH = BASE / "models" / "v2" / "safeher_classifier_v2_best.keras"

EMBED_DIR = BASE / "data" / "embeddings_v2"
VAL_PATH = EMBED_DIR / "val.npz"
TEST_PATH = EMBED_DIR / "test.npz"


def load_split(path):
    data = np.load(path)

    X = data["X"].astype(np.float32)
    y = data["y"].astype(np.int32)

    return X, y


def metrics_at_threshold(y_true, scores, threshold):
    preds = (scores >= threshold).astype(np.int32)

    tn, fp, fn, tp = confusion_matrix(
        y_true,
        preds,
        labels=[0, 1]
    ).ravel()

    accuracy = accuracy_score(y_true, preds)

    precision = precision_score(
        y_true,
        preds,
        zero_division=0
    )

    recall = recall_score(
        y_true,
        preds,
        zero_division=0
    )

    f1 = f1_score(
        y_true,
        preds,
        zero_division=0
    )

    specificity = (
        tn / (tn + fp)
        if (tn + fp) > 0
        else 0.0
    )

    return {
        "threshold": threshold,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "specificity": specificity,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
    }


def print_metrics(title, m):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

    print(f"Threshold   : {m['threshold']:.3f}")
    print(f"Accuracy    : {m['accuracy']:.4f}")
    print(f"Precision   : {m['precision']:.4f}")
    print(f"Recall      : {m['recall']:.4f}")
    print(f"F1          : {m['f1']:.4f}")
    print(f"Specificity : {m['specificity']:.4f}")

    print("\nConfusion matrix:")
    print(f"TN: {m['tn']}")
    print(f"FP: {m['fp']}")
    print(f"FN: {m['fn']}")
    print(f"TP: {m['tp']}")


def choose_threshold(y_true, scores):
    print("\n" + "=" * 70)
    print("VALIDATION THRESHOLD ANALYSIS")
    print("=" * 70)

    print(
        f"{'Threshold':>10} "
        f"{'Precision':>10} "
        f"{'Recall':>10} "
        f"{'F1':>10} "
        f"{'Specificity':>12} "
        f"{'FP':>7} "
        f"{'FN':>7}"
    )

    candidates = []

    for threshold in np.arange(0.10, 0.91, 0.05):
        m = metrics_at_threshold(
            y_true,
            scores,
            float(threshold)
        )

        candidates.append(m)

        print(
            f"{threshold:>10.2f} "
            f"{m['precision']:>10.4f} "
            f"{m['recall']:>10.4f} "
            f"{m['f1']:>10.4f} "
            f"{m['specificity']:>12.4f} "
            f"{m['fp']:>7} "
            f"{m['fn']:>7}"
        )

    # SafeHer is safety-oriented.
    # First prefer thresholds that retain >= 90% recall.
    high_recall = [
        m for m in candidates
        if m["recall"] >= 0.90
    ]

    if high_recall:
        best = max(
            high_recall,
            key=lambda m: (
                m["precision"],
                m["f1"],
                m["specificity"]
            )
        )

        reason = (
            "highest precision among tested thresholds "
            "with recall >= 0.90"
        )

    else:
        # If 90% recall cannot be achieved, maximize F2.
        # F2 weights recall more strongly than precision.
        def f2(m):
            p = m["precision"]
            r = m["recall"]

            if p == 0 and r == 0:
                return 0.0

            return (5 * p * r) / ((4 * p) + r)

        best = max(candidates, key=f2)

        reason = (
            "best F2 because no tested threshold "
            "reached 90% recall"
        )

    print("\nRecommended validation threshold:")
    print(f"  {best['threshold']:.2f}")
    print(f"Reason: {reason}")

    return best["threshold"]


def main():
    print("=" * 70)
    print("SAFEHER — V2 CLASSIFIER EVALUATION")
    print("=" * 70)

    print("\nLoading model:")
    print(MODEL_PATH)

    model = tf.keras.models.load_model(MODEL_PATH)

    print("\nLoading validation embeddings...")
    X_val, y_val = load_split(VAL_PATH)

    print("Validation X:", X_val.shape)
    print("Validation y:", y_val.shape)
    print("Distress:", int((y_val == 1).sum()))
    print("Normal  :", int((y_val == 0).sum()))

    print("\nGenerating validation probabilities...")

    val_scores = model.predict(
        X_val,
        batch_size=512,
        verbose=1
    ).reshape(-1)

    val_auc = roc_auc_score(y_val, val_scores)
    val_pr_auc = average_precision_score(y_val, val_scores)

    print("\nValidation threshold-independent metrics:")
    print(f"ROC-AUC : {val_auc:.4f}")
    print(f"PR-AUC  : {val_pr_auc:.4f}")

    default_val = metrics_at_threshold(
        y_val,
        val_scores,
        0.50
    )

    print_metrics(
        "VALIDATION RESULTS — DEFAULT THRESHOLD 0.50",
        default_val
    )

    chosen_threshold = choose_threshold(
        y_val,
        val_scores
    )

    chosen_val = metrics_at_threshold(
        y_val,
        val_scores,
        chosen_threshold
    )

    print_metrics(
        "VALIDATION RESULTS — CHOSEN THRESHOLD",
        chosen_val
    )

    # --------------------------------------------------------
    # TEST SET
    #
    # Threshold is already chosen using validation data.
    # We now evaluate the untouched test set ONCE.
    # --------------------------------------------------------

    print("\nLoading untouched TEST embeddings...")

    X_test, y_test = load_split(TEST_PATH)

    print("Test X:", X_test.shape)
    print("Test y:", y_test.shape)
    print("Distress:", int((y_test == 1).sum()))
    print("Normal  :", int((y_test == 0).sum()))

    print("\nGenerating test probabilities...")

    test_scores = model.predict(
        X_test,
        batch_size=512,
        verbose=1
    ).reshape(-1)

    test_auc = roc_auc_score(
        y_test,
        test_scores
    )

    test_pr_auc = average_precision_score(
        y_test,
        test_scores
    )

    print("\n" + "=" * 70)
    print("TEST — THRESHOLD-INDEPENDENT METRICS")
    print("=" * 70)

    print(f"ROC-AUC : {test_auc:.4f}")
    print(f"PR-AUC  : {test_pr_auc:.4f}")

    default_test = metrics_at_threshold(
        y_test,
        test_scores,
        0.50
    )

    print_metrics(
        "TEST RESULTS — DEFAULT THRESHOLD 0.50",
        default_test
    )

    chosen_test = metrics_at_threshold(
        y_test,
        test_scores,
        chosen_threshold
    )

    print_metrics(
        "FINAL TEST RESULTS — VALIDATION-CHOSEN THRESHOLD",
        chosen_test
    )

    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    print(f"Chosen threshold : {chosen_threshold:.2f}")
    print(f"Test ROC-AUC     : {test_auc:.4f}")
    print(f"Test PR-AUC      : {test_pr_auc:.4f}")
    print(f"Test accuracy    : {chosen_test['accuracy']:.4f}")
    print(f"Test precision   : {chosen_test['precision']:.4f}")
    print(f"Test recall      : {chosen_test['recall']:.4f}")
    print(f"Test F1          : {chosen_test['f1']:.4f}")
    print(f"Test specificity : {chosen_test['specificity']:.4f}")
    print(f"False positives  : {chosen_test['fp']}")
    print(f"False negatives  : {chosen_test['fn']}")

    print("\n✅ V2 evaluation complete.")


if __name__ == "__main__":
    main()
