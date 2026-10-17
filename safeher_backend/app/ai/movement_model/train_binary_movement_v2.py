"""
SafeHer Movement Model — Binary NORMAL/ABNORMAL training (v2)

Uses EXISTING dataset under data/normal, data/abnormal, data/features_cache.
Does NOT delete or modify original CSVs.
Does NOT overwrite data/models/* baseline artifacts.
Saves new artifacts to data/models/movement_v2/.

IMPORTANT: Dataset is SYNTHETIC. Metrics are NOT real-world SafeHer performance.
Does NOT wire this model into SOS.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.preprocessing import LabelEncoder, StandardScaler

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
NORMAL = DATA / "normal"
ABNORMAL = DATA / "abnormal"
META = DATA / "metadata" / "sessions.csv"
CACHE = DATA / "features_cache"
MODELS_V2 = DATA / "models" / "movement_v2"
LOG_DIR = DATA / "training_logs"

REQUIRED_COLS = [
    "timestamp",
    "accel_x",
    "accel_y",
    "accel_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "label",
    "session_id",
]

# Same participant split as existing baseline (documented, no leakage)
TRAIN_P = ["P001", "P002", "P003", "P004", "P005", "P006", "P007"]
VAL_P = ["P008", "P009"]
TEST_P = ["P010"]

# Feature layout matching cached X.shape[-1] == 49
# 7 channels × 7 stats (documented reconstruction of existing cache)
CHANNELS = ["accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z", "accel_mag"]
STATS = ["mean", "std", "var", "rms", "min", "max", "ptp"]
FEATURE_NAMES = [f"{ch}_{st}" for ch in CHANNELS for st in STATS]  # 49

WINDOW_SAMPLES = 100
HOP_SAMPLES = 50


class TeeLogger:
    def __init__(self, path: Path):
        self.path = path
        self._fh = open(path, "w", encoding="utf-8")

    def log(self, msg: str = ""):
        line = msg if isinstance(msg, str) else str(msg)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        out = f"[{ts}] {line}"
        print(out)
        self._fh.write(out + "\n")
        self._fh.flush()

    def close(self):
        self._fh.close()


def file_change(log: TeeLogger, reason: str, original: str, new: str, action: str, preserved: str):
    log.log("[FILE CHANGE]")
    log.log(f"Reason: {reason}")
    log.log(f"Original: {original}")
    log.log(f"New: {new}")
    log.log(f"Action: {action}")
    log.log(f"Original preserved: {preserved}")
    log.log("")


def validate_csv(path: Path) -> tuple[bool, str]:
    try:
        if path.stat().st_size == 0:
            return False, "empty_file"
        df = pd.read_csv(path)
        if df.empty:
            return False, "no_rows"
        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            return False, f"missing_columns:{missing}"
        sens = REQUIRED_COLS[1:7]
        if df[sens].isna().any().any():
            return False, "nan_sensor_values"
        if np.isinf(df[sens].to_numpy(dtype=float)).any():
            return False, "inf_sensor_values"
        if len(df) < WINDOW_SAMPLES:
            return False, f"too_short:{len(df)}"
        ts = df["timestamp"].to_numpy()
        if pd.isna(ts).any():
            return False, "nan_timestamps"
        if len(np.unique(ts)) < len(ts) * 0.95:
            # allow tiny dups but flag heavy duplication
            n_dup = len(ts) - len(np.unique(ts))
            if n_dup > max(5, len(ts) * 0.05):
                return False, f"duplicate_timestamps:{n_dup}"
        return True, "ok"
    except Exception as e:
        return False, f"exception:{e}"


def load_cached_features(sessions: pd.DataFrame, log: TeeLogger):
    Xs, ys, parts, acts, sids = [], [], [], [], []
    missing_cache = 0
    bad_cache = 0
    for _, row in sessions.iterrows():
        sid = row["session_id"]
        npz_path = CACHE / f"{sid}.npz"
        if not npz_path.exists():
            missing_cache += 1
            continue
        try:
            z = np.load(npz_path, allow_pickle=True)
            X = z["X"].astype(np.float32)
            y = z["y"].astype(np.int8)
            if X.ndim != 2 or X.shape[1] != 49:
                bad_cache += 1
                log.log(f"WARNING: bad feature shape {npz_path} {getattr(X, 'shape', None)}")
                continue
            if np.isnan(X).any() or np.isinf(X).any():
                bad_cache += 1
                log.log(f"WARNING: nan/inf in features {npz_path}")
                continue
            n = X.shape[0]
            Xs.append(X)
            ys.append(y)
            parts.extend([str(z["participant"])] * n)
            acts.extend([str(z["activity"])] * n)
            sids.extend([sid] * n)
        except Exception as e:
            bad_cache += 1
            log.log(f"WARNING: failed loading cache {npz_path}: {e}")
    log.log(f"Feature cache missing: {missing_cache}, bad: {bad_cache}")
    if not Xs:
        raise RuntimeError("No usable feature windows loaded from cache")
    return (
        np.vstack(Xs),
        np.concatenate(ys),
        np.array(parts),
        np.array(acts),
        np.array(sids),
    )


def metrics_block(y_true, y_pred) -> dict:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0
    return {
        "windows": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "false_positive_rate": float(fpr),
        "false_negative_rate": float(fnr),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
            "labels": {"0": "NORMAL", "1": "ABNORMAL"},
            "matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
        },
    }


def error_analysis(y_true, y_pred, activities) -> dict:
    fp_acts = Counter()
    fn_acts = Counter()
    for yt, yp, act in zip(y_true, y_pred, activities):
        if yt == 0 and yp == 1:
            fp_acts[str(act)] += 1
        elif yt == 1 and yp == 0:
            fn_acts[str(act)] += 1
    return {
        "false_positives_NORMAL_to_ABNORMAL_by_activity": dict(fp_acts.most_common()),
        "false_negatives_ABNORMAL_to_NORMAL_by_activity": dict(fn_acts.most_common()),
        "fp_total": int(sum(fp_acts.values())),
        "fn_total": int(sum(fn_acts.values())),
    }


def validate_all_sessions(sessions: pd.DataFrame, log: TeeLogger):
    from concurrent.futures import ThreadPoolExecutor, as_completed

    valid, invalid = [], []
    skip_reasons = Counter()

    def _one(row):
        rel = str(row["path"]).replace("/", os.sep)
        path = DATA / rel
        if not path.exists():
            return False, str(path), "missing_file"
        ok, reason = validate_csv(path)
        return ok, str(path), reason

    rows = [row for _, row in sessions.iterrows()]
    log.log(f"Validating {len(rows)} CSV files (parallel)...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(_one, row) for row in rows]
        for i, fut in enumerate(as_completed(futs), 1):
            ok, path, reason = fut.result()
            if ok:
                valid.append(path)
            else:
                skip_reasons[reason.split(":")[0]] += 1
                invalid.append((path, reason))
            if i % 1000 == 0:
                log.log(f"  validated {i}/{len(rows)}")
    return valid, invalid, skip_reasons


def main():
    started = datetime.now()
    stamp = started.strftime("%Y%m%d_%H%M%S")

    # [FILE CHANGE] create log dirs
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_V2.mkdir(parents=True, exist_ok=True)

    log_path = LOG_DIR / f"movement_training_{stamp}.log"
    latest_path = LOG_DIR / "movement_training_latest.log"
    log = TeeLogger(log_path)

    file_change(
        log,
        reason="Create permanent training log directory and versioned model output dir",
        original="(none)",
        new=str(LOG_DIR),
        action="CREATED_DIR",
        preserved="N/A",
    )
    file_change(
        log,
        reason="New model artifacts must not overwrite baseline models/",
        original=str(DATA / "models"),
        new=str(MODELS_V2),
        action="CREATED_DIR",
        preserved="YES (baseline untouched)",
    )

    status = "FAILED"
    try:
        log.log("=" * 70)
        log.log("SafeHer Movement Model Training v2")
        log.log("SYNTHETIC DATA — metrics are NOT real-world performance")
        log.log("=" * 70)
        log.log(f"Start time: {started.isoformat()}")
        log.log(f"Python: {sys.version}")
        log.log(f"CWD: {os.getcwd()}")
        log.log(f"DATA root: {DATA}")

        import sklearn
        import platform

        log.log(f"Platform: {platform.platform()}")
        log.log(f"numpy: {np.__version__}")
        log.log(f"pandas: {pd.__version__}")
        log.log(f"sklearn: {sklearn.__version__}")
        log.log(f"joblib: {joblib.__version__}")

        # ── Dataset inventory ──────────────────────────────────────────────
        if not META.exists():
            raise FileNotFoundError(f"Missing metadata: {META}")
        sessions = pd.read_csv(META)
        log.log(f"Metadata rows: {len(sessions)}")
        log.log(f"Class distribution: {sessions['class'].value_counts().to_dict()}")
        log.log(f"Participants: {sorted(sessions['participant_id'].unique())}")
        log.log(f"Synthetic flag unique: {sessions['synthetic'].unique().tolist()}")
        log.log(f"Activities: {sessions.groupby(['class','activity_label']).size().to_dict()}")

        n_normal_files = sum(1 for _ in NORMAL.rglob("*.csv"))
        n_abnormal_files = sum(1 for _ in ABNORMAL.rglob("*.csv"))
        log.log(f"CSV files under normal/: {n_normal_files}")
        log.log(f"CSV files under abnormal/: {n_abnormal_files}")
        log.log(f"Feature cache NPZ count: {len(list(CACHE.glob('*.npz')))}")

        # ── Validation ─────────────────────────────────────────────────────
        log.log("--- DATA VALIDATION ---")
        valid, invalid, skip_reasons = validate_all_sessions(sessions, log)

        report_path = LOG_DIR / "data_validation_report.txt"
        with open(report_path, "w", encoding="utf-8") as rf:
            rf.write("SafeHer Movement Data Validation Report\n")
            rf.write(f"Generated: {datetime.now().isoformat()}\n")
            rf.write("NOTE: Dataset is SYNTHETIC.\n\n")
            rf.write(f"Total sessions (metadata): {len(sessions)}\n")
            rf.write(f"Valid files: {len(valid)}\n")
            rf.write(f"Invalid/skipped files: {len(invalid)}\n")
            rf.write("Skip reasons:\n")
            for k, v in skip_reasons.most_common():
                rf.write(f"  {k}: {v}\n")
            if invalid:
                rf.write("\nInvalid details (first 200):\n")
                for p, r in invalid[:200]:
                    rf.write(f"  {p} -> {r}\n")
        file_change(
            log,
            reason="Validation report required by training protocol",
            original="(none)",
            new=str(report_path),
            action="CREATED",
            preserved="N/A",
        )
        log.log(f"Valid files: {len(valid)} / Invalid: {len(invalid)}")
        log.log(f"Skip reasons: {dict(skip_reasons)}")
        if len(valid) == 0:
            raise RuntimeError("No valid sensor files")

        # Keep only sessions with valid CSV
        valid_set = set(Path(p).name for p in valid)
        sessions_ok = sessions[sessions["session_id"].map(lambda s: f"{s}.csv" in valid_set)].copy()
        log.log(f"Sessions after validation filter: {len(sessions_ok)}")

        # ── Features from existing cache (no overwrite of original CSVs) ───
        log.log("--- FEATURE LOADING (existing features_cache) ---")
        log.log("Preprocessing: NONE on raw CSVs (originals untouched)")
        log.log(f"Using cached windows: window={WINDOW_SAMPLES}, hop={HOP_SAMPLES}, dims=49")
        log.log(f"Feature names ({len(FEATURE_NAMES)}): {FEATURE_NAMES}")

        X, y, participants, activities, session_ids = load_cached_features(sessions_ok, log)
        log.log(f"Total windows: {len(y)}")
        log.log(f"Label distribution (0=NORMAL,1=ABNORMAL): {dict(Counter(y.tolist()))}")

        # ── Split by participant ───────────────────────────────────────────
        log.log("--- SPLIT (participant-level) ---")
        log.log(f"Train participants: {TRAIN_P}")
        log.log(f"Val participants: {VAL_P}")
        log.log(f"Test participants: {TEST_P}")

        def mask(plist):
            return np.isin(participants, plist)

        m_tr, m_va, m_te = mask(TRAIN_P), mask(VAL_P), mask(TEST_P)
        Xtr, ytr, atr, str_ = X[m_tr], y[m_tr], activities[m_tr], session_ids[m_tr]
        Xva, yva, ava, sva = X[m_va], y[m_va], activities[m_va], session_ids[m_va]
        Xte, yte, ate, ste = X[m_te], y[m_te], activities[m_te], session_ids[m_te]

        log.log(f"train: windows={len(ytr)} sessions={len(set(str_))} labels={dict(Counter(ytr.tolist()))}")
        log.log(f"val:   windows={len(yva)} sessions={len(set(sva))} labels={dict(Counter(yva.tolist()))}")
        log.log(f"test:  windows={len(yte)} sessions={len(set(ste))} labels={dict(Counter(yte.tolist()))}")
        log.log(f"train sessions count: {len(set(str_))}, val: {len(set(sva))}, test: {len(set(ste))}")
        log.log(f"test participants: {TEST_P}")

        # ── Scale (fit on train only) ──────────────────────────────────────
        log.log("--- SCALER ---")
        scaler = StandardScaler()
        Xtr_s = scaler.fit_transform(Xtr)
        Xva_s = scaler.transform(Xva)
        Xte_s = scaler.transform(Xte)

        # ── Train ──────────────────────────────────────────────────────────
        log.log("--- MODEL TRAINING ---")
        model_cfg = {
            "model": "RandomForestClassifier",
            "n_estimators": 200,
            "max_depth": 24,
            "min_samples_leaf": 2,
            "class_weight": "balanced_subsample",
            "random_state": 42,
            "n_jobs": -1,
            "note": "v2 retrain on synthetic cache; does not overwrite baseline RF",
        }
        log.log(f"Model config: {model_cfg}")
        clf = RandomForestClassifier(
            n_estimators=model_cfg["n_estimators"],
            max_depth=model_cfg["max_depth"],
            min_samples_leaf=model_cfg["min_samples_leaf"],
            class_weight=model_cfg["class_weight"],
            random_state=model_cfg["random_state"],
            n_jobs=model_cfg["n_jobs"],
        )
        t0 = datetime.now()
        clf.fit(Xtr_s, ytr)
        train_seconds = (datetime.now() - t0).total_seconds()
        log.log(f"Training duration seconds: {train_seconds:.2f}")

        label_encoder = LabelEncoder()
        label_encoder.fit(["NORMAL", "ABNORMAL"])

        # ── Evaluate ───────────────────────────────────────────────────────
        log.log("--- EVALUATION ---")
        pred_tr = clf.predict(Xtr_s)
        pred_va = clf.predict(Xva_s)
        pred_te = clf.predict(Xte_s)

        metrics = {
            "note": (
                "SYNTHETIC DATA RESULTS — NOT real user data. "
                "Do NOT treat these metrics as real-world SafeHer performance. "
                "Real-device recordings are required for final validation."
            ),
            "synthetic": True,
            "model": model_cfg,
            "window_samples": WINDOW_SAMPLES,
            "hop_samples": HOP_SAMPLES,
            "feature_names": FEATURE_NAMES,
            "n_features": 49,
            "split": {
                "strategy": "participant-level (never window-level leakage)",
                "train_participants": TRAIN_P,
                "val_participants": VAL_P,
                "test_participants": TEST_P,
            },
            "counts": {
                "train_windows": int(len(ytr)),
                "val_windows": int(len(yva)),
                "test_windows": int(len(yte)),
                "train_sessions": int(len(set(str_))),
                "val_sessions": int(len(set(sva))),
                "test_sessions": int(len(set(ste))),
                "test_participants": len(TEST_P),
                "normal_sessions_dataset": int((sessions["class"] == "NORMAL").sum()),
                "abnormal_sessions_dataset": int((sessions["class"] == "ABNORMAL").sum()),
                "total_sessions_dataset": int(len(sessions)),
            },
            "train": metrics_block(ytr, pred_tr),
            "validation": metrics_block(yva, pred_va),
            "test": metrics_block(yte, pred_te),
            "error_analysis_test": error_analysis(yte, pred_te, ate),
            "training_duration_seconds": train_seconds,
            "sos_integration": "NOT CONNECTED — evaluate independently first",
        }

        for split_name in ("train", "validation", "test"):
            m = metrics[split_name]
            log.log(
                f"{split_name}: acc={m['accuracy']:.6f} prec={m['precision']:.6f} "
                f"rec={m['recall']:.6f} f1={m['f1']:.6f} FPR={m['false_positive_rate']:.6f} "
                f"FNR={m['false_negative_rate']:.6f} CM={m['confusion_matrix']}"
            )
        log.log(f"Test error analysis: {metrics['error_analysis_test']}")

        # ── Save artifacts (new dir only) ──────────────────────────────────
        log.log("--- SAVE ARTIFACTS ---")
        paths = {
            "model": MODELS_V2 / "movement_model.joblib",
            "scaler": MODELS_V2 / "scaler.joblib",
            "label_encoder": MODELS_V2 / "label_encoder.joblib",
            "metrics": MODELS_V2 / "metrics.json",
            "config": MODELS_V2 / "config.json",
            "feature_config": MODELS_V2 / "feature_config.json",
            "confusion_matrix": MODELS_V2 / "confusion_matrix.json",
            "error_analysis": MODELS_V2 / "error_analysis.json",
            "synthetic_notice": MODELS_V2 / "SYNTHETIC.txt",
            "metadata": MODELS_V2 / "model_metadata.json",
        }

        joblib.dump(clf, paths["model"])
        joblib.dump(scaler, paths["scaler"])
        joblib.dump(label_encoder, paths["label_encoder"])
        file_change(log, "Save v2 RF model", "(none)", str(paths["model"]), "CREATED", "N/A")
        file_change(log, "Save v2 scaler fitted on train only", "(none)", str(paths["scaler"]), "CREATED", "N/A")
        file_change(log, "Save label encoder", "(none)", str(paths["label_encoder"]), "CREATED", "N/A")

        with open(paths["metrics"], "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        file_change(log, "Save metrics JSON", "(none)", str(paths["metrics"]), "CREATED", "N/A")

        config = {
            "version": "movement_v2",
            "created": datetime.now().isoformat(),
            "data_root": str(DATA),
            "raw_data_untouched": True,
            "baseline_models_untouched": True,
            "window_samples": WINDOW_SAMPLES,
            "hop_samples": HOP_SAMPLES,
            "model": model_cfg,
            "split": metrics["split"],
            "synthetic": True,
            "connected_to_sos": False,
        }
        with open(paths["config"], "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        with open(paths["feature_config"], "w", encoding="utf-8") as f:
            json.dump(
                {
                    "n_features": 49,
                    "feature_names": FEATURE_NAMES,
                    "source": "existing features_cache/*.npz",
                    "channels": CHANNELS,
                    "stats": STATS,
                    "sensor_columns_raw": REQUIRED_COLS[1:7],
                },
                f,
                indent=2,
            )
        with open(paths["confusion_matrix"], "w", encoding="utf-8") as f:
            json.dump(
                {
                    "test": metrics["test"]["confusion_matrix"],
                    "validation": metrics["validation"]["confusion_matrix"],
                    "format": "[[TN, FP], [FN, TP]] with 0=NORMAL 1=ABNORMAL",
                },
                f,
                indent=2,
            )
        with open(paths["error_analysis"], "w", encoding="utf-8") as f:
            json.dump(metrics["error_analysis_test"], f, indent=2)
        with open(paths["synthetic_notice"], "w", encoding="utf-8") as f:
            f.write(
                "SYNTHETIC DATA RESULTS\n"
                "This model was trained only on generated IMU-like time series.\n"
                "Do NOT treat accuracy as real-world SafeHer performance.\n"
                "Collect real-device accelerometer/gyroscope recordings before production use.\n"
                "This model is NOT connected to automatic SOS.\n"
            )
        with open(paths["metadata"], "w", encoding="utf-8") as f:
            json.dump(
                {
                    "name": "safeher_movement_v2",
                    "task": "binary NORMAL vs ABNORMAL",
                    "framework": "scikit-learn RandomForestClassifier",
                    "artifacts": {k: str(v.name) for k, v in paths.items()},
                    "log_file": str(log_path),
                },
                f,
                indent=2,
            )
        for key in ("config", "feature_config", "confusion_matrix", "error_analysis", "synthetic_notice", "metadata"):
            file_change(log, f"Save {key}", "(none)", str(paths[key]), "CREATED", "N/A")

        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            cm = np.array(metrics["test"]["confusion_matrix"]["matrix"])
            fig, ax = plt.subplots(figsize=(5, 4))
            im = ax.imshow(cm, cmap="Blues")
            ax.set_xticks([0, 1], ["Pred NORMAL", "Pred ABNORMAL"])
            ax.set_yticks([0, 1], ["Actual NORMAL", "Actual ABNORMAL"])
            for i in range(2):
                for j in range(2):
                    ax.text(j, i, str(cm[i, j]), ha="center", va="center", color="black")
            ax.set_title("Test CM (SYNTHETIC)")
            fig.colorbar(im, ax=ax, fraction=0.046)
            png_path = MODELS_V2 / "confusion_matrix.png"
            fig.tight_layout()
            fig.savefig(png_path, dpi=120)
            plt.close(fig)
            file_change(log, "Save confusion matrix PNG", "(none)", str(png_path), "CREATED", "N/A")
        except Exception as e:
            log.log(f"WARNING: could not write confusion_matrix.png: {e}")

        summary_path = LOG_DIR / "movement_training_summary.md"
        te = metrics["test"]
        ea = metrics["error_analysis_test"]
        cm = te["confusion_matrix"]
        summary = f"""# SafeHer Movement Training Summary (v2)

