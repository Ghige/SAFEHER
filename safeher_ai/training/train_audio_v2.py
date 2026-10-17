"""
SafeHer Audio / Distress Model Training — audio_v2

Uses existing YAMNet embedding caches + binary DISTRESS/NORMAL labels.
Does NOT overwrite models/final/* .
Does NOT modify raw WAVs.
Does NOT connect to SOS / SDE.

Run with:
  ..\\venv311\\Scripts\\python.exe training\\train_audio_v2.py
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import traceback
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_DISTRESS = DATA / "raw" / "distress"
RAW_NORMAL = DATA / "raw" / "normal"
SPLITS = DATA / "splits"
EMB = DATA / "embeddings"
MODEL_DIR = DATA / "models" / "audio_v2"
LOG_DIR = DATA / "training_logs"
EXISTING_FINAL = ROOT / "models" / "final"

AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".mpeg"}


class Logger:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(path, "w", encoding="utf-8")

    def log(self, msg: str = ""):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", errors="replace").decode("ascii"))
        self.fh.write(line + "\n")
        self.fh.flush()

    def close(self):
        self.fh.close()


def file_change(log: Logger, reason, original, new, action, preserved):
    log.log("[FILE CHANGE]")
    log.log(f"Reason: {reason}")
    log.log(f"Original: {original}")
    log.log(f"New: {new}")
    log.log(f"Action: {action}")
    log.log(f"Original preserved: {preserved}")
    log.log("")


def list_audio(root: Path):
    if not root.exists():
        return []
    return sorted([p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTS])


def audit_raw(log: Logger):
    import soundfile as sf

    log.log("--- AUDIO DATASET AUDIT ---")
    distress = list_audio(RAW_DISTRESS)
    normal = list_audio(RAW_NORMAL)
    log.log(f"Distress files: {len(distress)}")
    log.log(f"Normal files: {len(normal)}")
    log.log(f"Total audio files: {len(distress) + len(normal)}")

    # subclass counts
    for label, files in [("distress", distress), ("normal", normal)]:
        by_parent = Counter()
        for p in files:
            try:
                rel = p.relative_to(RAW_DISTRESS if label == "distress" else RAW_NORMAL)
                top = rel.parts[0] if len(rel.parts) > 1 else "(root)"
            except Exception:
                top = p.parent.name
            by_parent[top] += 1
        log.log(f"{label} by folder: {dict(by_parent)}")

    # sample-rate / duration stats (sample up to 400 files for speed, plus all if smaller)
    def stats(files, name):
        srs, durs, corrupt, formats = [], [], [], Counter()
        hashes = {}
        dups = []
        sample = files if len(files) <= 500 else files[:: max(1, len(files) // 400)][:400]
        for p in files:
            formats[p.suffix.lower()] += 1
        for p in sample:
            try:
                if p.suffix.lower() != ".wav":
                    # duration via soundfile if possible
                    info = sf.info(str(p))
                    srs.append(info.samplerate)
                    durs.append(info.duration)
                else:
                    info = sf.info(str(p))
                    srs.append(info.samplerate)
                    durs.append(info.duration)
                # hash first 64KB for dup detect on sample
                h = hashlib.md5(p.read_bytes()[:65536]).hexdigest()
                if h in hashes:
                    dups.append((str(hashes[h]), str(p)))
                else:
                    hashes[h] = p
            except Exception as e:
                corrupt.append((str(p), str(e)))
        log.log(f"{name} formats: {dict(formats)}")
        if srs:
            log.log(
                f"{name} sample_rate (sampled {len(srs)}): "
                f"min={min(srs)} max={max(srs)} unique={sorted(set(srs))[:10]}"
            )
            log.log(
                f"{name} duration_sec (sampled): "
                f"min={min(durs):.3f} max={max(durs):.3f} mean={np.mean(durs):.3f}"
            )
        log.log(f"{name} corrupt (in sample): {len(corrupt)}")
        for c in corrupt[:20]:
            log.log(f"  corrupt: {c}")
        log.log(f"{name} possible dups (sample hash): {len(dups)}")
        return {"files": len(files), "formats": dict(formats), "corrupt_sample": len(corrupt), "dup_sample": len(dups)}

    dstat = stats(distress, "distress")
    nstat = stats(normal, "normal")
    return {
        "distress_files": len(distress),
        "normal_files": len(normal),
        "distress": dstat,
        "normal": nstat,
    }


def metrics_binary(y_true, y_pred):
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_recall_fscore_support,
        precision_score,
        recall_score,
    )

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0
    p0, r0, f0, _ = precision_recall_fscore_support(y_true, y_pred, labels=[0], average=None, zero_division=0)
    p1, r1, f1c, _ = precision_recall_fscore_support(y_true, y_pred, labels=[1], average=None, zero_division=0)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "false_positive_rate": float(fpr),
        "false_negative_rate": float(fnr),
        "per_class": {
            "NORMAL": {"precision": float(p0[0]), "recall": float(r0[0]), "f1": float(f0[0])},
            "DISTRESS": {"precision": float(p1[0]), "recall": float(r1[0]), "f1": float(f1c[0])},
        },
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
            "matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
            "labels": {"0": "NORMAL", "1": "DISTRESS"},
        },
    }


def main():
    started = datetime.now()
    stamp = started.strftime("%Y%m%d_%H%M%S")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"audio_training_{stamp}.log"
    latest = LOG_DIR / "audio_training_latest.log"
    log = Logger(log_path)
    status = "FAILED"

    file_change(log, "Create audio_v2 model dir (do not overwrite models/final)", str(EXISTING_FINAL), str(MODEL_DIR), "CREATED_DIR", "YES")
    file_change(log, "Create training logs dir", "(none)", str(LOG_DIR), "CREATED_DIR", "N/A")

    try:
        log.log("=" * 70)
        log.log("SafeHer AUDIO / DISTRESS training — audio_v2")
        log.log("Independent training. NOT connected to SOS/SDE/Speech/Movement fusion.")
        log.log("=" * 70)
        log.log(f"Start: {started.isoformat()}")
        log.log(f"Python: {sys.version}")
        log.log(f"Platform: {platform.platform()}")
        import sklearn
        import tensorflow as tf

        log.log(f"numpy={np.__version__} pandas={pd.__version__} sklearn={sklearn.__version__} tf={tf.__version__}")
        log.log(f"Existing final models (untouched): {list(EXISTING_FINAL.glob('*')) if EXISTING_FINAL.exists() else 'missing'}")

        audit = audit_raw(log)

        # Require existing embeddings + splits (from prior pipeline); do not regenerate raw
        for p in [SPLITS / "train.csv", SPLITS / "val.csv", SPLITS / "test.csv", EMB / "train.npz", EMB / "val.npz", EMB / "test.npz"]:
            if not p.exists():
                raise FileNotFoundError(f"Required artifact missing: {p}. Run existing 01/02 pipeline first.")
            log.log(f"Found: {p} size={p.stat().st_size}")

        train_df = pd.read_csv(SPLITS / "train.csv")
        val_df = pd.read_csv(SPLITS / "val.csv")
        test_df = pd.read_csv(SPLITS / "test.csv")
        log.log(f"Split rows train/val/test: {len(train_df)}/{len(val_df)}/{len(test_df)}")
        log.log(f"Train labels: {dict(train_df['label'].value_counts())}")
        log.log(f"Val labels: {dict(val_df['label'].value_counts())}")
        log.log(f"Test labels: {dict(test_df['label'].value_counts())}")
        if "source" in train_df.columns:
            log.log(f"Train unique sources: {train_df['source'].nunique()}")
            # leakage check: source overlap
            tr_s, te_s = set(train_df["source"]), set(test_df["source"])
            leak = tr_s & te_s
            log.log(f"Source overlap train&test: {len(leak)} (should be 0)")
        if "speaker" in train_df.columns:
            log.log(f"Train speakers: {train_df['speaker'].nunique()} values={train_df['speaker'].value_counts().head().to_dict()}")

        tr = np.load(EMB / "train.npz")
        va = np.load(EMB / "val.npz")
        te = np.load(EMB / "test.npz")
        Xtr, ytr = tr["X"].astype(np.float32), tr["y"].astype(np.int32)
        Xva, yva = va["X"].astype(np.float32), va["y"].astype(np.int32)
        Xte, yte = te["X"].astype(np.float32), te["y"].astype(np.int32)
        log.log(f"Embeddings shapes train={Xtr.shape} val={Xva.shape} test={Xte.shape}")
        assert Xtr.shape[0] == len(train_df)
        assert Xte.shape[0] == len(test_df)

        # Preprocessing note: embeddings already from peak-normalized 1s chunks (01 pipeline)
        log.log("Preprocessing: using existing YAMNet 1024-d embeddings (frozen). Raw WAVs untouched.")
        log.log("Augmentation: none applied in this run (no derived WAV copies created).")

        # Train new head — Dense classifier compatible with existing approach
        from tensorflow import keras
        from tensorflow.keras import layers

        model_cfg = {
            "architecture": "Dense(256)-Dropout(0.4)-Dense(64)-Dropout(0.3)-Dense(1,sigmoid)",
            "input_dim": 1024,
            "optimizer": "adam",
            "learning_rate": 1e-3,
            "batch_size": 32,
            "epochs_max": 40,
            "class_weight": {0: 1.0, 1: 2.0},
            "early_stopping_patience": 6,
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
            ]
        )
        model.compile(
            optimizer=keras.optimizers.Adam(model_cfg["learning_rate"]),
            loss="binary_crossentropy",
            metrics=["accuracy", keras.metrics.Precision(name="precision"), keras.metrics.Recall(name="recall")],
        )

        ckpt_path = MODEL_DIR / "best_weights.weights.h5"
        callbacks = [
            keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=model_cfg["early_stopping_patience"], restore_best_weights=True
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
            class_weight=model_cfg["class_weight"],
            callbacks=callbacks,
            verbose=1,
        )
        train_secs = (datetime.now() - t0).total_seconds()
        log.log(f"Training duration seconds: {train_secs:.2f}")
        file_change(log, "Save best weights", "(none)", str(ckpt_path), "CREATED", "N/A")

        # Evaluate
        def predict_labels(X):
            proba = model.predict(X, verbose=0).ravel()
            return (proba >= 0.5).astype(np.int32), proba

        pred_tr, _ = predict_labels(Xtr)
        pred_va, _ = predict_labels(Xva)
        pred_te, proba_te = predict_labels(Xte)
        m_tr = metrics_binary(ytr, pred_tr)
        m_va = metrics_binary(yva, pred_va)
        m_te = metrics_binary(yte, pred_te)
        for name, m in [("train", m_tr), ("validation", m_va), ("test", m_te)]:
            log.log(
                f"{name}: acc={m['accuracy']:.4f} prec={m['precision']:.4f} "
                f"rec={m['recall']:.4f} f1={m['f1']:.4f} FPR={m['false_positive_rate']:.4f} "
                f"FNR={m['false_negative_rate']:.4f} CM={m['confusion_matrix']}"
            )

        # Error analysis using test CSV metadata if present
        fp_types, fn_types = Counter(), Counter()
        if "source" in test_df.columns:
            for i, (yt, yp) in enumerate(zip(yte, pred_te)):
                src = str(test_df.iloc[i]["source"])
                # infer folderish type from source name
                key = src
                if yt == 0 and yp == 1:
                    fp_types[key] += 1
                elif yt == 1 and yp == 0:
                    fn_types[key] += 1
        # Map source filenames back to raw folder tags when possible
        folder_fp, folder_fn = Counter(), Counter()
        src_map = {}
        for root, kind in [(RAW_DISTRESS, "distress"), (RAW_NORMAL, "normal")]:
            if not root.exists():
                continue
            for p in list_audio(root):
                try:
                    rel = p.relative_to(root)
                    tag = f"{kind}/{(rel.parts[0] if len(rel.parts) > 1 else '(root)')}"
                except Exception:
                    tag = f"{kind}/unknown"
                stem = p.stem
                src_map[p.name.lower()] = tag
                src_map[stem.lower()] = tag
                src_map[(stem + "_out.wav").lower()] = tag
                src_map[(stem + "_out").lower()] = tag
        for i, (yt, yp) in enumerate(zip(yte, pred_te)):
            src = str(test_df.iloc[i]["source"]) if "source" in test_df.columns else ""
            tag = src_map.get(src.lower()) or src_map.get(Path(src).stem.lower())
            if not tag:
                stem = Path(src).stem.lower().replace("_out", "")
                tag = src_map.get(stem)
            if not tag:
                fp = str(test_df.iloc[i].get("filepath", "")).lower()
                tag = "distress/(processed)" if "distress" in fp else ("normal/(processed)" if "normal" in fp else "unknown")
            if yt == 0 and yp == 1:
                folder_fp[tag] += 1
            elif yt == 1 and yp == 0:
                folder_fn[tag] += 1
        log.log(f"FP by path-tag: {dict(folder_fp)}")
        log.log(f"FN by path-tag: {dict(folder_fn)}")

        # Volume robustness note: training used peak-normalized chunks → model not loudness-defined
        log.log("VOLUME NOTE: training embeddings come from peak-normalized chunks; loudness alone is not the label.")
        log.log("LOW-VOLUME / NOISE dedicated test sets: NOT AVAILABLE as separate labeled folders in this run.")

        # Save artifacts
        keras_path = MODEL_DIR / "audio_distress_classifier.keras"
        model.save(keras_path)
        file_change(log, "Save keras classifier head", "(none)", str(keras_path), "CREATED", "N/A")

        # Also save sklearn-compatible report objects
        from sklearn.preprocessing import LabelEncoder
        import joblib

        le = LabelEncoder()
        le.fit(["NORMAL", "DISTRESS"])
        joblib.dump(le, MODEL_DIR / "label_encoder.joblib")
        file_change(log, "Save label encoder", "(none)", str(MODEL_DIR / "label_encoder.joblib"), "CREATED", "N/A")

        # No input scaler — embeddings already used raw; document identity
        feature_cfg = {
            "feature_type": "YAMNet_embedding_1024",
            "sample_rate": 16000,
            "chunk_seconds": 1,
            "threshold": 0.5,
            "note": "Classifier head only; YAMNet frozen. Existing TFLite export in models/final untouched.",
        }
        with open(MODEL_DIR / "feature_config.json", "w", encoding="utf-8") as f:
            json.dump(feature_cfg, f, indent=2)
        with open(MODEL_DIR / "config.json", "w", encoding="utf-8") as f:
            json.dump({"model": model_cfg, "train_seconds": train_secs, "history_keys": list(hist.history.keys())}, f, indent=2)

        metrics = {
            "note": "Trained on existing SafeHer audio splits/embeddings. Do not claim production-ready without real-field validation.",
            "dataset_audit": audit,
            "split_rows": {"train": len(ytr), "validation": len(yva), "test": len(yte)},
            "train": m_tr,
            "validation": m_va,
            "test": m_te,
            "error_analysis_test": {
                "false_positives_NORMAL_to_DISTRESS_by_path_tag": dict(folder_fp),
                "false_negatives_DISTRESS_to_NORMAL_by_path_tag": dict(folder_fn),
                "fp_total": int(m_te["confusion_matrix"]["fp"]),
                "fn_total": int(m_te["confusion_matrix"]["fn"]),
            },
            "connected_to_sos": False,
        }
        with open(MODEL_DIR / "metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        with open(MODEL_DIR / "confusion_matrix.json", "w", encoding="utf-8") as f:
            json.dump(m_te["confusion_matrix"], f, indent=2)
        with open(MODEL_DIR / "model_metadata.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "name": "safeher_audio_v2",
                    "task": "binary NORMAL vs DISTRESS",
                    "artifacts": [p.name for p in MODEL_DIR.iterdir() if p.is_file()],
                    "existing_tflite_untouched": True,
                },
                f,
                indent=2,
            )
        for name in ["feature_config.json", "config.json", "metrics.json", "confusion_matrix.json", "model_metadata.json"]:
            file_change(log, f"Save {name}", "(none)", str(MODEL_DIR / name), "CREATED", "N/A")

        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            cm = np.array(m_te["confusion_matrix"]["matrix"])
            fig, ax = plt.subplots(figsize=(5, 4))
            im = ax.imshow(cm, cmap="Blues")
            ax.set_xticks([0, 1], ["Pred NORMAL", "Pred DISTRESS"])
            ax.set_yticks([0, 1], ["Actual NORMAL", "Actual DISTRESS"])
            for i in range(2):
                for j in range(2):
                    ax.text(j, i, str(cm[i, j]), ha="center", va="center")
            ax.set_title("Audio v2 Test CM")
            fig.colorbar(im, ax=ax, fraction=0.046)
            fig.tight_layout()
            png = MODEL_DIR / "confusion_matrix.png"
            fig.savefig(png, dpi=120)
            plt.close(fig)
            file_change(log, "Save CM PNG", "(none)", str(png), "CREATED", "N/A")
        except Exception as e:
            log.log(f"WARNING: PNG CM failed: {e}")

        # Summary md
        summary_path = LOG_DIR / "audio_training_summary.md"
        cm = m_te["confusion_matrix"]
        summary = f"""# Audio / Distress Training Summary (audio_v2)

