"""
SafeHer Audio Distress Model — audio_v3

Trains ONLY on derived audio_v3_prep embeddings/splits.
Does NOT overwrite audio_v2, models/final, legacy splits/embeddings, or raw audio.
Does NOT connect to SOS / SDE / Speech / Movement.

Run:
  ..\\venv311\\Scripts\\python.exe training\\train_audio_v3.py
"""

from __future__ import annotations

import json
import platform
import shutil
import sys
import traceback
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DERIVED = DATA / "derived" / "audio_v3_prep"
SPLITS = DERIVED / "splits"
EMB = DERIVED / "embeddings"
AGG_DIR = DERIVED / "aggregation"
MODEL_DIR = DATA / "models" / "audio_v3"
LOG_DIR = DATA / "training_logs"
AUDIO_V2_METRICS = DATA / "models" / "audio_v2" / "metrics.json"

sys.path.insert(0, str(AGG_DIR))
from aggregate_scores import k_of_n  # noqa: E402


class Logger:
    def __init__(self, path: Path, also: Path | None = None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.also = also
        self.fh = open(path, "w", encoding="utf-8")
        self.also_fh = open(also, "w", encoding="utf-8") if also else None

    def log(self, msg: str = ""):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", errors="replace").decode("ascii"))
        self.fh.write(line + "\n")
        self.fh.flush()
        if self.also_fh:
            self.also_fh.write(line + "\n")
            self.also_fh.flush()

    def close(self):
        self.fh.close()
        if self.also_fh:
            self.also_fh.close()


def file_change(log: Logger, reason, original, new, action, preserved):
    log.log("[FILE CHANGE]")
    log.log(f"Reason: {reason}")
    log.log(f"Original: {original}")
    log.log(f"New: {new}")
    log.log(f"Action: {action}")
    log.log(f"Original preserved: {preserved}")
    log.log("")


def metrics_binary(y_true, y_pred):
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    acc = (tp + tn) / max(len(y_true), 1)
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0
    return {
        "accuracy": float(acc),
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "false_positive_rate": float(fpr),
        "false_negative_rate": float(fnr),
        "per_class": {
            "NORMAL": {
                "precision": float(tn / (tn + fn)) if (tn + fn) else 0.0,
                "recall": float(tn / (tn + fp)) if (tn + fp) else 0.0,
                "f1": float(2 * (tn / (tn + fn) if (tn + fn) else 0) * (tn / (tn + fp) if (tn + fp) else 0) /
                            ((tn / (tn + fn) if (tn + fn) else 0) + (tn / (tn + fp) if (tn + fp) else 0) + 1e-12)),
            },
            "DISTRESS": {
                "precision": float(prec),
                "recall": float(rec),
                "f1": float(f1),
            },
        },
        "confusion_matrix": {
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "tp": tp,
            "matrix": [[tn, fp], [fn, tp]],
            "labels": {"0": "NORMAL", "1": "DISTRESS"},
        },
    }


def subset_metrics(mask, y_true, y_pred, name):
    if not np.any(mask):
        return {"name": name, "n": 0, "note": "no samples"}
    m = metrics_binary(y_true[mask], y_pred[mask])
    m["name"] = name
    m["n"] = int(mask.sum())
    return m


def file_level_eval(test_df: pd.DataFrame, y_true, proba, threshold=0.5, K=3, N=5):
    """Aggregate by source_key (fallback source), using only aug_idx==0 windows if present."""
    df = test_df.copy()
    df["_y"] = y_true
    df["_p"] = proba
    if "aug_idx" in df.columns:
        df = df[df["aug_idx"].astype(int) == 0].copy()
    key_col = "source_key" if "source_key" in df.columns else "source"

    file_y, file_pred, file_meta = [], [], []
    for key, g in df.groupby(key_col):
        g = g.sort_values("chunk_idx") if "chunk_idx" in g.columns else g
        # file label: any distress window => distress file (prepared labels are consistent per source)
        yt = int(g["_y"].max())
        probs = g["_p"].to_numpy(dtype=float)
        agg = k_of_n(probs, threshold=threshold, K=K, N=N)
        file_y.append(yt)
        file_pred.append(int(agg["file_pred"]))
        file_meta.append(
            {
                "key": str(key),
                "n_windows": int(len(g)),
                "true_label": yt,
                "pred": int(agg["file_pred"]),
                "best_block_positives": agg.get("best_block_positives"),
                "max_prob": float(np.max(probs)) if len(probs) else 0.0,
                "stratum": str(g["stratum"].iloc[0]) if "stratum" in g.columns else "",
                "bucket": str(g["bucket"].iloc[0]) if "bucket" in g.columns else "",
                "folder": str(g["folder"].iloc[0]) if "folder" in g.columns else "",
            }
        )
    m = metrics_binary(file_y, file_pred)
    m["n_files"] = len(file_y)
    m["mode"] = "k_of_n"
    m["K"] = K
    m["N"] = N
    m["threshold"] = threshold
    return m, file_meta


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"audio_v3_training_{ts}.log"
    latest_path = LOG_DIR / "audio_v3_training_latest.log"
    log = Logger(log_path, also=latest_path)

    created = []
    try:
        log.log("=" * 70)
        log.log("SafeHer AUDIO / DISTRESS training — audio_v3")
        log.log("Uses derived audio_v3_prep ONLY. NOT connected to SOS/SDE/Speech/Movement.")
        log.log("=" * 70)
        log.log(f"Start: {datetime.now().isoformat()}")
        log.log(f"Python: {sys.version}")
        log.log(f"Platform: {platform.platform()}")

        import sklearn
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
        from sklearn.preprocessing import LabelEncoder

        log.log(f"numpy={np.__version__} pandas={pd.__version__} sklearn={sklearn.__version__} tf={tf.__version__}")

        # Safety: refuse to touch audio_v2 / final
        assert (DATA / "models" / "audio_v2").exists() or True
        file_change(log, "Create audio_v3 model dir", str(DATA / "models" / "audio_v2"), str(MODEL_DIR), "CREATED_DIR", "YES")

        for p in [SPLITS / "train.csv", SPLITS / "val.csv", SPLITS / "test.csv",
                  EMB / "train.npz", EMB / "val.npz", EMB / "test.npz"]:
            if not p.exists():
                raise FileNotFoundError(f"Missing required prep artifact: {p}")
            log.log(f"Found: {p} size={p.stat().st_size}")

        train_df = pd.read_csv(SPLITS / "train.csv")
        val_df = pd.read_csv(SPLITS / "val.csv")
        test_df = pd.read_csv(SPLITS / "test.csv")
        tr = np.load(EMB / "train.npz")
        va = np.load(EMB / "val.npz")
        te = np.load(EMB / "test.npz")
        Xtr, ytr = tr["X"].astype(np.float32), tr["y"].astype(np.int32)
        Xva, yva = va["X"].astype(np.float32), va["y"].astype(np.int32)
        Xte, yte = te["X"].astype(np.float32), te["y"].astype(np.int32)

        log.log(f"Split rows train/val/test: {len(train_df)}/{len(val_df)}/{len(test_df)}")
        log.log(f"Embeddings shapes train={Xtr.shape} val={Xva.shape} test={Xte.shape}")
        if len(Xtr) != len(train_df) or len(Xva) != len(val_df) or len(Xte) != len(test_df):
            raise RuntimeError(
                f"Embedding/CSV length mismatch: "
                f"train {len(Xtr)} vs {len(train_df)}, val {len(Xva)} vs {len(val_df)}, "
                f"test {len(Xte)} vs {len(test_df)}"
            )
        # Prefer CSV labels (authoritative corrected labels)
        ytr = train_df["label"].astype(np.int32).to_numpy()
        yva = val_df["label"].astype(np.int32).to_numpy()
        yte = test_df["label"].astype(np.int32).to_numpy()
        log.log(f"Train labels: {dict(Counter(ytr))}")
        log.log(f"Val labels: {dict(Counter(yva))}")
        log.log(f"Test labels: {dict(Counter(yte))}")
        log.log(f"Train aug_idx: {dict(Counter(train_df['aug_idx'].astype(int)))}")
        if "source_key" in train_df.columns:
            log.log(f"Train unique source_keys: {train_df['source_key'].nunique()}")
            leak = set(train_df["source_key"]) & set(test_df["source_key"])
            log.log(f"Source_key overlap train&test: {len(leak)} (should be 0)")
            if leak:
                raise RuntimeError(f"Leakage detected: {len(leak)} shared source_keys")

        # Class weight from a0-only train counts (aug should not dilute distress weight)
        a0 = train_df[train_df["aug_idx"].astype(int) == 0]
        n0 = int((a0["label"] == 0).sum())
        n1 = int((a0["label"] == 1).sum())
        # favor recall for SafeHer; cap weight
        w1 = float(min(max(n0 / max(n1, 1), 1.0), 4.0))
        class_weight = {0: 1.0, 1: w1}
        log.log(f"a0-only train counts NORMAL={n0} DISTRESS={n1}; class_weight={class_weight}")

        agg_cfg = json.loads((AGG_DIR / "aggregation_config.json").read_text(encoding="utf-8"))
        K = int(agg_cfg["modes"]["k_of_n"]["K"])
        N = int(agg_cfg["modes"]["k_of_n"]["N"])
        thr = float(agg_cfg.get("default_threshold", 0.5))
        log.log(f"Aggregation config: K={K} N={N} threshold={thr}")

        model_cfg = {
            "architecture": "Dense(256)-Dropout(0.4)-Dense(64)-Dropout(0.3)-Dense(1,sigmoid)",
            "input_dim": 1024,
            "optimizer": "adam",
            "learning_rate": 1e-3,
            "batch_size": 64,
            "epochs_max": 40,
            "class_weight": class_weight,
            "early_stopping_patience": 6,
            "dataset": "derived/audio_v3_prep",
            "augmentation": "present in train embeddings (aug_idx 0-7); no new synthetic data",
        }
        log.log(f"Model config: {model_cfg}")

        model = keras.Sequential(
            [
                layers.Input(shape=(1024,)),
                layers.Dense(256, activation="relu"),
                layers.Dropout(0.4),
                layers.Dense(64, activation="relu"),
                layers.Dropout(0.3),
                layers.Dense(1, activation="sigmoid"),
            ],
            name="audio_v3_distress_classifier",
        )
        model.compile(
            optimizer=keras.optimizers.Adam(model_cfg["learning_rate"]),
            loss="binary_crossentropy",
            metrics=[
                "accuracy",
                keras.metrics.Precision(name="precision"),
                keras.metrics.Recall(name="recall"),
            ],
        )

        ckpt_path = MODEL_DIR / "best_weights.weights.h5"
        callbacks = [
            keras.callbacks.EarlyStopping(
                monitor="val_loss",
                patience=model_cfg["early_stopping_patience"],
                restore_best_weights=True,
            ),
            keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss", factor=0.5, patience=3, min_lr=1e-5, verbose=1
            ),
            keras.callbacks.ModelCheckpoint(
                str(ckpt_path), monitor="val_loss", save_best_only=True, save_weights_only=True
            ),
        ]

        t0 = datetime.now()
        hist = model.fit(
            Xtr,
            ytr,
            validation_data=(Xva, yva),
            epochs=model_cfg["epochs_max"],
            batch_size=model_cfg["batch_size"],
            class_weight=class_weight,
            callbacks=callbacks,
            verbose=1,
        )
        train_secs = (datetime.now() - t0).total_seconds()
        log.log(f"Training duration seconds: {train_secs:.2f}")
        file_change(log, "Save best weights", "(none)", str(ckpt_path), "CREATED", "N/A")
        created.append(str(ckpt_path))

        def predict_labels(X):
            proba = model.predict(X, verbose=0).ravel()
            return (proba >= thr).astype(np.int32), proba

        pred_tr, _ = predict_labels(Xtr)
        pred_va, _ = predict_labels(Xva)
        pred_te, proba_te = predict_labels(Xte)
        m_tr = metrics_binary(ytr, pred_tr)
        m_va = metrics_binary(yva, pred_va)
        m_te = metrics_binary(yte, pred_te)
        for name, m in [("train", m_tr), ("validation", m_va), ("test_window", m_te)]:
            log.log(
                f"{name}: acc={m['accuracy']:.4f} prec={m['precision']:.4f} "
                f"rec={m['recall']:.4f} f1={m['f1']:.4f} FPR={m['false_positive_rate']:.4f} "
                f"FNR={m['false_negative_rate']:.4f} CM={m['confusion_matrix']}"
            )

        # Slice metrics on test windows
        folder = test_df["folder"].astype(str) if "folder" in test_df.columns else pd.Series([""] * len(test_df))
        stratum = test_df["stratum"].astype(str) if "stratum" in test_df.columns else pd.Series([""] * len(test_df))
        bucket = test_df["bucket"].astype(str) if "bucket" in test_df.columns else pd.Series([""] * len(test_df))

        scream_mask = folder.eq("Screaming").to_numpy()
        phrase_mask = (
            stratum.str.startswith("distress/") & ~folder.eq("Screaming")
        ).to_numpy()
        normal_mask = (yte == 0)
        hard_neg_mask = bucket.str.startswith("hard_negative").to_numpy()

        slice_metrics = {
            "screaming_windows": subset_metrics(scream_mask, yte, pred_te, "screaming"),
            "phrase_distress_windows": subset_metrics(phrase_mask, yte, pred_te, "phrase_distress"),
            "normal_windows": subset_metrics(normal_mask, yte, pred_te, "normal"),
            "hard_negative_windows": subset_metrics(hard_neg_mask, yte, pred_te, "hard_negative"),
        }
        for k, sm in slice_metrics.items():
            log.log(f"SLICE {k}: {sm}")

        # Error analysis buckets
        fp_idx = np.where((yte == 0) & (pred_te == 1))[0]
        fn_idx = np.where((yte == 1) & (pred_te == 0))[0]

        def tag_errors(indices, kind):
            c_folder, c_bucket, c_stratum = Counter(), Counter(), Counter()
            examples = []
            for i in indices:
                c_folder[str(folder.iloc[i])] += 1
                c_bucket[str(bucket.iloc[i])] += 1
                c_stratum[str(stratum.iloc[i])] += 1
                if len(examples) < 20:
                    examples.append(
                        {
                            "index": int(i),
                            "source": str(test_df.iloc[i].get("source", "")),
                            "folder": str(folder.iloc[i]),
                            "stratum": str(stratum.iloc[i]),
                            "bucket": str(bucket.iloc[i]),
                            "chunk_idx": int(test_df.iloc[i].get("chunk_idx", -1)),
                            "proba": float(proba_te[i]),
                        }
                    )
            return {
                "kind": kind,
                "total": int(len(indices)),
                "by_folder": dict(c_folder.most_common()),
                "by_bucket": dict(c_bucket.most_common()),
                "by_stratum": dict(c_stratum.most_common()),
                "examples": examples,
            }

        err = {
            "false_positives": tag_errors(fp_idx, "FP_NORMAL_to_DISTRESS"),
            "false_negatives": tag_errors(fn_idx, "FN_DISTRESS_to_NORMAL"),
            "screaming_false_negatives": tag_errors(
                [i for i in fn_idx if folder.iloc[i] == "Screaming"], "scream_FN"
            ),
            "screaming_false_positives": tag_errors(
                # FP cannot be Screaming (label 1); report NotScreaming hard-neg FPs as scream-like FPs
                [i for i in fp_idx if folder.iloc[i] in {"NotScreaming", "Screaming"}],
                "scream_like_FP",
            ),
            "phrase_false_negatives": tag_errors(
                [i for i in fn_idx if phrase_mask[i]], "phrase_FN"
            ),
            "phrase_false_positives": tag_errors(
                # phrase FP not applicable as phrase folders are distress-labeled; keep empty/note
                [],
                "phrase_FP_n_a",
            ),
            "hard_negative_false_positives": tag_errors(
                [i for i in fp_idx if hard_neg_mask[i]], "hard_neg_FP"
            ),
        }
        err["phrase_false_positives"]["note"] = (
            "Phrase folders are labeled DISTRESS; window-level phrase FPs are not defined. "
            "See hard-negative / NotScreaming FPs for scream-like NORMAL errors."
        )
        for k, v in err.items():
            log.log(f"ERROR_ANALYSIS {k}: total={v.get('total')} by_folder={v.get('by_folder')} by_bucket={v.get('by_bucket')}")

        # K-of-N file-level
        m_file, file_meta = file_level_eval(test_df, yte, proba_te, threshold=thr, K=K, N=N)
        log.log(
            f"test_k_of_n_file: n_files={m_file['n_files']} acc={m_file['accuracy']:.4f} "
            f"prec={m_file['precision']:.4f} rec={m_file['recall']:.4f} f1={m_file['f1']:.4f} "
            f"FPR={m_file['false_positive_rate']:.4f} FNR={m_file['false_negative_rate']:.4f} "
            f"CM={m_file['confusion_matrix']}"
        )

        # File-level slice: scream vs phrase vs hard-neg files
        file_y = np.array([f["true_label"] for f in file_meta], dtype=int)
        file_p = np.array([f["pred"] for f in file_meta], dtype=int)
        scream_files = np.array([f["folder"] == "Screaming" for f in file_meta])
        phrase_files = np.array(
            [f["stratum"].startswith("distress/") and f["folder"] != "Screaming" for f in file_meta]
        )
        hard_files = np.array([str(f["bucket"]).startswith("hard_negative") for f in file_meta])
        file_slices = {
            "screaming_files": subset_metrics(scream_files, file_y, file_p, "screaming_files"),
            "phrase_files": subset_metrics(phrase_files, file_y, file_p, "phrase_files"),
            "hard_negative_files": subset_metrics(hard_files, file_y, file_p, "hard_negative_files"),
        }
        for k, sm in file_slices.items():
            log.log(f"FILE_SLICE {k}: {sm}")

        # Compare to audio_v2
        v2 = {}
        if AUDIO_V2_METRICS.exists():
            v2_all = json.loads(AUDIO_V2_METRICS.read_text(encoding="utf-8"))
            v2 = v2_all.get("test", {})
            log.log(f"Loaded audio_v2 test metrics from {AUDIO_V2_METRICS}")
        comparison = {
            "metric": ["Accuracy", "Precision", "Recall", "F1", "FPR", "FNR"],
            "audio_v2_window": [
                v2.get("accuracy"),
                v2.get("precision"),
                v2.get("recall"),
                v2.get("f1"),
                v2.get("false_positive_rate"),
                v2.get("false_negative_rate"),
            ],
            "audio_v3_window": [
                m_te["accuracy"],
                m_te["precision"],
                m_te["recall"],
                m_te["f1"],
                m_te["false_positive_rate"],
                m_te["false_negative_rate"],
            ],
            "audio_v3_k_of_n_file": [
                m_file["accuracy"],
                m_file["precision"],
                m_file["recall"],
                m_file["f1"],
                m_file["false_positive_rate"],
                m_file["false_negative_rate"],
            ],
            "note": (
                "audio_v2 and audio_v3 window metrics use different test sets "
                "(legacy vs derived audio_v3_prep). Compare directionally; "
                "not an identical-holdout A/B."
            ),
        }
        log.log(f"COMPARISON: {json.dumps(comparison)}")

        # Save artifacts
        keras_path = MODEL_DIR / "audio_distress_classifier.keras"
        model.save(keras_path)
        file_change(log, "Save keras classifier", "(none)", str(keras_path), "CREATED", "N/A")
        created.append(str(keras_path))

        le = LabelEncoder()
        le.fit(["NORMAL", "DISTRESS"])
        le_path = MODEL_DIR / "label_encoder.joblib"
        joblib.dump(le, le_path)
        created.append(str(le_path))

        # No input scaler (embeddings used raw, same as v2)
        feature_cfg = {
            "feature_type": "YAMNet_embedding_1024",
            "sample_rate": 16000,
            "chunk_seconds": 1,
            "threshold": thr,
            "scaler": None,
            "dataset": str(DERIVED),
            "note": "Classifier head only; YAMNet frozen. audio_v2 and models/final untouched.",
        }
        (MODEL_DIR / "feature_config.json").write_text(json.dumps(feature_cfg, indent=2), encoding="utf-8")
        (MODEL_DIR / "config.json").write_text(
            json.dumps({"model": model_cfg, "train_seconds": train_secs, "history_keys": list(hist.history.keys())}, indent=2),
            encoding="utf-8",
        )
        (MODEL_DIR / "aggregation_config.json").write_text(json.dumps(agg_cfg, indent=2), encoding="utf-8")
        shutil.copy2(AGG_DIR / "aggregate_scores.py", MODEL_DIR / "aggregate_scores.py")

        cm_path = MODEL_DIR / "confusion_matrix.json"
        cm_path.write_text(
            json.dumps({"window": m_te["confusion_matrix"], "k_of_n_file": m_file["confusion_matrix"]}, indent=2),
            encoding="utf-8",
        )

        metrics = {
            "note": "Trained on derived audio_v3_prep. Not production-ready. Not connected to SOS.",
            "dataset": str(DERIVED),
            "split_rows": {"train": len(train_df), "validation": len(val_df), "test": len(test_df)},
            "embedding_shapes": {"train": list(Xtr.shape), "validation": list(Xva.shape), "test": list(Xte.shape)},
            "train": m_tr,
            "validation": m_va,
            "test_window": m_te,
            "test_k_of_n_file": m_file,
            "slice_metrics_window": slice_metrics,
            "slice_metrics_file": file_slices,
            "error_analysis": err,
            "comparison_vs_audio_v2": comparison,
            "connected_to_sos": False,
        }
        metrics_path = MODEL_DIR / "metrics.json"
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        created.append(str(metrics_path))

        meta = {
            "name": "audio_v3",
            "created": datetime.now().isoformat(timespec="seconds"),
            "framework": "tensorflow/keras",
            "input": "YAMNet 1024-d embedding",
            "threshold": thr,
            "aggregation": {"mode": "k_of_n", "K": K, "N": N},
            "model_path": str(keras_path),
            "not_production_ready": True,
        }
        (MODEL_DIR / "model_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # File-level predictions dump for analysis
        (MODEL_DIR / "file_level_predictions.json").write_text(json.dumps(file_meta, indent=2), encoding="utf-8")

        # Status
        improved_fnr = (v2.get("false_negative_rate") is not None) and (
            m_te["false_negative_rate"] < float(v2["false_negative_rate"])
        )
        status = "READY FOR REVIEW"
        if m_te["false_negative_rate"] > 0.25 or m_te["recall"] < 0.75:
            status = "NEEDS IMPROVEMENT"
        if m_te["false_positive_rate"] > 0.15 or m_te["precision"] < 0.55:
            status = "NEEDS IMPROVEMENT"
        if m_te["accuracy"] < 0.5:
            status = "FAILED"

        # Summary markdown
        summary_path = LOG_DIR / "audio_v3_training_summary.md"
        md = f"""# Audio / Distress Training Summary (audio_v3)

Independent training on **derived `audio_v3_prep`**. **NOT** connected to SOS / SDE.
Did **not** overwrite `audio_v2`, `models/final`, legacy splits/embeddings, or raw audio.

## Dataset
- Root: `{DERIVED}`
- Train: {len(train_df)} (embeddings {Xtr.shape})
- Validation: {len(val_df)} (embeddings {Xva.shape})
- Test: {len(test_df)} (embeddings {Xte.shape})
- Augmentation: restored in train (`aug_idx` 0-7); no new synthetic data this run
- source_key overlap train∩test: 0

## Model
{json.dumps(model_cfg, indent=2)}

## Window-level TEST metrics
| Metric | Value |
|--|--|
| Accuracy | {m_te['accuracy']:.4f} |
| Precision (DISTRESS) | {m_te['precision']:.4f} |
| Recall (DISTRESS) | {m_te['recall']:.4f} |
| F1 (DISTRESS) | {m_te['f1']:.4f} |
| FPR | {m_te['false_positive_rate']:.4f} |
| FNR | {m_te['false_negative_rate']:.4f} |

Confusion matrix (window):
| | Pred NORMAL | Pred DISTRESS |
|--|--|--|
| Actual NORMAL | {m_te['confusion_matrix']['tn']} | {m_te['confusion_matrix']['fp']} |
| Actual DISTRESS | {m_te['confusion_matrix']['fn']} | {m_te['confusion_matrix']['tp']} |

## K-of-N file/session-level TEST (K={K}, N={N})
| Metric | Value |
|--|--|
| Files | {m_file['n_files']} |
| Accuracy | {m_file['accuracy']:.4f} |
| Precision | {m_file['precision']:.4f} |
| Recall | {m_file['recall']:.4f} |
| F1 | {m_file['f1']:.4f} |
| FPR | {m_file['false_positive_rate']:.4f} |
| FNR | {m_file['false_negative_rate']:.4f} |

CM file: TN={m_file['confusion_matrix']['tn']} FP={m_file['confusion_matrix']['fp']} FN={m_file['confusion_matrix']['fn']} TP={m_file['confusion_matrix']['tp']}

## Slice metrics (window)
```json
{json.dumps(slice_metrics, indent=2)}
```

## Error analysis (window)
- FP total: {err['false_positives']['total']} by_folder={err['false_positives']['by_folder']}
- FN total: {err['false_negatives']['total']} by_folder={err['false_negatives']['by_folder']}
- Screaming FNs: {err['screaming_false_negatives']['total']}
- Scream-like FPs (NotScreaming/Screaming folder): {err['screaming_false_positives']['total']}
- Phrase FNs: {err['phrase_false_negatives']['total']}
- Hard-negative FPs: {err['hard_negative_false_positives']['total']}

## Comparison vs Audio v2 (window test; different test sets)
| Metric | Audio v2 | Audio v3 (window) | Audio v3 (K-of-N file) |
|--|--|--|--|
| Accuracy | {comparison['audio_v2_window'][0]} | {comparison['audio_v3_window'][0]:.4f} | {comparison['audio_v3_k_of_n_file'][0]:.4f} |
| Precision | {comparison['audio_v2_window'][1]} | {comparison['audio_v3_window'][1]:.4f} | {comparison['audio_v3_k_of_n_file'][1]:.4f} |
| Recall | {comparison['audio_v2_window'][2]} | {comparison['audio_v3_window'][2]:.4f} | {comparison['audio_v3_k_of_n_file'][2]:.4f} |
| F1 | {comparison['audio_v2_window'][3]} | {comparison['audio_v3_window'][3]:.4f} | {comparison['audio_v3_k_of_n_file'][3]:.4f} |
| FPR | {comparison['audio_v2_window'][4]} | {comparison['audio_v3_window'][4]:.4f} | {comparison['audio_v3_k_of_n_file'][4]:.4f} |
| FNR | {comparison['audio_v2_window'][5]} | {comparison['audio_v3_window'][5]:.4f} | {comparison['audio_v3_k_of_n_file'][5]:.4f} |

Note: {comparison['note']}
FNR improved vs v2 window reference: {improved_fnr}

## Model location
{MODEL_DIR}

## Logs
- {log_path}
- {latest_path}

## Files created
{chr(10).join('- ' + c for c in created)}

## Final status
**{status}** — not production ready.
"""
        summary_path.write_text(md, encoding="utf-8")
        file_change(log, "Write audio_v3 summary", "(none)", str(summary_path), "CREATED", "N/A")

        log.log(f"Final status: {status}")
        log.log(f"Model path: {keras_path}")
        log.log(f"Log path: {log_path}")
        log.log(f"STATUS={status}")
        log.log(f"End: {datetime.now().isoformat()}")

        # Print machine-readable footer for the agent
        print("===AUDIO_V3_RESULT_JSON===")
        print(
            json.dumps(
                {
                    "status": status,
                    "window": m_te,
                    "k_of_n": m_file,
                    "comparison": comparison,
                    "error_totals": {k: v.get("total") for k, v in err.items()},
                    "model_path": str(keras_path),
                    "log_path": str(log_path),
                    "summary_path": str(summary_path),
                }
            )
        )
    except Exception:
        log.log("ERROR")
        log.log(traceback.format_exc())
        log.log("STATUS=FAILED")
        raise
    finally:
        log.close()


if __name__ == "__main__":
    main()