**SYNTHETIC DATA RESULTS — NOT real-world SafeHer performance.**
Real-device recordings are required for final validation.
This model is **NOT** connected to automatic SOS.

## Dataset
Total files/sessions: {len(sessions)}
Normal: {(sessions['class']=='NORMAL').sum()}
Abnormal: {(sessions['class']=='ABNORMAL').sum()}
Valid CSVs: {len(valid)}
Invalid/skipped: {len(invalid)}

## Split (participant-level)
Train: participants {TRAIN_P} — windows {len(ytr)}, sessions {len(set(str_))}
Validation: participants {VAL_P} — windows {len(yva)}, sessions {len(set(sva))}
Test: participants {TEST_P} — windows {len(yte)}, sessions {len(set(ste))}

## Model
Architecture: RandomForestClassifier (n_estimators={model_cfg['n_estimators']}, max_depth={model_cfg['max_depth']})
Features: 49 cached window stats from accel/gyro (+ accel magnitude reconstruction names)
Hyperparameters: {json.dumps(model_cfg)}

## Results (TEST — SYNTHETIC)
Accuracy: {te['accuracy']:.6f}
Precision: {te['precision']:.6f}
Recall: {te['recall']:.6f}
F1: {te['f1']:.6f}
FPR: {te['false_positive_rate']:.6f}
FNR: {te['false_negative_rate']:.6f}