Independent training. **NOT** connected to SOS / SDE.
Existing `models/final/*` TFLite artifacts were **not** overwritten.

## Dataset
Distress files: {audit['distress_files']}
Normal files: {audit['normal_files']}
Total: {audit['distress_files'] + audit['normal_files']}
Labels: NORMAL=0, DISTRESS=1 (folder-based; peak-normalized training chunks)

## Split (existing source-level splits + embeddings)
Train: {len(ytr)} windows
Validation: {len(yva)}
Test: {len(yte)}

## Preprocessing
Existing pipeline: 16 kHz mono, 1s chunks, peak-normalize, YAMNet 1024-d embeddings (frozen).
Raw WAVs untouched. No new augmentation in this run.

## Model
{model_cfg}

## Test metrics
Accuracy: {m_te['accuracy']:.6f}
Precision: {m_te['precision']:.6f}
Recall: {m_te['recall']:.6f}
F1: {m_te['f1']:.6f}
FPR: {m_te['false_positive_rate']:.6f}
FNR: {m_te['false_negative_rate']:.6f}

## Confusion Matrix (test)
| | Pred NORMAL | Pred DISTRESS |
|--|--|--|
| Actual NORMAL | {cm['tn']} | {cm['fp']} |
| Actual DISTRESS | {cm['fn']} | {cm['tp']} |

