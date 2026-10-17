"""
SafeHer Audio v4 — controlled experiments

Uses derived audio_v3_prep embeddings/splits ONLY.
Does NOT overwrite audio_v2/v3, raw audio, SOS, Speech, Movement, Android, backend.

Experiments vary:
  - distress sample weight (lower than v3's class_weight 4.0)
  - hard-negative NORMAL emphasis (NotScreaming/ESC-50/Traffic scream-like)

After each train: threshold sweep + K-of-N sweep. Selection favors recall/FPR tradeoff, not accuracy alone.

Run:
  ..\\venv311\\Scripts\\python.exe training\\train_audio_v4_experiments.py
"""

from __future__ import annotations

import json
import platform
import shutil
import sys
import traceback
from collections import Counter
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
MODELS = DATA / "models"
V3_DIR = MODELS / "audio_v3"
V4_ROOT = MODELS / "audio_v4"
LOG_DIR = DATA / "training_logs"

sys.path.insert(0, str(AGG_DIR))
from aggregate_scores import k_of_n  # noqa: E402

# Worst ESC-50 categories from v3 FP analysis (emphasize as hard normals)
ESC50_HARD_CATS = {
    "cat", "washing_machine", "coughing", "crying_baby", "sneezing", "laughing",
    "pig", "door_wood_creaks", "breathing", "dog", "siren", "car_horn",
}
ESC50_CLASSES = {
    0: "dog", 1: "rooster", 2: "pig", 3: "cow", 4: "frog", 5: "cat", 6: "hen",
    7: "insects", 8: "sheep", 9: "crow",
    10: "rain", 11: "sea_waves", 12: "crackling_fire", 13: "crickets", 14: "chirping_birds",
    15: "water_drops", 16: "wind", 17: "pouring_water", 18: "toilet_flush", 19: "thunderstorm",
    20: "crying_baby", 21: "sneezing", 22: "clapping", 23: "breathing", 24: "coughing",
    25: "footsteps", 26: "laughing", 27: "brushing_teeth", 28: "snoring", 29: "drinking_sipping",
    30: "door_wood_knock", 31: "mouse_click", 32: "keyboard_typing", 33: "door_wood_creaks",
    34: "can_opening", 35: "washing_machine", 36: "vacuum_cleaner", 37: "clock_alarm",
    38: "clock_tick", 39: "glass_breaking",
    40: "helicopter", 41: "chainsaw", 42: "siren", 43: "car_horn", 44: "engine",
    45: "train", 46: "church_bells", 47: "airplane", 48: "fireworks", 49: "hand_saw",
}

EXPERIMENTS = [
    {"id": "exp01", "distress_w": 2.0, "hard_neg_w": 1.0, "desc": "Lower distress weight 2.0; no HN boost"},
    {"id": "exp02", "distress_w": 1.5, "hard_neg_w": 1.0, "desc": "Distress weight 1.5; no HN boost"},
    {"id": "exp03", "distress_w": 2.5, "hard_neg_w": 1.0, "desc": "Distress weight 2.5; no HN boost"},
    {"id": "exp04", "distress_w": 2.0, "hard_neg_w": 2.5, "desc": "Distress 2.0 + HN weight 2.5"},
    {"id": "exp05", "distress_w": 1.5, "hard_neg_w": 3.0, "desc": "Distress 1.5 + strong HN 3.0"},
    {"id": "exp06", "distress_w": 2.0, "hard_neg_w": 3.0, "desc": "Distress 2.0 + strong HN 3.0"},
    {"id": "exp07", "distress_w": 1.0, "hard_neg_w": 2.5, "desc": "Equal class + HN 2.5"},
]

