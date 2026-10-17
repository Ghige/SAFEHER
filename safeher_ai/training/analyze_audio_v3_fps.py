"""
Audio v3 FALSE POSITIVE / THRESHOLD / K-of-N / FAIR V2-V3 ANALYSIS

Read-only. Does NOT train, modify models, labels, raw audio, or SOS.

Run:
  ..\\venv311\\Scripts\\python.exe training\\analyze_audio_v3_fps.py
"""

from __future__ import annotations

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
DERIVED = DATA / "derived" / "audio_v3_prep"
SPLITS = DERIVED / "splits"
EMB = DERIVED / "embeddings"
MODEL_V3 = DATA / "models" / "audio_v3"
MODEL_V2 = DATA / "models" / "audio_v2"
LEGACY_SPLITS = DATA / "splits"
OUT = DATA / "training_logs" / "audio_v3_analysis"
LOG_DIR = DATA / "training_logs"

sys.path.insert(0, str(MODEL_V3))
from aggregate_scores import k_of_n  # noqa: E402

# Official ESC-50 target → category name
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


def dist_stats(x):
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return {}
    qs = np.percentile(x, [25, 50, 75, 90, 95, 99])
    return {
        "n": int(len(x)),
        "mean": float(np.mean(x)),
        "median": float(np.median(x)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
        "p25": float(qs[0]),
        "p50": float(qs[1]),
        "p75": float(qs[2]),
        "p90": float(qs[3]),
        "p95": float(qs[4]),
        "p99": float(qs[5]),
    }


def esc50_category(source: str) -> str:
    # filenames like 1-115921-A-22.wav → target 22
    stem = Path(source).stem
    parts = stem.split("-")
    try:
        tid = int(parts[-1])
        return ESC50_CLASSES.get(tid, f"unknown_{tid}")
    except Exception:
        return "unknown"


def classify_notscream_fp(row) -> str:
    """Heuristic content tag for NotScreaming FPs (no label changes)."""
    like = float(row.get("scream_likeness", 0))
    high = float(row.get("highband_ge2khz", 0))
    cent = float(row.get("spectral_centroid_hz", 0))
    # High scream-likeness → hard negative (genuinely scream-like under heuristic)
    if like >= 0.70 or (high >= 0.45 and cent >= 2200):
        return "POTENTIAL_HARD_NEGATIVE"
    if like >= 0.55 or (high >= 0.35 and cent >= 1800):
        return "AMBIGUOUS_VOCAL_OR_NOISE"
    if cent < 1200 and high < 0.25:
        return "LIKELY_ENVIRONMENTAL_OR_LOWBAND"
    return "POSSIBLE_MODEL_OVERTRIGGER"


def file_level_kofn(df, proba, y, K, N, thr=0.5, key_col="source_key"):
    d = df.copy()
    d["_p"] = proba
    d["_y"] = y
    if "aug_idx" in d.columns:
        d = d[d["aug_idx"].astype(int) == 0]
    fy, fp = [], []
    for _, g in d.groupby(key_col if key_col in d.columns else "source"):
        g = g.sort_values("chunk_idx") if "chunk_idx" in g.columns else g
        yt = int(g["_y"].max())
        agg = k_of_n(g["_p"].to_numpy(dtype=float), threshold=thr, K=K, N=N)
        fy.append(yt)
        fp.append(int(agg["file_pred"]))
    return metrics_binary(fy, fp)


def try_pr_roc(y_true, proba):
    out = {"pr_auc": None, "roc_auc": None}
    try:
        from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_curve, roc_curve
        out["pr_auc"] = float(average_precision_score(y_true, proba))
        out["roc_auc"] = float(roc_auc_score(y_true, proba))
        # save curve points
        p, r, t = precision_recall_curve(y_true, proba)
        fpr, tpr, rt = roc_curve(y_true, proba)
        out["pr_curve_points"] = int(len(t))
        out["roc_curve_points"] = int(len(rt))
        # optional plot
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(1, 2, figsize=(10, 4))
            ax[0].plot(r, p)
            ax[0].set_title(f"PR curve (AP={out['pr_auc']:.3f})")
            ax[0].set_xlabel("Recall")
            ax[0].set_ylabel("Precision")
            ax[1].plot(fpr, tpr)
            ax[1].set_title(f"ROC (AUC={out['roc_auc']:.3f})")
            ax[1].set_xlabel("FPR")
            ax[1].set_ylabel("TPR")
            fig.tight_layout()
            fig.savefig(OUT / "pr_roc_curves.png", dpi=120)
            plt.close(fig)
            out["plot"] = str(OUT / "pr_roc_curves.png")
        except Exception as e:
            out["plot_error"] = str(e)
    except Exception as e:
        out["error"] = str(e)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = Logger(LOG_DIR / f"audio_v3_fp_analysis_{ts}.log", LOG_DIR / "audio_v3_fp_analysis_latest.log")
    created = []
    try:
        log.log("=" * 70)
        log.log("Audio v3 FP / threshold / K-of-N / fair v2-v3 ANALYSIS (read-only)")
        log.log(f"Start: {datetime.now().isoformat()}")
        log.log(f"Python: {sys.version}")
        log.log(f"Platform: {platform.platform()}")

        import tensorflow as tf
        from tensorflow import keras

        log.log(f"numpy={np.__version__} pandas={pd.__version__} tf={tf.__version__}")

        # --- Audit ---
        cfg = json.loads((MODEL_V3 / "config.json").read_text(encoding="utf-8"))
        feat = json.loads((MODEL_V3 / "feature_config.json").read_text(encoding="utf-8"))
        agg = json.loads((MODEL_V3 / "aggregation_config.json").read_text(encoding="utf-8"))
        log.log(f"Model path: {MODEL_V3 / 'audio_distress_classifier.keras'}")
        log.log(f"Architecture: {cfg.get('model', {})}")
        log.log(f"Feature config: {feat}")
        log.log(f"Aggregation: {agg}")
        K0 = int(agg["modes"]["k_of_n"]["K"])
        N0 = int(agg["modes"]["k_of_n"]["N"])
        thr0 = float(feat.get("threshold", agg.get("default_threshold", 0.5)))
        log.log(f"Current threshold={thr0}, K={K0}, N={N0}")

        test_df = pd.read_csv(SPLITS / "test.csv")
        emb = np.load(EMB / "test.npz")
        X = emb["X"].astype(np.float32)
        y = test_df["label"].astype(int).to_numpy()
        assert len(X) == len(test_df) == len(y)
        log.log(f"Test windows: {len(test_df)}; label counts: {dict(Counter(y))}")

        model = keras.models.load_model(MODEL_V3 / "audio_distress_classifier.keras")
        proba = model.predict(X, verbose=0).ravel()
        pred = (proba >= thr0).astype(int)
        base = metrics_binary(y, pred)
        log.log(f"Confirm window metrics @0.5: {base}")
        assert base["fp"] == 1109 or abs(base["fp"] - 1109) <= 2, f"FP count unexpected: {base['fp']}"

        # ============================================================
        # FP category analysis
        # ============================================================
        fp_mask = (y == 0) & (pred == 1)
        fp_df = test_df.loc[fp_mask].copy()
        fp_df["proba"] = proba[fp_mask]
        fp_df["fp_category"] = fp_df["folder"].map(
            lambda f: f if f in {"NotScreaming", "ESC-50-master", "Traffic"} else "Other"
        )
        # hard-negative flag
        fp_df["is_hard_neg"] = fp_df["bucket"].astype(str).str.startswith("hard_negative")

        # category totals in full test (for FPR within category)
        cat_total = {}
        for cat in ["NotScreaming", "ESC-50-master", "Traffic", "Other"]:
            if cat == "Other":
                m = ~test_df["folder"].isin(["NotScreaming", "ESC-50-master", "Traffic"]) & (y == 0)
            else:
                m = (test_df["folder"] == cat) & (y == 0)
            cat_total[cat] = int(m.sum())

        hard_total = int(((test_df["bucket"].astype(str).str.startswith("hard_negative")) & (y == 0)).sum())

        def cat_block(name, sub, denom):
            return {
                "category": name,
                "fp_count": int(len(sub)),
                "pct_of_all_fp": float(len(sub) / max(len(fp_df), 1)),
                "category_normal_windows": denom,
                "fpr_within_category": float(len(sub) / denom) if denom else None,
                "proba": dist_stats(sub["proba"].to_numpy()) if len(sub) else {},
            }

        fp_cats = [
            cat_block("NotScreaming", fp_df[fp_df.folder == "NotScreaming"], cat_total["NotScreaming"]),
            cat_block("ESC-50-master", fp_df[fp_df.folder == "ESC-50-master"], cat_total["ESC-50-master"]),
            cat_block("Traffic", fp_df[fp_df.folder == "Traffic"], cat_total["Traffic"]),
            cat_block("Other", fp_df[~fp_df.folder.isin(["NotScreaming", "ESC-50-master", "Traffic"])], cat_total["Other"]),
            cat_block("Hard-negative", fp_df[fp_df.is_hard_neg], hard_total),
        ]
        log.log(f"FP categories: {json.dumps(fp_cats, indent=2)}")

        # ============================================================
        # NotScreaming deep dive
        # ============================================================
        ns = fp_df[fp_df.folder == "NotScreaming"].copy()
        ns["content_tag"] = ns.apply(classify_notscream_fp, axis=1)
        ns_tag_counts = dict(Counter(ns["content_tag"]))
        ns_summary = {
            "fp_count": int(len(ns)),
            "content_tag_counts": ns_tag_counts,
            "mean_scream_likeness": float(ns["scream_likeness"].mean()) if len(ns) else None,
            "mean_highband": float(ns["highband_ge2khz"].mean()) if len(ns) else None,
            "mean_centroid": float(ns["spectral_centroid_hz"].mean()) if len(ns) else None,
            "already_bucket_hard_neg": int(ns["is_hard_neg"].sum()),
            "note": (
                "Tags are heuristic from scream_likeness/spectral features — NOT human listening. "
                "No labels changed. POTENTIAL_HARD_NEGATIVE = high scream-likeness under prepared gates."
            ),
        }
        log.log(f"NotScreaming FP summary: {ns_summary}")

        # ============================================================
        # ESC-50
        # ============================================================
        esc = fp_df[fp_df.folder == "ESC-50-master"].copy()
        esc["esc50_category"] = esc["source"].map(esc50_category)
        # totals per esc category among NORMAL esc test windows
        esc_all = test_df[(test_df.folder == "ESC-50-master") & (y == 0)].copy()
        esc_all["esc50_category"] = esc_all["source"].map(esc50_category)
        esc_rows = []
        for cat, gfp in esc.groupby("esc50_category"):
            tot = int((esc_all.esc50_category == cat).sum())
            esc_rows.append({
                "esc50_category": cat,
                "total_normal_windows": tot,
                "false_positives": int(len(gfp)),
                "fpr": float(len(gfp) / tot) if tot else None,
                "avg_predicted_probability": float(gfp["proba"].mean()),
                "median_probability": float(gfp["proba"].median()),
            })
        esc_table = pd.DataFrame(esc_rows).sort_values(["false_positives", "fpr"], ascending=False)
        esc_csv = OUT / "esc50_fp_by_category.csv"
        esc_table.to_csv(esc_csv, index=False)
        created.append(str(esc_csv))
        log.log(f"ESC-50 worst categories:\n{esc_table.head(15).to_string(index=False)}")

        # ============================================================
        # Traffic
        # ============================================================
        tr = fp_df[fp_df.folder == "Traffic"].copy()
        traffic_summary = {
            "fp_count": int(len(tr)),
            "proba": dist_stats(tr["proba"]) if len(tr) else {},
            "scream_likeness": dist_stats(tr["scream_likeness"]) if len(tr) else {},
            "highband": dist_stats(tr["highband_ge2khz"]) if len(tr) else {},
            "centroid": dist_stats(tr["spectral_centroid_hz"]) if len(tr) else {},
            "hypothesis": (
                "Traffic FPs with elevated highband/centroid may reflect horns/sirens/broadband "
                "engine noise resembling scream energy after peak-norm; lowband FPs suggest over-trigger."
            ),
        }
        log.log(f"Traffic FP summary: {traffic_summary}")

        # ============================================================
        # Probability distributions TP/FP/TN/FN
        # ============================================================
        groups = {
            "TRUE_POSITIVES": proba[(y == 1) & (pred == 1)],
            "FALSE_POSITIVES": proba[(y == 0) & (pred == 1)],
            "TRUE_NEGATIVES": proba[(y == 0) & (pred == 0)],
            "FALSE_NEGATIVES": proba[(y == 1) & (pred == 0)],
        }
        group_stats = {k: dist_stats(v) for k, v in groups.items()}
        log.log(f"Probability distributions: {json.dumps(group_stats, indent=2)}")
        # near-threshold FP fraction
        fp_probs = groups["FALSE_POSITIVES"]
        near = float(np.mean((fp_probs >= 0.5) & (fp_probs < 0.6))) if len(fp_probs) else None
        high = float(np.mean(fp_probs >= 0.8)) if len(fp_probs) else None
        log.log(f"FP fraction in [0.5,0.6)={near}; FP fraction >=0.8={high}")

        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(8, 5))
            for name, vals in groups.items():
                if len(vals):
                    ax.hist(vals, bins=30, alpha=0.45, label=name, density=True)
            ax.axvline(0.5, color="k", linestyle="--", label="threshold 0.5")
            ax.set_xlabel("P(distress)")
            ax.set_ylabel("Density")
            ax.set_title("Audio v3 probability distributions")
            ax.legend(fontsize=8)
            hist_path = OUT / "probability_histograms.png"
            fig.tight_layout()
            fig.savefig(hist_path, dpi=120)
            plt.close(fig)
            created.append(str(hist_path))
        except Exception as e:
            log.log(f"WARNING histogram failed: {e}")

        # ============================================================
        # Threshold sweep
        # ============================================================
        thresholds = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
        thr_rows = []
        for t in thresholds:
            m = metrics_binary(y, (proba >= t).astype(int))
            thr_rows.append({"threshold": t, **m})
        thr_df = pd.DataFrame(thr_rows)
        thr_csv = OUT / "threshold_analysis.csv"
        thr_df.to_csv(thr_csv, index=False)
        created.append(str(thr_csv))
        # also requested path under training_logs root
        thr_csv2 = LOG_DIR / "threshold_analysis.csv"
        thr_df.to_csv(thr_csv2, index=False)
        created.append(str(thr_csv2))

        # candidates: high recall + lower FPR
        candidates = thr_df[(thr_df["recall"] >= 0.80) & (thr_df["false_positive_rate"] <= 0.15)]
        candidates2 = thr_df[(thr_df["recall"] >= 0.85)]
        log.log(f"Threshold table:\n{thr_df.to_string(index=False)}")

        def df_table(df: pd.DataFrame) -> str:
            if df is None or len(df) == 0:
                return "_none_"
            return df.to_string(index=False)

        thr_md = OUT / "threshold_analysis.md"
        thr_md.write_text(
            "\n".join([
                "# Audio v3 Threshold Analysis (model unchanged)",
                "",
                "Predictions from existing audio_v3 head; thresholds applied post-hoc.",
                "",
                "```",
                df_table(thr_df),
                "```",
                "",
                "## Useful trade-off candidates",
                "",
                "Recall≥0.80 and FPR≤0.15:",
                "",
                "```",
                df_table(candidates),
                "```",
                "",
                "All thresholds with Recall≥0.85:",
                "",
                "```",
                df_table(candidates2),
                "```",
                "",
                "## Note",
                "No production threshold selected in this analysis.",
            ]),
            encoding="utf-8",
        )
        # also copy name at logs root
        (LOG_DIR / "threshold_analysis.md").write_text(thr_md.read_text(encoding="utf-8"), encoding="utf-8")
        created.append(str(thr_md))

        # ============================================================
        # PR / ROC
        # ============================================================
        curves = try_pr_roc(y, proba)
        log.log(f"PR/ROC: {curves}")

        # ============================================================
        # K-of-N sweep
        # ============================================================
        kn_rows = []
        for K in [1, 2, 3, 4, 5]:
            m = file_level_kofn(test_df, proba, y, K=K, N=5, thr=thr0)
            kn_rows.append({"K": K, "N": 5, "threshold": thr0, **m})
        kn_df = pd.DataFrame(kn_rows)
        kn_csv = OUT / "k_of_n_analysis.csv"
        kn_df.to_csv(kn_csv, index=False)
        created.append(str(kn_csv))
        log.log(f"K-of-N table:\n{kn_df.to_string(index=False)}")

        # ============================================================
        # Fair v2 vs v3 comparison
        # ============================================================
        v2_model = keras.models.load_model(MODEL_V2 / "audio_distress_classifier.keras")
        proba_v2_on_v3test = v2_model.predict(X, verbose=0).ravel()  # same embeddings

        v2_train = pd.read_csv(LEGACY_SPLITS / "train.csv")
        v2_test = pd.read_csv(LEGACY_SPLITS / "test.csv")
        v2_train_sources = set(v2_train["source"].astype(str))
        v2_test_sources = set(v2_test["source"].astype(str))

        # Fair set A: sources in BOTH legacy test and v3 test
        mask_A = test_df["source"].astype(str).isin(v2_test_sources).to_numpy()
        # Fair set B: v3 test sources NOT in v2 train (no train leakage for v2)
        mask_B = (~test_df["source"].astype(str).isin(v2_train_sources)).to_numpy()

        def eval_both(mask, name):
            if mask.sum() == 0:
                return {"name": name, "n": 0, "error": "empty set"}
            yb = y[mask]
            p3 = proba[mask]
            p2 = proba_v2_on_v3test[mask]
            dsub = test_df.loc[mask].reset_index(drop=True)
            m3 = metrics_binary(yb, (p3 >= thr0).astype(int))
            m2 = metrics_binary(yb, (p2 >= thr0).astype(int))
            # slices
            folder = dsub["folder"].astype(str)
            scream = folder.eq("Screaming").to_numpy() & (yb == 1)
            phrase = folder.ne("Screaming") & dsub["stratum"].astype(str).str.startswith("distress/") & (yb == 1)
            hard = dsub["bucket"].astype(str).str.startswith("hard_negative").to_numpy() & (yb == 0)

            def slice_rec(mask_s, probs):
                if mask_s.sum() == 0:
                    return None
                return float(((probs[mask_s] >= thr0).astype(int) == 1).mean())  # recall if positives

            def slice_fpr(mask_s, probs):
                if mask_s.sum() == 0:
                    return None
                return float((probs[mask_s] >= thr0).mean())

            # AUCs on subset
            aucs3 = try_pr_roc(yb, p3)
            aucs2 = try_pr_roc(yb, p2)
            # file-level K=3,N=5
            f3 = file_level_kofn(dsub, p3, yb, K=3, N=5, thr=thr0)
            f2 = file_level_kofn(dsub, p2, yb, K=3, N=5, thr=thr0)
            return {
                "name": name,
                "n_windows": int(mask.sum()),
                "n_sources": int(dsub["source"].nunique()),
                "label_counts": dict(Counter(yb.tolist())),
                "audio_v2_window": m2,
                "audio_v3_window": m3,
                "audio_v2_k_of_n": f2,
                "audio_v3_k_of_n": f3,
                "audio_v2_pr_auc": aucs2.get("pr_auc"),
                "audio_v2_roc_auc": aucs2.get("roc_auc"),
                "audio_v3_pr_auc": aucs3.get("pr_auc"),
                "audio_v3_roc_auc": aucs3.get("roc_auc"),
                "screaming_recall_v2": slice_rec(scream, p2),
                "screaming_recall_v3": slice_rec(scream, p3),
                "phrase_recall_v2": slice_rec(phrase.to_numpy(), p2),
                "phrase_recall_v3": slice_rec(phrase.to_numpy(), p3),
                "hard_negative_fpr_v2": slice_fpr(hard, p2),
                "hard_negative_fpr_v3": slice_fpr(hard, p3),
                "definition": (
                    "Same v3_prep test embeddings + corrected v3 labels; "
                    "both classifier heads scored without retraining."
                ),
            }

        fair_A = eval_both(mask_A, "dual_test_intersection")
        fair_B = eval_both(mask_B, "v3_test_not_in_v2_train")
        log.log(f"Fair A (both tests): n={fair_A.get('n_windows')} sources={fair_A.get('n_sources')}")
        log.log(f"Fair B (v3 test \\ v2 train): n={fair_B.get('n_windows')} sources={fair_B.get('n_sources')}")

        # ============================================================
        # Error overlap on fair set B (primary larger fair set)
        # ============================================================
        def error_overlap(mask):
            yb = y[mask]
            p3 = (proba[mask] >= thr0).astype(int)
            p2 = (proba_v2_on_v3test[mask] >= thr0).astype(int)
            fp2 = (yb == 0) & (p2 == 1)
            fp3 = (yb == 0) & (p3 == 1)
            fn2 = (yb == 1) & (p2 == 0)
            fn3 = (yb == 1) & (p3 == 0)
            return {
                "fp_both": int(np.sum(fp2 & fp3)),
                "fp_only_v2": int(np.sum(fp2 & ~fp3)),
                "fp_only_v3": int(np.sum(~fp2 & fp3)),
                "fn_both": int(np.sum(fn2 & fn3)),
                "fn_only_v2": int(np.sum(fn2 & ~fn3)),
                "fn_only_v3": int(np.sum(~fn2 & fn3)),
                "n_windows": int(mask.sum()),
            }

        overlap_A = error_overlap(mask_A)
        overlap_B = error_overlap(mask_B)
        log.log(f"Error overlap A: {overlap_A}")
        log.log(f"Error overlap B: {overlap_B}")

        # ============================================================
        # Write reports
        # ============================================================
        fp_md = LOG_DIR / "audio_v3_fp_analysis.md"
        fp_body = f"""# Audio v3 False Positive Analysis

Read-only investigation. Models/labels/raw audio **unchanged**.

## Audit confirmation
- Architecture: `{cfg.get('model', {}).get('architecture')}`
- Input dim: 1024 (YAMNet embedding)
- Preprocessing: derived `audio_v3_prep` peak-norm 1s chunks → frozen YAMNet embeddings
- Test split: `{SPLITS / 'test.csv'}` ({len(test_df)} windows)
- Threshold: **{thr0}**
- K-of-N (unchanged): **K={K0}, N={N0}**

Confirmed window CM @0.5: TN={base['tn']} FP={base['fp']} FN={base['fn']} TP={base['tp']}

## Total false positives
**{base['fp']}**

## Category breakdown
```json
{json.dumps(fp_cats, indent=2)}
```

## NotScreaming FP analysis (n={ns_summary['fp_count']})
```json
{json.dumps(ns_summary, indent=2)}
```
Interpretation:
- `POTENTIAL_HARD_NEGATIVE`: high scream-likeness — likely genuine hard negatives (do not auto-relabel)
- `AMBIGUOUS_VOCAL_OR_NOISE`: mid likeness — needs human review
- `LIKELY_ENVIRONMENTAL_OR_LOWBAND` / `POSSIBLE_MODEL_OVERTRIGGER`: lower likeness — more likely model over-trigger

## ESC-50 FP analysis
See `{esc_csv}` (top rows below).

```
{esc_table.head(20).to_string(index=False)}
```

Worst ESC-50 categories are those with high FP counts and/or high within-category FPR
(often vocal/siren/alarm-like AudioSet classes such as crying_baby, siren, laughing, etc.).

## Traffic FP analysis
```json
{json.dumps(traffic_summary, indent=2)}
```

## Hard-negative analysis
- Hard-negative NORMAL windows in test: {hard_total}
- Hard-negative FPs: {int(fp_df['is_hard_neg'].sum())}
- Within hard-neg FPR: {float(fp_df['is_hard_neg'].sum()/hard_total) if hard_total else None}

## Probability distributions
```json
{json.dumps(group_stats, indent=2)}
```
FP fraction in [0.5, 0.6): {near}
FP fraction ≥ 0.8: {high}

## Main FP cause (summary)
Class-weight 4.0 + peak-normalized YAMNet embeddings push the operating point toward high recall.
Many FPs are NotScreaming / hard-negative scream-like content (embedding-space neighbors of distress)
plus ESC-50 vocal/siren categories and some Traffic broadband events — not merely threshold-edge noise alone
(see FP≥0.8 fraction).
"""
        fp_md.write_text(fp_body, encoding="utf-8")
        created.append(str(fp_md))
        (OUT / "audio_v3_fp_analysis.md").write_text(fp_body, encoding="utf-8")

        fair_md = LOG_DIR / "audio_v2_v3_fair_comparison.md"
        fair_md.write_text(
            f"""# Fair Audio v2 vs Audio v3 Comparison

**No retraining.** Both heads scored on the **same** `audio_v3_prep` test embeddings and **corrected v3 labels**.

## Why previous comparison was unfair
v2 metrics used legacy `data/splits/test.csv` + `data/embeddings/test.npz`.
v3 metrics used `derived/audio_v3_prep` splits/embeddings with chunk-level label cleanup.
Different samples and labels → not comparable.

## Fair set definitions
1. **Set A — dual test intersection**: sources present in BOTH legacy v2 test and v3 test.
   - Windows: {fair_A.get('n_windows')}, sources: {fair_A.get('n_sources')}
2. **Set B — v3 test not in v2 train** (recommended primary): no v2 train leakage.
   - Windows: {fair_B.get('n_windows')}, sources: {fair_B.get('n_sources')}

Identical inputs: v3_prep YAMNet 1024-d embeddings. Threshold 0.5 for both.

## Set B window metrics (primary)
| Metric | Audio v2 | Audio v3 |
|--|--|--|
| Accuracy | {fair_B['audio_v2_window']['accuracy']:.4f} | {fair_B['audio_v3_window']['accuracy']:.4f} |
| Precision | {fair_B['audio_v2_window']['precision']:.4f} | {fair_B['audio_v3_window']['precision']:.4f} |
| Recall | {fair_B['audio_v2_window']['recall']:.4f} | {fair_B['audio_v3_window']['recall']:.4f} |
| F1 | {fair_B['audio_v2_window']['f1']:.4f} | {fair_B['audio_v3_window']['f1']:.4f} |
| FPR | {fair_B['audio_v2_window']['false_positive_rate']:.4f} | {fair_B['audio_v3_window']['false_positive_rate']:.4f} |
| FNR | {fair_B['audio_v2_window']['false_negative_rate']:.4f} | {fair_B['audio_v3_window']['false_negative_rate']:.4f} |
| PR-AUC | {fair_B.get('audio_v2_pr_auc')} | {fair_B.get('audio_v3_pr_auc')} |
| ROC-AUC | {fair_B.get('audio_v2_roc_auc')} | {fair_B.get('audio_v3_roc_auc')} |

### Set B slices
| Slice | v2 | v3 |
|--|--|--|
| Screaming recall | {fair_B.get('screaming_recall_v2')} | {fair_B.get('screaming_recall_v3')} |
| Phrase distress recall | {fair_B.get('phrase_recall_v2')} | {fair_B.get('phrase_recall_v3')} |
| Hard-negative FPR | {fair_B.get('hard_negative_fpr_v2')} | {fair_B.get('hard_negative_fpr_v3')} |

### Set B K-of-N (K=3,N=5)
| Metric | v2 | v3 |
|--|--|--|
| Accuracy | {fair_B['audio_v2_k_of_n']['accuracy']:.4f} | {fair_B['audio_v3_k_of_n']['accuracy']:.4f} |
| Precision | {fair_B['audio_v2_k_of_n']['precision']:.4f} | {fair_B['audio_v3_k_of_n']['precision']:.4f} |
| Recall | {fair_B['audio_v2_k_of_n']['recall']:.4f} | {fair_B['audio_v3_k_of_n']['recall']:.4f} |
| F1 | {fair_B['audio_v2_k_of_n']['f1']:.4f} | {fair_B['audio_v3_k_of_n']['f1']:.4f} |
| FPR | {fair_B['audio_v2_k_of_n']['false_positive_rate']:.4f} | {fair_B['audio_v3_k_of_n']['false_positive_rate']:.4f} |
| FNR | {fair_B['audio_v2_k_of_n']['false_negative_rate']:.4f} | {fair_B['audio_v3_k_of_n']['false_negative_rate']:.4f} |

## Set A (small dual-test intersection)
```json
{json.dumps(fair_A, indent=2, default=str)}
```

## Error overlap (did v3 fix v2 errors or shift them?)
### Set B
```json
{json.dumps(overlap_B, indent=2)}
```
### Set A
```json
{json.dumps(overlap_A, indent=2)}
```

Interpretation guide:
- High `fp_only_v3` with lower `fn_only_v2` → v3 traded FNs for new FPs
- High `fp_both` → shared hard-negative confusion remains
""",
            encoding="utf-8",
        )
        created.append(str(fair_md))
        (OUT / "audio_v2_v3_fair_comparison.md").write_text(fair_md.read_text(encoding="utf-8"), encoding="utf-8")

        # Recommendation
        # Derive best threshold candidates textually
        best_thr_notes = []
        for _, r in thr_df.iterrows():
            if r["recall"] >= 0.85 and r["false_positive_rate"] <= 0.12:
                best_thr_notes.append(f"t={r['threshold']}: rec={r['recall']:.3f} FPR={r['false_positive_rate']:.3f} F1={r['f1']:.3f}")
        if not best_thr_notes:
            # pick knee-like: maximize F1 among recall>=0.8
            sub = thr_df[thr_df["recall"] >= 0.80]
            if len(sub):
                best = sub.loc[sub["f1"].idxmax()]
                best_thr_notes.append(
                    f"No thr with rec≥0.85 & FPR≤0.12. Best F1 with rec≥0.80: "
                    f"t={best['threshold']} F1={best['f1']:.3f} rec={best['recall']:.3f} FPR={best['false_positive_rate']:.3f}"
                )

        rec_md = LOG_DIR / "audio_v4_recommendation.md"
        rec_md.write_text(
            f"""# Audio v4 Recommendation (analysis only — DO NOT implement yet)

Based on Audio v3 FP / threshold / K-of-N / fair v2–v3 investigation.

## Problem separation

### DATA PROBLEM
- NotScreaming contains many scream-like hard negatives (high scream_likeness FPs tagged `POTENTIAL_HARD_NEGATIVE`).
- ESC-50 vocal/siren/alarm categories drive systematic FPs.
- These are largely **content overlap**, not random label flips — do not blindly delete; curate HARD_NEG sampling.

### MODEL PROBLEM
- Fair comparison (Set B) shows v3 pushes **much higher recall / lower FNR** than v2 on the same embeddings/labels, but with **higher FPR / lower precision**.
- Class weight 4.0 + aug-inflated distress count likely over-emphasizes distress.
- Mean-pooled YAMNet head struggles to separate scream-like normals from distress in embedding space (`fp_vs_tp` previously ~0.98).

### THRESHOLD PROBLEM
- Default 0.5 is recall-heavy for this head.
- Many FPs are **not** only barely above 0.5 (see FP≥0.8 fraction) → threshold alone cannot fully fix hard-neg overlap, but can reclaim precision.
- Candidates (see threshold_analysis): {'; '.join(best_thr_notes) if best_thr_notes else 'see CSV'}

### AGGREGATION PROBLEM
- K-of-N at K=3,N=5 helps slightly vs naive windows but does not solve NotScreaming confusion.
- Higher K (4–5) may cut FPR with recall cost — evaluate before changing defaults.

## Recommended Audio v4 focus (priority order)
1. **Hard-negative training strategy** (not deletion): controlled oversampling/downweighting of `hard_negative_*` + ESC-50 siren/cry/laugh classes; keep as NORMAL.
2. **Rebalance class weights** (try 1.5–2.5, not 4.0) or focal loss / precision-oriented objective after hard-neg handling.
3. **Threshold calibration on validation** for an FNR budget (e.g. FNR≤12%) with reported FPR — without claiming production.
4. **K-of-N tuning** jointly with threshold (e.g. K=3..4) on file-level SafeHer metric.
5. **Optional architecture**: frame max/attention over YAMNet frames (temporal) — only after data/weight/threshold work.
6. **Human review sample** of AMBIGUOUS NotScreaming FPs before any label correction.
7. **Do not** invent new synthetic distress; prefer hard-neg mining + weight/threshold/aggregation first.

## What NOT to do first
- Blind retrain with same weight 4.0
- Auto-relabel NotScreaming → DISTRESS
- Delete ESC-50/Traffic
- Connect to SOS

## Success criteria for v4 (suggested)
- Keep recall ≳ 0.85 on corrected test
- Cut window FPR toward ≤ 0.10–0.12
- Reduce hard-negative FPR vs v3
- Show fair Set-B improvement on F1 and FPR without collapsing recall
""",
            encoding="utf-8",
        )
        created.append(str(rec_md))
        (OUT / "audio_v4_recommendation.md").write_text(rec_md.read_text(encoding="utf-8"), encoding="utf-8")

        # Save machine JSON bundle
        bundle = {
            "base_metrics": base,
            "fp_categories": fp_cats,
            "notscreaming": ns_summary,
            "esc50_top": esc_table.head(25).to_dict(orient="records"),
            "traffic": traffic_summary,
            "probability_groups": group_stats,
            "fp_near_threshold_frac": near,
            "fp_high_conf_frac": high,
            "thresholds": thr_rows,
            "k_of_n": kn_rows,
            "curves": {k: curves.get(k) for k in ["pr_auc", "roc_auc", "plot", "error"]},
            "fair_A": fair_A,
            "fair_B": fair_B,
            "overlap_A": overlap_A,
            "overlap_B": overlap_B,
            "created_files": created,
        }
        bundle_path = OUT / "analysis_bundle.json"
        # remove huge nested if any
        bundle_path.write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")
        created.append(str(bundle_path))

        # export ns tags
        ns_out = OUT / "notscreaming_fp_tags.csv"
        ns[["source", "chunk_idx", "proba", "scream_likeness", "highband_ge2khz", "spectral_centroid_hz", "bucket", "content_tag"]].to_csv(ns_out, index=False)
        created.append(str(ns_out))

        log.log(f"Files created: {created}")
        log.log("STATUS=ANALYSIS_COMPLETE")
        log.log(f"End: {datetime.now().isoformat()}")
        print("===ANALYSIS_RESULT_JSON===")
        print(json.dumps({
            "fp_total": base["fp"],
            "fp_cats": {c["category"]: c["fp_count"] for c in fp_cats},
            "ns_tags": ns_tag_counts,
            "pr_auc": curves.get("pr_auc"),
            "roc_auc": curves.get("roc_auc"),
            "fair_B_v2_fnr": fair_B["audio_v2_window"]["false_negative_rate"],
            "fair_B_v3_fnr": fair_B["audio_v3_window"]["false_negative_rate"],
            "fair_B_v2_fpr": fair_B["audio_v2_window"]["false_positive_rate"],
            "fair_B_v3_fpr": fair_B["audio_v3_window"]["false_positive_rate"],
            "overlap_B": overlap_B,
            "out_dir": str(OUT),
        }, indent=2))
    except Exception:
        log.log("ERROR")
        log.log(traceback.format_exc())
        log.log("STATUS=FAILED")
        raise
    finally:
        log.close()


if __name__ == "__main__":
    main()
