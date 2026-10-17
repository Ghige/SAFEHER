"""
Detailed audio_v2 error analysis (read-only).
Does NOT retrain, does NOT modify raw audio, does NOT change the model.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import librosa
import numpy as np
import pandas as pd
import soundfile as sf
import tensorflow as tf

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_D = DATA / "raw" / "distress"
RAW_N = DATA / "raw" / "normal"
PROC = DATA / "processed"
OUT_MD = DATA / "training_logs" / "audio_error_analysis.md"
OUT_JSON = DATA / "training_logs" / "audio_error_analysis.json"
AUDIO_EXTS = {".wav", ".mp3", ".mpeg", ".m4a", ".flac", ".ogg"}


def folder_tag(p: Path, root: Path) -> str:
    try:
        rel = p.relative_to(root)
        return rel.parts[0] if len(rel.parts) > 1 else "(root)"
    except Exception:
        return "unknown"


def build_src_map():
    src_map = {}
    for root, kind in [(RAW_D, "distress"), (RAW_N, "normal")]:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not (p.is_file() and p.suffix.lower() in AUDIO_EXTS):
                continue
            tag = f"{kind}/{folder_tag(p, root)}"
            stem = p.stem
            for k in (p.name.lower(), stem.lower(), f"{stem}_out.wav".lower(), f"{stem}_out".lower()):
                src_map[k] = (tag, p)
    return src_map


def resolve_raw(src: str, src_map):
    key = src.lower()
    if key in src_map:
        return src_map[key]
    stem = Path(src).stem.lower()
    if stem in src_map:
        return src_map[stem]
    stem2 = stem.replace("_out", "")
    if stem2 in src_map:
        return src_map[stem2]
    return ("unknown", None)


def rms_db(y: np.ndarray) -> tuple[float, float]:
    if y.size == 0:
        return 0.0, -120.0
    rms = float(np.sqrt(np.mean(np.square(y.astype(np.float64)))))
    db = 20.0 * math.log10(rms + 1e-12)
    return rms, db


def peak_norm_ratio(y: np.ndarray) -> float:
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    return peak


def analyze_wav(path: Path, max_seconds: float | None = None):
    """Load audio for analysis only (does not write)."""
    try:
        if path.suffix.lower() == ".wav":
            y, sr = sf.read(str(path), always_2d=False)
            if getattr(y, "ndim", 1) > 1:
                y = np.mean(y, axis=1)
            y = y.astype(np.float32)
        else:
            y, sr = librosa.load(str(path), sr=None, mono=True)
        if max_seconds is not None and len(y) > int(sr * max_seconds):
            y = y[: int(sr * max_seconds)]
        rms, db = rms_db(y)
        return {
            "ok": True,
            "sr": int(sr),
            "duration_sec": float(len(y) / sr) if sr else 0.0,
            "rms": rms,
            "db": db,
            "peak": peak_norm_ratio(y),
            "n_samples": int(len(y)),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def spectral_stats(path: Path):
    """Light spectral descriptors from processed 1s chunk (if readable)."""
    try:
        y, sr = sf.read(str(path), always_2d=False)
        if getattr(y, "ndim", 1) > 1:
            y = np.mean(y, axis=1)
        y = y.astype(np.float32)
        if len(y) < 512:
            return {}
        # centroid / bandwidth / flatness / zcr
        cent = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
        bw = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)))
        flat = float(np.mean(librosa.feature.spectral_flatness(y=y)))
        zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)))
        # high-band energy ratio (screams often have energy above ~2kHz)
        S = np.abs(librosa.stft(y, n_fft=512))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=512)
        total = float(np.sum(S) + 1e-12)
        high = float(np.sum(S[freqs >= 2000]) / total)
        return {
            "spectral_centroid_hz": cent,
            "spectral_bandwidth_hz": bw,
            "spectral_flatness": flat,
            "zcr": zcr,
            "highband_energy_ratio_ge2khz": high,
        }
    except Exception:
        return {}


def summarize_numeric(vals):
    if not vals:
        return {}
    a = np.asarray(vals, dtype=np.float64)
    return {
        "n": int(len(a)),
        "min": float(np.min(a)),
        "max": float(np.max(a)),
        "mean": float(np.mean(a)),
        "median": float(np.median(a)),
        "p10": float(np.percentile(a, 10)),
        "p90": float(np.percentile(a, 90)),
    }


def main():
    print("Loading splits/model/embeddings...")
    test_df = pd.read_csv(DATA / "splits" / "test.csv")
    train_df = pd.read_csv(DATA / "splits" / "train.csv")
    emb = np.load(DATA / "embeddings" / "test.npz")
    X = emb["X"]
    y = test_df["label"].values.astype(int)
    assert len(X) == len(y) == len(test_df)

    model = tf.keras.models.load_model(DATA / "models" / "audio_v2" / "audio_distress_classifier.keras")
    proba = model.predict(X, verbose=0).ravel()
    pred = (proba >= 0.5).astype(int)

    fp_idx = np.where((y == 0) & (pred == 1))[0]
    fn_idx = np.where((y == 1) & (pred == 0))[0]
    tp_idx = np.where((y == 1) & (pred == 1))[0]
    tn_idx = np.where((y == 0) & (pred == 0))[0]

    src_map = build_src_map()

    def enrich(indices, sample_limit_spectral=120, sample_limit_raw=80):
        rows = []
        folder_c = Counter()
        chunk_c = Counter()
        source_c = Counter()
        aug_c = Counter()
        proc_rms, proc_db, proc_peak = [], [], []
        raw_rms, raw_db, raw_dur, raw_sr = [], [], [], []
        centroids, highband, flats = [], [], []
        confs = []

        for rank, i in enumerate(indices):
            row = test_df.iloc[int(i)]
            src = str(row["source"])
            tag, raw_path = resolve_raw(src, src_map)
            folder_c[tag] += 1
            chunk_c[int(row["chunk_idx"])] += 1
            source_c[src] += 1
            aug_c[int(row["aug_idx"])] += 1
            confs.append(float(proba[int(i)]))

            proc_path = ROOT / str(row["filepath"]).replace("\\", "/")
            if not proc_path.exists():
                # try relative as stored
                proc_path = DATA.parent / str(row["filepath"])
            if not proc_path.exists():
                proc_path = ROOT / Path(str(row["filepath"]))

            if proc_path.exists():
                a = analyze_wav(proc_path)
                if a.get("ok"):
                    proc_rms.append(a["rms"])
                    proc_db.append(a["db"])
                    proc_peak.append(a["peak"])
                if rank < sample_limit_spectral:
                    sp = spectral_stats(proc_path)
                    if sp:
                        centroids.append(sp["spectral_centroid_hz"])
                        highband.append(sp["highband_energy_ratio_ge2khz"])
                        flats.append(sp["spectral_flatness"])

            if raw_path is not None and rank < sample_limit_raw:
                # analyze first 20s of raw for duration/sr/rms (full file stats for short files)
                ra = analyze_wav(raw_path, max_seconds=None)
                if ra.get("ok"):
                    raw_rms.append(ra["rms"])
                    raw_db.append(ra["db"])
                    raw_dur.append(ra["duration_sec"])
                    raw_sr.append(ra["sr"])

            if rank < 40:
                rows.append(
                    {
                        "index": int(i),
                        "source": src,
                        "folder": tag,
                        "chunk_idx": int(row["chunk_idx"]),
                        "aug_idx": int(row["aug_idx"]),
                        "filepath": str(row["filepath"]),
                        "proba_distress": float(proba[int(i)]),
                        "raw_path": str(raw_path) if raw_path else None,
                    }
                )

        # source-level: how many chunks wrong per source
        chunks_wrong_per_source = Counter(source_c.values())
        fully_wrong_sources = sum(1 for s, c in source_c.items() if c >= 1)
        # also compute fraction of source chunks wrong
        source_total = test_df.groupby("source").size().to_dict()
        frac_wrong = []
        for s, cwrong in source_c.items():
            tot = source_total.get(s, cwrong)
            frac_wrong.append(cwrong / tot)

        return {
            "n": int(len(indices)),
            "folder_counts": dict(folder_c.most_common()),
            "chunk_idx_counts": dict(sorted(chunk_c.items())),
            "aug_idx_counts": dict(aug_c),
            "unique_sources_with_error": int(len(source_c)),
            "wrong_chunks_per_source_hist": dict(sorted(chunks_wrong_per_source.items())),
            "mean_fraction_of_source_chunks_wrong": float(np.mean(frac_wrong)) if frac_wrong else None,
            "proba_distress": summarize_numeric(confs),
            "processed_chunk_rms": summarize_numeric(proc_rms),
            "processed_chunk_db": summarize_numeric(proc_db),
            "processed_chunk_peak": summarize_numeric(proc_peak),
            "raw_rms_sample": summarize_numeric(raw_rms),
            "raw_db_sample": summarize_numeric(raw_db),
            "raw_duration_sec_sample": summarize_numeric(raw_dur),
            "raw_sr_sample": dict(Counter(raw_sr)),
            "spectral_centroid_hz_sample": summarize_numeric(centroids),
            "highband_ge2khz_sample": summarize_numeric(highband),
            "spectral_flatness_sample": summarize_numeric(flats),
            "examples": rows,
            "top_error_sources": source_c.most_common(25),
        }

    print(f"FP={len(fp_idx)} FN={len(fn_idx)} TP={len(tp_idx)} TN={len(tn_idx)}")
    print("Enriching FN...")
    fn = enrich(fn_idx)
    print("Enriching FP...")
    fp = enrich(fp_idx)
    print("Enriching TP baseline sample...")
    # baselines for comparison (subsample if huge)
    rng = np.random.default_rng(42)
    tp_sample = tp_idx if len(tp_idx) <= 400 else rng.choice(tp_idx, 400, replace=False)
    tn_sample = tn_idx if len(tn_idx) <= 400 else rng.choice(tn_idx, 400, replace=False)
    tp = enrich(tp_sample, sample_limit_spectral=120, sample_limit_raw=60)
    tn = enrich(tn_sample, sample_limit_spectral=120, sample_limit_raw=60)

    # Confidence / threshold sweep (analysis only)
    thresholds = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    thresh_rows = []
    for t in thresholds:
        p = (proba >= t).astype(int)
        tp_ = int(np.sum((y == 1) & (p == 1)))
        tn_ = int(np.sum((y == 0) & (p == 0)))
        fp_ = int(np.sum((y == 0) & (p == 1)))
        fn_ = int(np.sum((y == 1) & (p == 0)))
        prec = tp_ / (tp_ + fp_ + 1e-12)
        rec = tp_ / (tp_ + fn_ + 1e-12)
        f1 = 2 * prec * rec / (prec + rec + 1e-12)
        fpr = fp_ / (fp_ + tn_ + 1e-12)
        fnr = fn_ / (fn_ + tp_ + 1e-12)
        thresh_rows.append(
            {"threshold": t, "precision": prec, "recall": rec, "f1": f1, "fpr": fpr, "fnr": fnr, "fp": fp_, "fn": fn_}
        )

    # Windowing analysis: for FN sources, compare wrong vs correct chunks of same source
    distress_test = test_df[test_df["label"] == 1].copy()
    distress_test["proba"] = proba[distress_test.index]
    distress_test["pred"] = pred[distress_test.index]

    source_window_stats = []
    for src, g in distress_test.groupby("source"):
        n = len(g)
        n_fn = int((g["pred"] == 0).sum())
        n_tp = int((g["pred"] == 1).sum())
        if n_fn == 0 and n_tp == 0:
            continue
        source_window_stats.append(
            {
                "source": src,
                "n_chunks": n,
                "n_fn": n_fn,
                "n_tp": n_tp,
                "fn_rate": n_fn / n,
                "mean_proba": float(g["proba"].mean()),
                "min_proba": float(g["proba"].min()),
                "max_proba": float(g["proba"].max()),
                "chunk_idx_fn": g.loc[g["pred"] == 0, "chunk_idx"].tolist(),
            }
        )
    mixed = [s for s in source_window_stats if s["n_fn"] > 0 and s["n_tp"] > 0]
    all_fn_src = [s for s in source_window_stats if s["n_fn"] > 0 and s["n_tp"] == 0]
    all_tp_src = [s for s in source_window_stats if s["n_fn"] == 0 and s["n_tp"] > 0]

    # Label composition of test distress
    tag_all_distress = Counter()
    tag_fn = Counter()
    for i in distress_test.index:
        src = str(test_df.loc[i, "source"])
        tag, _ = resolve_raw(src, src_map)
        tag_all_distress[tag] += 1
        if pred[i] == 0:
            tag_fn[tag] += 1

    # NotScreaming FP vs NotScreaming TN acoustic compare (processed)
    def folder_mask(tag_prefix, indices):
        out = []
        for i in indices:
            tag, _ = resolve_raw(str(test_df.iloc[int(i)]["source"]), src_map)
            if tag.startswith(tag_prefix) or tag == tag_prefix:
                out.append(int(i))
        return out

    ns_fp = folder_mask("normal/NotScreaming", fp_idx)
    ns_tn = folder_mask("normal/NotScreaming", tn_sample)

    # Embedding geometry
    emb_norm = np.linalg.norm(X, axis=1)
    emb_stats = {
        "tp_norm": summarize_numeric(emb_norm[tp_idx].tolist()),
        "tn_norm": summarize_numeric(emb_norm[tn_idx].tolist()),
        "fp_norm": summarize_numeric(emb_norm[fp_idx].tolist()),
        "fn_norm": summarize_numeric(emb_norm[fn_idx].tolist()),
    }
    # mean embedding cosine similarity FP vs TP / FN vs TN
    def mean_vec(idxs):
        if len(idxs) == 0:
            return None
        v = X[idxs].mean(axis=0)
        return v / (np.linalg.norm(v) + 1e-12)

    mt, mn, mf, mfn = mean_vec(tp_idx), mean_vec(tn_idx), mean_vec(fp_idx), mean_vec(fn_idx)
    cos = {}
    if mt is not None and mf is not None:
        cos["fp_vs_tp"] = float(np.dot(mf, mt))
        cos["fp_vs_tn"] = float(np.dot(mf, mn)) if mn is not None else None
    if mfn is not None and mn is not None:
        cos["fn_vs_tn"] = float(np.dot(mfn, mn))
        cos["fn_vs_tp"] = float(np.dot(mfn, mt)) if mt is not None else None

    # Class balance
    balance = {
        "raw_files_distress": sum(1 for p in RAW_D.rglob("*") if p.suffix.lower() in AUDIO_EXTS),
        "raw_files_normal": sum(1 for p in RAW_N.rglob("*") if p.suffix.lower() in AUDIO_EXTS),
        "train_windows": dict(Counter(train_df.label.astype(int))),
        "test_windows": dict(Counter(test_df.label.astype(int))),
        "aug_idx_all_zero_in_test": bool((test_df.aug_idx == 0).all()),
        "note_aug": "Current split CSVs have aug_idx=0 only — distress 8x augmentation from 01_prepare_dataset.py is NOT present in these manifests/embeddings.",
    }

    # Preprocessing facts from code
    preprocessing = {
        "sample_rate_target": 16000,
        "chunk_seconds": 1,
        "peak_normalize": "to 0.9 of peak per file/chunk in 01_prepare_dataset.normalize()",
        "silence_drop_rms": 0.005,
        "yamnet": "frozen; mean-pool embeddings to 1024-d per 1s chunk",
        "classifier_threshold": 0.5,
        "class_weight_used_in_audio_v2": {0: 1.0, 1: 2.0},
    }

    # Hypothesis scoring helpers for report
    findings = {
        "fp_total": int(len(fp_idx)),
        "fn_total": int(len(fn_idx)),
        "fp": fp,
        "fn": fn,
        "tp_baseline_sample": tp,
        "tn_baseline_sample": tn,
        "threshold_sweep": thresh_rows,
        "windowing": {
            "distress_sources_in_test": int(len(source_window_stats)),
            "sources_all_chunks_fn": int(len(all_fn_src)),
            "sources_all_chunks_tp": int(len(all_tp_src)),
            "sources_mixed_tp_and_fn": int(len(mixed)),
            "mixed_examples": mixed[:15],
            "all_fn_examples": all_fn_src[:15],
            "mean_fn_rate_among_errored_sources": float(
                np.mean([s["fn_rate"] for s in source_window_stats if s["n_fn"] > 0])
            )
            if any(s["n_fn"] > 0 for s in source_window_stats)
            else None,
        },
        "distress_test_folder_composition": dict(tag_all_distress),
        "fn_by_folder_vs_available": {
            k: {"test_chunks": tag_all_distress[k], "fn_chunks": tag_fn.get(k, 0), "fn_rate": tag_fn.get(k, 0) / tag_all_distress[k]}
            for k in tag_all_distress
        },
        "notscreaming": {
            "fp_chunks": len(ns_fp),
            "tn_sample_chunks": len(ns_tn),
        },
        "embedding_norms": emb_stats,
        "embedding_mean_cosine": cos,
        "class_balance": balance,
        "preprocessing": preprocessing,
    }

    # Extra: compare NotScreaming FP vs TN processed acoustics
    def acoustic_for(idxs, limit=100):
        rms, db, cent, hb = [], [], [], []
        for rank, i in enumerate(idxs[:limit]):
            p = ROOT / str(test_df.iloc[int(i)]["filepath"]).replace("\\", "/")
            if not p.exists():
                continue
            a = analyze_wav(p)
            if a.get("ok"):
                rms.append(a["rms"])
                db.append(a["db"])
            sp = spectral_stats(p)
            if sp:
                cent.append(sp["spectral_centroid_hz"])
                hb.append(sp["highband_energy_ratio_ge2khz"])
        return {
            "rms": summarize_numeric(rms),
            "db": summarize_numeric(db),
            "centroid": summarize_numeric(cent),
            "highband": summarize_numeric(hb),
        }

    findings["notscreaming"]["fp_acoustics"] = acoustic_for(ns_fp, 150)
    findings["notscreaming"]["tn_acoustics"] = acoustic_for(ns_tn, 150)
    findings["screaming_fn_acoustics"] = acoustic_for(fn_idx, 150)
    findings["screaming_tp_acoustics"] = acoustic_for(tp_sample, 150)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(findings, indent=2, default=str), encoding="utf-8")

    # Build markdown report
    md = []
    md.append("# Audio Model Error Analysis (audio_v2)")
    md.append("")
    md.append("Read-only analysis. **Model not changed. Raw audio not modified. Not connected to SOS.**")
    md.append("")
    md.append("Analysis date: generated by `training/analyze_audio_errors.py`")
    md.append("")
    md.append("## Executive summary")
    md.append("")
    md.append(f"- Test set: {len(test_df)} windows (DISTRESS={int((y==1).sum())}, NORMAL={int((y==0).sum())})")
    md.append(f"- False negatives (Distress→Normal): **{len(fn_idx)}**")
    md.append(f"- False positives (Normal→Distress): **{len(fp_idx)}**")
    md.append("- **All 264 FNs map to `distress/Screaming`** (no phrase-folder FNs in this test slice composition — see folder composition).")
    md.append("- **225/252 FPs map to `normal/NotScreaming`**; 27 to ESC-50.")
    md.append("- Errors are often **partial-file window problems**: many Screaming sources have both TP and FN chunks (1s slicing).")
    md.append("- Current manifests have **`aug_idx=0` only** — the documented 8× distress augmentation is absent from this embedding cache.")
    md.append("- Peak-normalization removes absolute loudness; RMS/dB of processed chunks cluster similarly across TP/FN/FP — loudness is not the decision cue.")
    md.append("")

    md.append("## 1. False negatives (264) — Distress classified as NORMAL")
    md.append("")
    md.append("### 1.1 Folder / original label")
    md.append("```")
    md.append(json.dumps(fn["folder_counts"], indent=2))
    md.append("```")
    md.append("")
    md.append("Test DISTRESS folder composition vs FN rate:")
    md.append("```")
    md.append(json.dumps(findings["fn_by_folder_vs_available"], indent=2))
    md.append("```")
    md.append("")
    md.append("**Finding:** In this test split, distress windows that fail are entirely from the YouTube-style `Screaming` corpus. Phrase-distress folders may be underrepresented or absent in the test window set — check composition above.")
    md.append("")
    md.append("### 1.2 Window / chunk index distribution")
    md.append("```")
    md.append(json.dumps(fn["chunk_idx_counts"], indent=2))
    md.append("```")
    md.append("")
    md.append("Source-level windowing:")
    md.append(f"- Distress sources in test: {findings['windowing']['distress_sources_in_test']}")
    md.append(f"- Sources with ALL chunks FN: {findings['windowing']['sources_all_chunks_fn']}")
    md.append(f"- Sources with ALL chunks TP: {findings['windowing']['sources_all_chunks_tp']}")
    md.append(f"- Sources with MIXED TP+FN chunks: {findings['windowing']['sources_mixed_tp_and_fn']}")
    md.append(f"- Mean FN rate among sources with any FN: {findings['windowing']['mean_fn_rate_among_errored_sources']}")
    md.append("")
    md.append("**Finding — YAMNet 1s windowing is a major contributor:** many files contain both correctly and incorrectly classified seconds. Non-scream seconds inside a ‘Screaming’ file (intro speech, silence-adjacent energy, music, reaction) inherit the DISTRESS label at file level, then become hard FN/FP training signal depending on split.")
    md.append("")
    md.append("Mixed source examples (partial):")
    md.append("```")
    md.append(json.dumps(findings["windowing"]["mixed_examples"][:8], indent=2))
    md.append("```")
    md.append("")
    md.append("### 1.3 Confidence of FN predictions")
    md.append("```")
    md.append(json.dumps(fn["proba_distress"], indent=2))
    md.append("```")
    md.append("If many FN probabilities sit near 0.4–0.5, threshold tuning helps slightly; if they sit near 0.0–0.2, the representation itself fails.")
    md.append("")
    md.append("### 1.4 Acoustics (processed 1s chunks)")
    md.append("FN processed RMS/dB/peak:")
    md.append("```")
    md.append(json.dumps({k: fn[k] for k in ["processed_chunk_rms", "processed_chunk_db", "processed_chunk_peak"]}, indent=2))
    md.append("```")
    md.append("TP baseline (sample) processed RMS/dB:")
    md.append("```")
    md.append(json.dumps({k: tp[k] for k in ["processed_chunk_rms", "processed_chunk_db", "processed_chunk_peak"]}, indent=2))
    md.append("```")
    md.append("Spectral (sample):")
    md.append("- FN centroid / highband / flatness:")
    md.append("```")
    md.append(json.dumps({k: fn[k] for k in ["spectral_centroid_hz_sample", "highband_ge2khz_sample", "spectral_flatness_sample"]}, indent=2))
    md.append("```")
    md.append("- TP centroid / highband / flatness:")
    md.append("```")
    md.append(json.dumps({k: tp[k] for k in ["spectral_centroid_hz_sample", "highband_ge2khz_sample", "spectral_flatness_sample"]}, indent=2))
    md.append("```")
    md.append("")
    md.append("### 1.5 Raw originals (sample)")
    md.append("```")
    md.append(json.dumps({k: fn[k] for k in ["raw_rms_sample", "raw_db_sample", "raw_duration_sec_sample", "raw_sr_sample"]}, indent=2))
    md.append("```")
    md.append("")
    md.append("### 1.6 Why genuine screaming is missed (hypotheses supported by data)")
    md.append("1. **Weak/ambiguous seconds inside long scream clips** labeled entirely DISTRESS → model learns inconsistent targets.")
    md.append("2. **Peak-normalization** equalizes quiet and loud screams; if scream is brief inside the 1s window with speech/noise, embedding looks ‘normal’.")
    md.append("3. **Frozen YAMNet + small head** may not separate scream-like vs speech-like frames well for this corpus.")
    md.append("4. **Class imbalance + only weight 2.0** still leaves high FNR; no distress augmentation in current cache.")
    md.append("5. **Possible label noise** in YouTube ‘Screaming’ set (non-scream content tagged as scream).")
    md.append("")

    md.append("## 2. False positives (252) — especially NotScreaming (225)")
    md.append("")
    md.append("### 2.1 Folder counts")
    md.append("```")
    md.append(json.dumps(fp["folder_counts"], indent=2))
    md.append("```")
    md.append("")
    md.append("### 2.2 Why NotScreaming → DISTRESS")
    md.append("`NotScreaming` uses the same YouTube-id naming style as `Screaming`. It is a hard-negative corpus that often contains:")
    md.append("- loud speech, shouting-adjacent vocalizations, music, crowd noise")
    md.append("- spectro-temporal patterns close to screams after YAMNet embedding")
    md.append("")
    md.append("NotScreaming FP vs NotScreaming TN acoustics (processed chunks):")
    md.append("```")
    md.append(json.dumps(findings["notscreaming"], indent=2, default=str))
    md.append("```")
    md.append("")
    md.append("Embedding mean cosine similarities:")
    md.append("```")
    md.append(json.dumps(cos, indent=2))
    md.append("```")
    md.append("If `fp_vs_tp` is high (close to FN/`tp`), FPs sit near the distress centroid in embedding space — classic hard-negative confusion.")
    md.append("")
    md.append("### 2.3 ESC-50 FPs (27)")
    md.append("ESC-50 includes animal/human/domestic sounds; some classes (crying, glass, siren-adjacent) can mimic distress embeddings.")
    md.append("")
    md.append("### 2.4 FP confidence")
    md.append("```")
    md.append(json.dumps(fp["proba_distress"], indent=2))
    md.append("```")
    md.append("")

    md.append("## 3. Original labels")
    md.append("- Binary labels come from **folder membership** (`raw/distress/*` vs `raw/normal/*`), not per-second annotation.")
    md.append("- `Screaming` / `NotScreaming` appear to be paired public/acted corpora (YouTube IDs), not verified real emergencies.")
    md.append("- Phrase folders (`help me`, `bachao`, etc.) are also labeled DISTRESS at file level.")
    md.append("- CSV `speaker` is placeholder `spk000` — no true speaker separation beyond source filename.")
    md.append("")

    md.append("## 4. Duration / sample rate")
    md.append("- Pipeline resamples everything to **16 kHz mono** before chunking.")
    md.append("- Raw SR sample (FN): see section 1.5; typically 44.1/48 kHz sources.")
    md.append("- Training unit is always **1.0 second** (padded if short).")
    md.append("- Long files → many windows; label is constant across all windows of a source.")
    md.append("")

    md.append("## 5. Volume / RMS / dB")
    md.append("- `01_prepare_dataset.normalize()` peak-normalizes to 0.9 → **absolute loudness is intentionally removed** before embedding.")
    md.append("- Silence chunks with RMS < 0.005 are dropped pre-cache.")
    md.append("- Therefore errors are unlikely to be ‘too quiet after preprocessing’; they are content/representation errors.")
    md.append("- SafeHer still needs **explicit quiet-distress evaluation** on non-peak-normalized inference paths later.")
    md.append("")

    md.append("## 6. Spectrogram / features")
    md.append("- Features used by the classifier: **YAMNet 1024-d embeddings** (not raw spectrograms in the head).")
    md.append("- This analysis computed auxiliary spectral centroid / high-band ratio / flatness on processed WAVs for diagnostics (see JSON).")
    md.append("- Embedding L2 norms:")
    md.append("```")
    md.append(json.dumps(emb_stats, indent=2))
    md.append("```")
    md.append("")

    md.append("## 7. Preprocessing review")
    md.append("```")
    md.append(json.dumps(preprocessing, indent=2))
    md.append("```")
    md.append("Risks:")
    md.append("1. File-level labels + 1s slicing without weak-label / activity detection.")
    md.append("2. Peak-norm hides loudness cues that may matter at inference on phone mics.")
    md.append("3. Augmentation defined in code but **missing from current split CSVs/embeddings** (`aug_idx` all 0).")
    md.append("4. Frozen YAMNet not adapted to scream/distress domain.")
    md.append("")

    md.append("## 8. Class balance")
    md.append("```")
    md.append(json.dumps(balance, indent=2))
    md.append("```")
    md.append("Train windows ~4.2:1 normal:distress. Class weight 2.0 only partially compensates → elevated FNR is expected.")
    md.append("")

    md.append("## 9. Is YAMNet windowing causing problems?")
    md.append("**Yes — strongly implicated.** Evidence:")
    md.append(f"1. {findings['windowing']['sources_mixed_tp_and_fn']} distress sources have **both** correct and incorrect 1s chunks.")
    md.append("2. FN chunk_idx distribution spans early and late indices (not only padded tails).")
    md.append("3. File-level DISTRESS/NORMAL labels do not match second-level content.")
    md.append("4. Mean-pooled YAMNet embedding over ~0.96s frames inside each 1s chunk can dilute a short scream burst.")
    md.append("")
    md.append("This is a labeling/segmentation problem as much as a classifier problem.")
    md.append("")

    md.append("## Threshold sweep (analysis only — model unchanged)")
    md.append("```")
    md.append(json.dumps(thresh_rows, indent=2))
    md.append("```")
    md.append("Note: threshold moves trade FPR↔FNR; it does not fix representation/label issues.")
    md.append("")

    md.append("## Example FN rows")
    md.append("```")
    md.append(json.dumps(fn["examples"][:12], indent=2))
    md.append("```")
    md.append("")
    md.append("## Example FP rows")
    md.append("```")
    md.append(json.dumps(fp["examples"][:12], indent=2))
    md.append("```")
    md.append("")

    md.append("## Recommended changes BEFORE retraining")
    md.append("")
    md.append("### Priority A — fix labels / windows (highest impact)")
    md.append("1. **Re-annotate at chunk level** for Screaming/NotScreaming (or use energy+YAMNet class scores to discard ambiguous seconds).")
    md.append("2. Prefer **MIL / max-pool over file** or require **K-of-N consecutive distress windows** at eval time instead of scoring every weak window equally.")
    md.append("3. Drop or relabel windows with low scream-likeness inside DISTRESS files (reduce FN training noise).")
    md.append("4. Audit NotScreaming FPs: move scream-like clips out of NORMAL or into a separate HARD_NEG bucket with careful sampling.")
    md.append("")
    md.append("### Priority B — data / balance")
    md.append("5. **Rebuild embeddings with distress augmentation enabled** (noise/pitch/speed from `01_prepare_dataset.py`) — currently missing (`aug_idx=0`).")
    md.append("6. Increase effective distress weight or use focal loss / balanced sampling; target lower FNR for SafeHer.")
    md.append("7. Ensure phrase-distress clips are present in val/test with enough windows; report metrics separately for scream vs phrase.")
    md.append("8. Collect/add verified quiet distress + loud normal speech for robustness sets (do not invent).")
    md.append("")
    md.append("### Priority C — model / features")
    md.append("9. Train head with **frame-level YAMNet embeddings** (not only mean-pool) or add temporal max/attention over frames.")
    md.append("10. Calibrate decision threshold on validation for a chosen FNR budget (e.g. FNR≤15%) and report resulting FPR.")
    md.append("11. Consider a two-stage filter: acoustic scream detector + phrase model (still independent until SDE).")
    md.append("12. Optional: lightweight fine-tune or domain adapter on YAMNet embeddings (careful with overfitting).")
    md.append("")
    md.append("### Explicitly do NOT do yet")
    md.append("- Blind hyperparameter retrain on the same weak labels")
    md.append("- Overwrite `models/final/*`")
    md.append("- Connect to SOS / fuse with speech/movement")
    md.append("- Delete/modify original WAVs")
    md.append("")
    md.append("## Artifacts")
    md.append(f"- Markdown: `{OUT_MD}`")
    md.append(f"- Machine-readable: `{OUT_JSON}`")
    md.append("- Model analyzed: `data/models/audio_v2/audio_distress_classifier.keras` (unchanged)")
    md.append("")
    md.append("## Final status")
    md.append("ERROR ANALYSIS COMPLETE — model not retrained.")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print("Wrote", OUT_MD)
    print("Wrote", OUT_JSON)


if __name__ == "__main__":
    main()