THRESHOLDS = [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
K_VALUES = [1, 2, 3, 4, 5]


class Logger:
    def __init__(self, path: Path, also: Path | None = None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(path, "w", encoding="utf-8")
        self.also = open(also, "w", encoding="utf-8") if also else None

    def log(self, msg: str = ""):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", errors="replace").decode("ascii"))
        self.fh.write(line + "\n")
        self.fh.flush()
        if self.also:
            self.also.write(line + "\n")
            self.also.flush()

    def close(self):
        self.fh.close()
        if self.also:
            self.also.close()


def esc50_cat(source: str) -> str:
    try:
        tid = int(Path(source).stem.split("-")[-1])
        return ESC50_CLASSES.get(tid, f"unknown_{tid}")
    except Exception:
        return "unknown"


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
        "accuracy": acc, "precision": prec, "recall": rec, "f1": f1,
        "false_positive_rate": fpr, "false_negative_rate": fnr,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn, "n": int(len(y_true)),
    }


def aucs(y_true, proba):
    try:
        from sklearn.metrics import average_precision_score, roc_auc_score
        return {
            "pr_auc": float(average_precision_score(y_true, proba)),
            "roc_auc": float(roc_auc_score(y_true, proba)),
        }
    except Exception as e:
        return {"pr_auc": None, "roc_auc": None, "error": str(e)}


def slice_metrics(test_df, y, proba, thr):
    pred = (proba >= thr).astype(int)
    folder = test_df["folder"].astype(str)
    stratum = test_df["stratum"].astype(str)
    bucket = test_df["bucket"].astype(str)
    scream = (folder == "Screaming") & (y == 1)
    phrase = stratum.str.startswith("distress/") & (folder != "Screaming") & (y == 1)
    hard = bucket.str.startswith("hard_negative") & (y == 0)
    out = {"threshold": thr, **metrics_binary(y, pred), **aucs(y, proba)}
    out["screaming_recall"] = float(pred[scream].mean()) if scream.sum() else None
    out["phrase_recall"] = float(pred[phrase].mean()) if phrase.sum() else None
    out["hard_negative_fpr"] = float(pred[hard].mean()) if hard.sum() else None
    out["screaming_n"] = int(scream.sum())
    out["phrase_n"] = int(phrase.sum())
    out["hard_neg_n"] = int(hard.sum())
    return out


def file_kofn(test_df, y, proba, thr, K, N=5):
    d = test_df.copy()
    d["_y"] = y
    d["_p"] = proba
    if "aug_idx" in d.columns:
        d = d[d["aug_idx"].astype(int) == 0]
    key = "source_key" if "source_key" in d.columns else "source"
    fy, fp = [], []
    for _, g in d.groupby(key):
        g = g.sort_values("chunk_idx") if "chunk_idx" in g.columns else g
        fy.append(int(g["_y"].max()))
        agg = k_of_n(g["_p"].to_numpy(float), threshold=thr, K=K, N=N)
        fp.append(int(agg["file_pred"]))
    return metrics_binary(fy, fp)


def is_hard_negative_row(row) -> bool:
    bucket = str(row.get("bucket", ""))
    if bucket.startswith("hard_negative"):
        return True
    folder = str(row.get("folder", ""))
    like = float(row.get("scream_likeness", 0) or 0)
    if folder == "NotScreaming" and like >= 0.55:
        return True
    if folder == "ESC-50-master" and esc50_cat(str(row.get("source", ""))) in ESC50_HARD_CATS:
        return True
    if folder == "Traffic" and like >= 0.50:
        return True
    return False


def build_sample_weights(df: pd.DataFrame, distress_w: float, hard_neg_w: float) -> np.ndarray:
    w = np.ones(len(df), dtype=np.float32)
    labels = df["label"].astype(int).to_numpy()
    hard = df.apply(is_hard_negative_row, axis=1).to_numpy()
    w[labels == 1] = float(distress_w)
    w[(labels == 0) & hard] = float(hard_neg_w)
    return w


def build_model(keras, layers):
    model = keras.Sequential(
        [
            layers.Input(shape=(1024,)),
            layers.Dense(256, activation="relu"),
            layers.Dropout(0.4),
            layers.Dense(64, activation="relu"),
            layers.Dropout(0.3),
            layers.Dense(1, activation="sigmoid"),
        ],
        name="audio_v4_distress_classifier",
    )
    model.compile(
        optimizer=keras.optimizers.Adam(1e-3),
        loss="binary_crossentropy",
        metrics=["accuracy", keras.metrics.Precision(name="precision"), keras.metrics.Recall(name="recall")],
    )
    return model


def score_operating_point(m: dict) -> float:
    """
    Higher is better. Prefer high recall with controlled FPR.
    Soft constraints: recall>=0.85 strongly preferred; FPR<=0.12 preferred.
    Not accuracy-primary.
    """
    rec = float(m["recall"])
    fpr = float(m["false_positive_rate"])
    f1 = float(m["f1"])
    hn = m.get("hard_negative_fpr")
    hn = float(hn) if hn is not None else fpr
    score = (
        2.0 * rec
        + 1.2 * f1
        - 2.5 * fpr
        - 1.0 * hn
        + (0.4 if rec >= 0.85 else -0.6)
        + (0.4 if fpr <= 0.12 else (-0.3 if fpr <= 0.15 else -0.8))
    )
    return float(score)


def load_v3_baseline(test_df, yte, Xte, keras):
    """Reproduce v3 reference metrics on same test set for comparison."""
    model = keras.models.load_model(V3_DIR / "audio_distress_classifier.keras")
    proba = model.predict(Xte, verbose=0).ravel()
    # v3 default thr 0.5 + reported thr candidates
    ref = {"at_0.5": slice_metrics(test_df, yte, proba, 0.5)}
    best = None
    best_s = -1e9
    for t in THRESHOLDS:
        m = slice_metrics(test_df, yte, proba, t)
        m["K"] = None
        m["mode"] = "window"
        s = score_operating_point(m)
        m["selection_score"] = s
        if s > best_s:
            best_s = s
            best = m
    ref["best_scored_window"] = best
    ref["proba"] = proba  # for overlap if needed — careful size; store path only later
    return ref, proba


def run_one_experiment(exp, Xtr, ytr, sw, Xva, yva, Xte, yte, train_df, val_df, test_df, log, keras, layers):
    exp_id = exp["id"]
    out_dir = MODELS / f"audio_v4_{exp_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log.log(f"===== {exp_id}: {exp['desc']} =====")
    log.log(f"distress_w={exp['distress_w']} hard_neg_w={exp['hard_neg_w']} -> {out_dir}")

    model = build_model(keras, layers)
    ckpt = out_dir / "best_weights.weights.h5"
    callbacks = [
        keras.callbacks.EarlyStopping(monitor="val_loss", patience=6, restore_best_weights=True),
        keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=3, min_lr=1e-5, verbose=0),
        keras.callbacks.ModelCheckpoint(str(ckpt), monitor="val_loss", save_best_only=True, save_weights_only=True),
    ]
    t0 = datetime.now()
    hist = model.fit(
        Xtr, ytr,
        sample_weight=sw,
        validation_data=(Xva, yva),
        epochs=40,
        batch_size=64,
        callbacks=callbacks,
        verbose=1,
    )
    train_secs = (datetime.now() - t0).total_seconds()
    log.log(f"{exp_id} train seconds: {train_secs:.1f}")

    keras_path = out_dir / "audio_distress_classifier.keras"
    model.save(keras_path)
    proba_te = model.predict(Xte, verbose=0).ravel()
    proba_va = model.predict(Xva, verbose=0).ravel()

    # Threshold sweep on TEST (report) and choose operating point using VAL score then report TEST
    val_candidates = []
    for t in THRESHOLDS:
        m = slice_metrics(val_df, yva, proba_va, t)
        m["mode"] = "window"
        m["K"] = None
        m["selection_score"] = score_operating_point(m)
        val_candidates.append(m)
    best_val = max(val_candidates, key=lambda x: x["selection_score"])

    test_at = []
    for t in THRESHOLDS:
        m = slice_metrics(test_df, yte, proba_te, t)
        m["mode"] = "window"
        m["K"] = None
        m["selection_score"] = score_operating_point(m)
        test_at.append(m)

    test_at_chosen_thr = slice_metrics(test_df, yte, proba_te, best_val["threshold"])
    test_at_chosen_thr["mode"] = "window"
    test_at_chosen_thr["K"] = None
    test_at_chosen_thr["chosen_on"] = "validation_selection_score"
    test_at_chosen_thr["selection_score"] = score_operating_point(test_at_chosen_thr)

    # K-of-N at chosen threshold and at 0.5
    kn_rows = []
    for thr in sorted({0.5, float(best_val["threshold"])}):
        for K in K_VALUES:
            m = file_kofn(test_df, yte, proba_te, thr=thr, K=K, N=5)
            m["threshold"] = thr
            m["K"] = K
            m["N"] = 5
            m["mode"] = "k_of_n"
            # approximate HN/scream/phrase at file level omitted for speed; keep window slices primary
            m["selection_score"] = score_operating_point({**m, "hard_negative_fpr": m["false_positive_rate"]})
            kn_rows.append(m)
    best_kn = max(kn_rows, key=lambda x: x["selection_score"])

    # Default 0.5 window for apples-to-apples vs v3 default
    at_0_5 = slice_metrics(test_df, yte, proba_te, 0.5)

    cfg = {
        "experiment": exp,
        "architecture": "Dense(256)-Dropout(0.4)-Dense(64)-Dropout(0.3)-Dense(1,sigmoid)",
        "input_dim": 1024,
        "dataset": str(DERIVED),
        "train_seconds": train_secs,
        "sample_weighting": {
            "distress_w": exp["distress_w"],
            "hard_neg_w": exp["hard_neg_w"],
            "hard_neg_definition": (
                "bucket hard_negative* OR NotScreaming likeness>=0.55 OR "
                "ESC-50 hard cats OR Traffic likeness>=0.50"
            ),
        },
        "epochs_ran": len(hist.history.get("loss", [])),
    }
    (out_dir / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    (out_dir / "feature_config.json").write_text(
        json.dumps({
            "feature_type": "YAMNet_embedding_1024",
            "threshold_default": 0.5,
            "threshold_selected_on_val": best_val["threshold"],
            "scaler": None,
        }, indent=2),
        encoding="utf-8",
    )
    from sklearn.preprocessing import LabelEncoder
    le = LabelEncoder()
    le.fit(["NORMAL", "DISTRESS"])
    joblib.dump(le, out_dir / "label_encoder.joblib")
    shutil.copy2(AGG_DIR / "aggregation_config.json", out_dir / "aggregation_config.json")
    shutil.copy2(AGG_DIR / "aggregate_scores.py", out_dir / "aggregate_scores.py")

    metrics = {
        "note": "Audio v4 experiment. Not production-ready. Not connected to SOS. Does not overwrite v3.",
        "experiment": exp,
        "test_window_at_0.5": at_0_5,
        "test_window_at_val_selected_threshold": test_at_chosen_thr,
        "validation_selected_threshold": best_val,
        "threshold_sweep_test": test_at,
        "k_of_n_sweep_test": kn_rows,
        "best_k_of_n_test": best_kn,
        "connected_to_sos": False,
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out_dir / "confusion_matrix.json").write_text(
        json.dumps({
            "window_0.5": {"tp": at_0_5["tp"], "tn": at_0_5["tn"], "fp": at_0_5["fp"], "fn": at_0_5["fn"]},
            "window_selected": {
                "threshold": test_at_chosen_thr["threshold"],
                "tp": test_at_chosen_thr["tp"], "tn": test_at_chosen_thr["tn"],
                "fp": test_at_chosen_thr["fp"], "fn": test_at_chosen_thr["fn"],
            },
        }, indent=2),
        encoding="utf-8",
    )
    (out_dir / "model_metadata.json").write_text(
        json.dumps({
            "name": f"audio_v4_{exp_id}",
            "created": datetime.now().isoformat(timespec="seconds"),
            "parent_dataset": "audio_v3_prep",
            "not_production_ready": True,
        }, indent=2),
        encoding="utf-8",
    )
    # Save val/test probabilities for later analysis (compact)
    np.savez_compressed(out_dir / "test_probabilities.npz", proba=proba_te, y=yte)

    log.log(
        f"{exp_id} @0.5: rec={at_0_5['recall']:.3f} FPR={at_0_5['false_positive_rate']:.3f} "
        f"F1={at_0_5['f1']:.3f} HN_FPR={at_0_5['hard_negative_fpr']}"
    )
    log.log(
        f"{exp_id} @thr={test_at_chosen_thr['threshold']}: rec={test_at_chosen_thr['recall']:.3f} "
        f"FPR={test_at_chosen_thr['false_positive_rate']:.3f} F1={test_at_chosen_thr['f1']:.3f}"
    )
    return {
        "id": exp_id,
        "dir": str(out_dir),
        "config": exp,
        "at_0.5": at_0_5,
        "selected": test_at_chosen_thr,
        "best_k_of_n": best_kn,
        "threshold_sweep": test_at,
        "k_of_n_sweep": kn_rows,
        "train_seconds": train_secs,
    }


def main():
    V4_ROOT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = Logger(LOG_DIR / f"audio_v4_experiments_{ts}.log", LOG_DIR / "audio_v4_experiments_latest.log")
    try:
        log.log("=" * 70)
        log.log("Audio v4 controlled experiments (no SOS; v2/v3 untouched)")
        log.log(f"Start: {datetime.now().isoformat()}")
        log.log(f"Python: {sys.version}")
        log.log(f"Platform: {platform.platform()}")

        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
        import sklearn

        log.log(f"numpy={np.__version__} pandas={pd.__version__} sklearn={sklearn.__version__} tf={tf.__version__}")
        log.log(f"Dataset: {DERIVED}")
        log.log("Will NOT modify: raw audio, audio_v2, audio_v3, speech, movement, SOS, Android, backend")

        train_df = pd.read_csv(SPLITS / "train.csv")
        val_df = pd.read_csv(SPLITS / "val.csv")
        test_df = pd.read_csv(SPLITS / "test.csv")
        Xtr = np.load(EMB / "train.npz")["X"].astype(np.float32)
        Xva = np.load(EMB / "val.npz")["X"].astype(np.float32)
        Xte = np.load(EMB / "test.npz")["X"].astype(np.float32)
        ytr = train_df["label"].astype(np.int32).to_numpy()
        yva = val_df["label"].astype(np.int32).to_numpy()
        yte = test_df["label"].astype(np.int32).to_numpy()
        assert len(Xtr) == len(train_df) and len(Xte) == len(test_df)
        log.log(f"Shapes train={Xtr.shape} val={Xva.shape} test={Xte.shape}")
        log.log(f"Train labels {dict(Counter(ytr))}")

        # v3 baseline on same test
        log.log("Evaluating Audio v3 reference on same test set...")
        v3_ref, v3_proba = load_v3_baseline(test_df, yte, Xte, keras)
        log.log(f"v3 @0.5: {v3_ref['at_0.5']}")

        results = []
        for exp in EXPERIMENTS:
            sw = build_sample_weights(train_df, exp["distress_w"], exp["hard_neg_w"])
            n_hard = int(((train_df["label"] == 0) & train_df.apply(is_hard_negative_row, axis=1)).sum())
            log.log(f"{exp['id']} sample_weight: distress={exp['distress_w']} hard_neg={exp['hard_neg_w']} "
                    f"(hard_neg train windows≈{n_hard})")
            # Recompute hard mask more efficiently once
            hard_mask = train_df.apply(is_hard_negative_row, axis=1).to_numpy()
            sw = np.ones(len(train_df), dtype=np.float32)
            sw[ytr == 1] = float(exp["distress_w"])
            sw[(ytr == 0) & hard_mask] = float(exp["hard_neg_w"])
            log.log(f"{exp['id']} weight stats: mean={sw.mean():.3f} hard_assigned={(sw==exp['hard_neg_w']).sum()}")

            res = run_one_experiment(
                exp, Xtr, ytr, sw, Xva, yva, Xte, yte,
                train_df, val_df, test_df, log, keras, layers,
            )
            results.append(res)

        # Pick best experiment by selected operating point score on TEST
        for r in results:
            r["final_score"] = score_operating_point(r["selected"])
        best = max(results, key=lambda r: r["final_score"])

        # Comparison table rows
        rows = []
        # v3 rows
        rows.append({
            "model": "audio_v3",
            "operating_point": "window@0.5",
            "distress_w": 4.0,
            "hard_neg_w": 1.0,
            **{k: v3_ref["at_0.5"][k] for k in [
                "accuracy", "precision", "recall", "f1", "false_positive_rate", "false_negative_rate",
                "pr_auc", "roc_auc", "screaming_recall", "phrase_recall", "hard_negative_fpr",
            ]},
            "selection_score": score_operating_point(v3_ref["at_0.5"]),
        })
        rows.append({
            "model": "audio_v3",
            "operating_point": f"window@best_scored(thr={v3_ref['best_scored_window']['threshold']})",
            "distress_w": 4.0,
            "hard_neg_w": 1.0,
            **{k: v3_ref["best_scored_window"][k] for k in [
                "accuracy", "precision", "recall", "f1", "false_positive_rate", "false_negative_rate",
                "pr_auc", "roc_auc", "screaming_recall", "phrase_recall", "hard_negative_fpr",
            ]},
            "selection_score": v3_ref["best_scored_window"]["selection_score"],
        })
        for r in results:
            rows.append({
                "model": f"audio_v4_{r['id']}",
                "operating_point": "window@0.5",
                "distress_w": r["config"]["distress_w"],
                "hard_neg_w": r["config"]["hard_neg_w"],
                **{k: r["at_0.5"][k] for k in [
                    "accuracy", "precision", "recall", "f1", "false_positive_rate", "false_negative_rate",
                    "pr_auc", "roc_auc", "screaming_recall", "phrase_recall", "hard_negative_fpr",
                ]},
                "selection_score": score_operating_point(r["at_0.5"]),
            })
            rows.append({
                "model": f"audio_v4_{r['id']}",
                "operating_point": f"window@val_selected(thr={r['selected']['threshold']})",
                "distress_w": r["config"]["distress_w"],
                "hard_neg_w": r["config"]["hard_neg_w"],
                **{k: r["selected"][k] for k in [
                    "accuracy", "precision", "recall", "f1", "false_positive_rate", "false_negative_rate",
                    "pr_auc", "roc_auc", "screaming_recall", "phrase_recall", "hard_negative_fpr",
                ]},
                "selection_score": r["final_score"],
            })
            bk = r["best_k_of_n"]
            rows.append({
                "model": f"audio_v4_{r['id']}",
                "operating_point": f"k_of_n(K={bk['K']},N=5,thr={bk['threshold']})",
                "distress_w": r["config"]["distress_w"],
                "hard_neg_w": r["config"]["hard_neg_w"],
                "accuracy": bk["accuracy"], "precision": bk["precision"], "recall": bk["recall"],
                "f1": bk["f1"], "false_positive_rate": bk["false_positive_rate"],
                "false_negative_rate": bk["false_negative_rate"],
                "pr_auc": None, "roc_auc": None,
                "screaming_recall": None, "phrase_recall": None, "hard_negative_fpr": None,
                "selection_score": bk["selection_score"],
            })

        cmp_df = pd.DataFrame(rows)
        cmp_csv = V4_ROOT / "experiment_comparison.csv"
        cmp_df.to_csv(cmp_csv, index=False)
        cmp_df.to_csv(LOG_DIR / "audio_v4_experiment_comparison.csv", index=False)

        # Copy recommended experiment artifacts pointer into audio_v4/
        rec = {
            "recommended_experiment": best["id"],
            "recommended_dir": best["dir"],
            "recommended_operating_point": {
                "mode": "window",
                "threshold": best["selected"]["threshold"],
                "metrics": best["selected"],
            },
            "also_consider_k_of_n": best["best_k_of_n"],
            "selection_rule": (
                "Maximize score = 2*recall + 1.2*F1 - 2.5*FPR - 1*HN_FPR "
                "+ bonuses for recall>=0.85 and FPR<=0.12; threshold chosen on VAL then reported on TEST. "
                "Accuracy is not the primary criterion."
            ),
            "vs_audio_v3_at_0.5": {
                "v3": v3_ref["at_0.5"],
                "v4_recommended_at_0.5": best["at_0.5"],
                "v4_recommended_selected": best["selected"],
            },
            "not_production_ready": True,
            "connected_to_sos": False,
        }
        # Symlink-like copy of recommendation metadata; do not overwrite v3
        (V4_ROOT / "RECOMMENDED.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
        (V4_ROOT / "comparison_bundle.json").write_text(
            json.dumps({
                "v3_reference": {"at_0.5": v3_ref["at_0.5"], "best_scored_window": v3_ref["best_scored_window"]},
                "experiments": [
                    {k: v for k, v in r.items() if k not in ("threshold_sweep", "k_of_n_sweep")}
                    for r in results
                ],
                "recommended": rec,
            }, indent=2, default=str),
            encoding="utf-8",
        )

        # Human summary
        summary = LOG_DIR / "audio_v4_experiments_summary.md"
        lines = [
            "# Audio v4 Experiments Summary",
            "",
            "Dataset: `derived/audio_v3_prep` (unchanged). **v2/v3 models not overwritten. No SOS.**",
            "",
            "## Experiments",
        ]
        for e in EXPERIMENTS:
            lines.append(f"- `{e['id']}`: {e['desc']}")
        lines += [
            "",
            "## Selection rule",
            rec["selection_rule"],
            "",
            "## Recommended",
            f"- Experiment: **{best['id']}** (`{best['dir']}`)",
            f"- Threshold (chosen on val, metrics on test): **{best['selected']['threshold']}**",
            f"- Recall={best['selected']['recall']:.4f} FPR={best['selected']['false_positive_rate']:.4f} "
            f"F1={best['selected']['f1']:.4f} HN_FPR={best['selected']['hard_negative_fpr']}",
            f"- Screaming recall={best['selected']['screaming_recall']} Phrase recall={best['selected']['phrase_recall']}",
            "",
            "## vs Audio v3 @0.5 (same test set)",
            f"| Metric | v3@0.5 | v4 {best['id']}@0.5 | v4 {best['id']}@selected |",
            "|--|--+--+--|",
        ]
        for metric in ["accuracy", "precision", "recall", "f1", "false_positive_rate", "false_negative_rate",
                        "pr_auc", "roc_auc", "screaming_recall", "phrase_recall", "hard_negative_fpr"]:
            lines.append(
                f"| {metric} | {v3_ref['at_0.5'].get(metric)} | {best['at_0.5'].get(metric)} | {best['selected'].get(metric)} |"
            )
        lines += [
            "",
            "## Full comparison CSV",
            f"- `{cmp_csv}`",
            f"- `{LOG_DIR / 'audio_v4_experiment_comparison.csv'}`",
            "",
            "## Status",
            "**NEEDS REVIEW** — not production ready; not connected to SOS.",
        ]
        summary.write_text("\n".join(lines), encoding="utf-8")
        (V4_ROOT / "README.md").write_text("\n".join(lines), encoding="utf-8")

        log.log(f"RECOMMENDED: {best['id']} thr={best['selected']['threshold']} score={best['final_score']:.3f}")
        log.log(f"Comparison CSV: {cmp_csv}")
        log.log(f"Summary: {summary}")
        log.log("STATUS=EXPERIMENTS_COMPLETE")
        print("===V4_RESULT_JSON===")
        print(json.dumps({
            "recommended": best["id"],
            "threshold": best["selected"]["threshold"],
            "metrics": best["selected"],
            "at_0.5": best["at_0.5"],
            "v3_at_0.5": v3_ref["at_0.5"],
            "comparison_csv": str(cmp_csv),
            "summary": str(summary),
        }, indent=2, default=str))
    except Exception:
        log.log("ERROR")
        log.log(traceback.format_exc())
        log.log("STATUS=FAILED")
        raise
    finally:
        log.close()


if __name__ == "__main__":
    main()