## Per-class
{json.dumps(m_te['per_class'], indent=2)}

## Errors
FP path-tags: {dict(folder_fp)}
FN path-tags: {dict(folder_fn)}

## Limitations
- Metrics from existing processed splits/embeddings; field validation still required.
- Dedicated low-volume / noise stress sets not present as separate labeled folders.
- Loudness is not the training label (peak-normalized), but real-world volume robustness needs targeted tests.

## Model location
{MODEL_DIR}

## Final Status
SUCCESS
"""
        summary_path.write_text(summary, encoding="utf-8")
        file_change(log, "Write audio summary", "(none)", str(summary_path), "CREATED", "N/A")

        report = {
            "status": "SUCCESS",
            "dataset": audit,
            "split": {"train": len(ytr), "validation": len(yva), "test": len(yte)},
            "test_metrics": m_te,
            "model_dir": str(MODEL_DIR),
            "log": str(log_path),
            "summary": str(summary_path),
        }
        (LOG_DIR / "audio_training_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

        status = "SUCCESS"
        log.log(f"Final status: {status}")
        log.log(f"Model path: {keras_path}")
    except Exception:
        log.log("ERROR")
        log.log(traceback.format_exc())
        status = "FAILED"
        raise
    finally:
        log.log(f"STATUS={status}")
        log.close()
        latest.write_text(log_path.read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    main()