## Confusion Matrix (test)
|  | Pred NORMAL | Pred ABNORMAL |
|--|--|--|
| Actual NORMAL | {cm['tn']} | {cm['fp']} |
| Actual ABNORMAL | {cm['fn']} | {cm['tp']} |

## Errors (test)
False positives (NORMAL→ABNORMAL) total: {ea['fp_total']}
By activity: {json.dumps(ea['false_positives_NORMAL_to_ABNORMAL_by_activity'], indent=2)}
False negatives (ABNORMAL→NORMAL) total: {ea['fn_total']}
By activity: {json.dumps(ea['false_negatives_ABNORMAL_to_NORMAL_by_activity'], indent=2)}

## Files Created
- {log_path}
- {latest_path}
- {report_path}
- {summary_path}
- {MODELS_V2}/ (all v2 artifacts)

## Files Changed
- None of the original normal/ or abnormal/ CSVs were modified.

## Files Moved/Copied
- None. Raw data left in place. Features loaded from existing features_cache/.

## Problems
- Existing baseline model was pickled with sklearn 1.9.0; local env may differ — v2 retrained fresh.
- Skip reasons during validation: {dict(skip_reasons)}

## Final Status
SUCCESS
"""
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary)
        file_change(log, "Write training summary markdown", "(none)", str(summary_path), "CREATED", "N/A")

        latest_path.write_text(Path(log_path).read_text(encoding="utf-8"), encoding="utf-8")
        file_change(log, "Mirror latest log pointer", str(log_path), str(latest_path), "COPIED", "YES")

        status = "SUCCESS"
        log.log(f"Final model path: {paths['model']}")
        log.log(f"Scaler path: {paths['scaler']}")
        log.log(f"Label encoder path: {paths['label_encoder']}")
        log.log(f"Final status: {status}")
        log.log(f"End time: {datetime.now().isoformat()}")
        log.log("SOS integration: NOT PERFORMED (by design)")

        report_json = LOG_DIR / "movement_training_report.json"
        with open(report_json, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "status": status,
                    "synthetic": True,
                    "dataset_sessions": int(len(sessions)),
                    "normal": int((sessions["class"] == "NORMAL").sum()),
                    "abnormal": int((sessions["class"] == "ABNORMAL").sum()),
                    "split_windows": {
                        "train": int(len(ytr)),
                        "val": int(len(yva)),
                        "test": int(len(yte)),
                    },
                    "split_sessions": {
                        "train": int(len(set(str_))),
                        "val": int(len(set(sva))),
                        "test": int(len(set(ste))),
                    },
                    "model": model_cfg["model"],
                    "features": 49,
                    "test_metrics": te,
                    "error_analysis": ea,
                    "model_dir": str(MODELS_V2),
                    "log": str(log_path),
                    "summary": str(summary_path),
                },
                f,
                indent=2,
            )
        file_change(log, "Write machine-readable report", "(none)", str(report_json), "CREATED", "N/A")

    except Exception:
        status = "FAILED"
        log.log("ERROR: training failed")
        log.log(traceback.format_exc())
        raise
    finally:
        log.log(f"STATUS={status}")
        log.close()
        try:
            latest_path.write_text(Path(log_path).read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass


if __name__ == "__main__":
    main()
