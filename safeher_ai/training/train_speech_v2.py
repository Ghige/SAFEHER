"""
SafeHer Speech v2 — binary EMERGENCY vs NORMAL training

Uses ONLY the prepared dataset:
  data/derived/speech_v2_prep/

- Keeps original 191 emergency recordings (features from derived copies; originals untouched)
- Uses 4,500 NORMAL clips as the negative class
- Leakage-aware TRAIN / VALIDATION / TEST splits
- Existing 8x audio augmentation recipe applied ONLY to training EMERGENCY
- Does NOT augment val/test; does NOT modify original audio files
- Saves model to data/models/speech_v2/
- Does NOT connect to SOS / Android / backend / Audio / Movement models

Run:
  ..\\venv311\\Scripts\\python.exe training\\train_speech_v2.py
"""

from __future__ import annotations

import json
import platform
import re
import sys
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path

import joblib
import librosa
import numpy as np
import pandas as pd
import soundfile as sf
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PREP = DATA / "derived" / "speech_v2_prep"
META_CSV = PREP / "metadata" / "speech_metadata.csv"
SPLITS_DIR = PREP / "splits"
MODEL_DIR = DATA / "models" / "speech_v2"
LOG_DIR = DATA / "training_logs"

SAMPLE_RATE = 16000
MAX_SECONDS = 2.0
CHUNK_SAMPLES = int(SAMPLE_RATE * MAX_SECONDS)
N_MFCC = 40
NOISE_LEVELS = [0.10, 0.20, 0.35]
TRAIN_RATIO, VAL_RATIO, TEST_RATIO = 0.70, 0.15, 0.15
RANDOM_STATE = 42
VOLUME_DB_LEVELS = [-6.0, -12.0, -18.0]

PHRASE_ORDER = ["help_me", "i_need_help", "mujhe_bachao", "madat_karo"]
LANG_ORDER = ["english", "hindi", "marathi"]


class Logger:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
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


def peak_normalize(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32)
    peak = float(np.max(np.abs(x))) + 1e-9
    return (x / peak).astype(np.float32)


def normalize_emergency_base(original_id: str) -> str:
    """Collapse Copy variants of the same emergency recording for leakage control."""
    s = str(original_id)
    s = re.sub(r"\s*-\s*Copy(\s*\(\d+\))?", "", s, flags=re.IGNORECASE)
    s = re.sub(r"_+Copy(_\d+)?", "", s, flags=re.IGNORECASE)
    s = re.sub(r"_mono$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[_\s]+", " ", s).strip().lower()
    return s


def make_group_key(row: pd.Series) -> str:
    label = str(row["safeher_label"]).upper()
    lang = str(row["language"]).lower()
    if label == "EMERGENCY":
        phrase = str(row.get("phrase") or "").strip().lower()
        base = normalize_emergency_base(row.get("original_id") or row["clip_id"])
        return f"em::{lang}::{phrase}::{base}"
    spk = row.get("speaker_id")
    if pd.notna(spk) and str(spk).strip():
        return f"nm::spk::{lang}::{str(spk).strip()}"
    # FLEURS original_id is a transcript/index shared across languages — use clip_id
    return f"nm::clip::{row['clip_id']}"


def load_wave(path: Path) -> np.ndarray:
    audio, sr = sf.read(str(path), always_2d=False)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    audio = audio.astype(np.float32)
    if sr != SAMPLE_RATE:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=SAMPLE_RATE)
    return peak_normalize(audio)


def to_chunk(audio: np.ndarray) -> np.ndarray:
    if len(audio) < CHUNK_SAMPLES:
        return np.pad(audio, (0, CHUNK_SAMPLES - len(audio))).astype(np.float32)
    return audio[:CHUNK_SAMPLES].astype(np.float32)


def mfcc_features_from_audio(audio: np.ndarray) -> np.ndarray:
    chunk = to_chunk(peak_normalize(audio))
    mfcc = librosa.feature.mfcc(y=chunk, sr=SAMPLE_RATE, n_mfcc=N_MFCC)
    return np.concatenate(
        [mfcc.mean(axis=1), mfcc.std(axis=1), mfcc.min(axis=1), mfcc.max(axis=1)]
    ).astype(np.float32)


def list_audio(root: Path) -> list[Path]:
    exts = {".wav", ".mp3", ".mpeg", ".m4a", ".flac", ".ogg"}
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in exts)


def build_noise_bank(log: Logger) -> list[np.ndarray]:
    bank: list[np.ndarray] = []
    noise_dir = DATA / "raw" / "noise"
    if noise_dir.exists():
        for p in list_audio(noise_dir)[:20]:
            try:
                bank.append(peak_normalize(load_wave(p)[: CHUNK_SAMPLES * 5]))
            except Exception:
                pass
    for rel in ["Traffic", "airplane", "cars", "Truck"]:
        d = DATA / "raw" / "normal" / rel
        if not d.exists():
            continue
        for p in list_audio(d)[:6]:
            try:
                bank.append(peak_normalize(load_wave(p)[: CHUNK_SAMPLES * 5]))
            except Exception:
                pass
    if not bank:
        log.log("WARNING: no ambient noise bank; using synthetic noise")
        rng = np.random.default_rng(RANDOM_STATE)
        bank = [rng.normal(0, 0.05, CHUNK_SAMPLES * 5).astype(np.float32)]
    log.log(f"Noise bank clips: {len(bank)}")
    return bank


def noise_chunk(bank: list[np.ndarray]) -> np.ndarray:
    src = bank[np.random.randint(0, len(bank))]
    if len(src) >= CHUNK_SAMPLES:
        start = np.random.randint(0, len(src) - CHUNK_SAMPLES + 1)
        n = src[start : start + CHUNK_SAMPLES]
    else:
        n = np.tile(src, (CHUNK_SAMPLES // max(len(src), 1)) + 1)[:CHUNK_SAMPLES]
    return peak_normalize(n.astype(np.float32))


def augment_chunk(chunk: np.ndarray, bank: list[np.ndarray]) -> list[np.ndarray]:
    """Same 8x recipe as prepare_audio_v3_dataset / 01_prepare_dataset (train only)."""
    versions = [chunk.copy()]
    for level in NOISE_LEVELS:
        noise = noise_chunk(bank)
        versions.append(peak_normalize((1 - level) * chunk + level * noise))
    for steps in [2, -2]:
        try:
            shifted = librosa.effects.pitch_shift(chunk, sr=SAMPLE_RATE, n_steps=steps)
            versions.append(peak_normalize(shifted.astype(np.float32)))
        except Exception:
            versions.append(chunk.copy())
    for rate in [1.1, 0.9]:
        try:
            stretched = librosa.effects.time_stretch(chunk, rate=rate)[:CHUNK_SAMPLES]
            if len(stretched) < CHUNK_SAMPLES:
                stretched = np.pad(stretched, (0, CHUNK_SAMPLES - len(stretched)))
            versions.append(peak_normalize(stretched.astype(np.float32)))
        except Exception:
            versions.append(chunk.copy())
    return versions


def split_groups_stratified(df: pd.DataFrame, log: Logger) -> pd.DataFrame:
    """
    Assign each leakage group to exactly one split.
    Stratify by language + label (+ phrase for emergency) at the group level.
    """
    work = df.copy()
    work["group_key"] = work.apply(make_group_key, axis=1)
    work["split"] = ""

    # One stratum row per group
    gmeta = (
        work.groupby("group_key", as_index=False)
        .agg(
            language=("language", "first"),
            safeher_label=("safeher_label", "first"),
            phrase=("phrase", "first"),
            n=("clip_id", "count"),
        )
    )
    gmeta["stratum"] = gmeta.apply(
        lambda r: f"{r['safeher_label']}|{r['language']}|"
        + (str(r["phrase"]) if str(r["safeher_label"]).upper() == "EMERGENCY" else "na"),
        axis=1,
    )

    assign: dict[str, str] = {}
    rng = np.random.RandomState(RANDOM_STATE)

    for stratum, sub in gmeta.groupby("stratum"):
        keys = sub["group_key"].tolist()
        rng.shuffle(keys)
        n = len(keys)
        if n == 1:
            # Prefer train for singleton strata
            assign[keys[0]] = "train"
            log.log(f"Split note: singleton stratum {stratum} -> train")
            continue
        if n == 2:
            assign[keys[0]] = "train"
            assign[keys[1]] = "test"
            log.log(f"Split note: 2-group stratum {stratum} -> train/test")
            continue
        n_test = max(1, int(round(n * TEST_RATIO)))
        n_val = max(1, int(round(n * VAL_RATIO)))
        if n_test + n_val >= n:
            n_test = 1
            n_val = 1
        n_train = n - n_test - n_val
        for k in keys[:n_train]:
            assign[k] = "train"
        for k in keys[n_train : n_train + n_val]:
            assign[k] = "validation"
        for k in keys[n_train + n_val :]:
            assign[k] = "test"

    work["split"] = work["group_key"].map(assign)
    missing = work["split"].eq("").sum()
    if missing:
        raise RuntimeError(f"{missing} clips missing split assignment")

    log.log(
        "Group counts by split: "
        + str(work.drop_duplicates("group_key").groupby("split").size().to_dict())
    )
    log.log("Clip counts by split: " + str(work.groupby("split").size().to_dict()))
    for split in ["train", "validation", "test"]:
        part = work[work["split"] == split]
        log.log(
            f"  {split}: EM={int((part.safeher_label=='EMERGENCY').sum())} "
            f"NM={int((part.safeher_label=='NORMAL').sum())} "
            f"by_lang={dict(Counter(part.language))} "
            f"em_phrase={dict(Counter(part.loc[part.safeher_label=='EMERGENCY','phrase']))}"
        )
    return work


def binary_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", pos_label=1, zero_division=0
    )
    fpr = float(fp / (fp + tn)) if (fp + tn) else 0.0
    fnr = float(fn / (fn + tp)) if (fn + tp) else 0.0
    out = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "fpr": fpr,
        "fnr": fnr,
        "confusion_matrix": {
            "labels": ["NORMAL(0)", "EMERGENCY(1)"],
            "matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
    }
    try:
        out["pr_auc"] = float(average_precision_score(y_true, y_prob))
    except Exception:
        out["pr_auc"] = None
    try:
        out["roc_auc"] = float(roc_auc_score(y_true, y_prob))
    except Exception:
        out["roc_auc"] = None
    return out


def per_language_metrics(
    df_split: pd.DataFrame, y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray
) -> dict:
    out = {}
    langs = df_split["language"].values
    for lang in LANG_ORDER:
        mask = langs == lang
        if mask.sum() == 0:
            continue
        out[lang] = binary_metrics(y_true[mask], y_pred[mask], y_prob[mask])
        out[lang]["support"] = int(mask.sum())
        out[lang]["emergency_support"] = int(np.sum(y_true[mask] == 1))
        out[lang]["normal_support"] = int(np.sum(y_true[mask] == 0))
    return out


def per_phrase_metrics(
    df_split: pd.DataFrame, y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray
) -> dict:
    """Detection performance on EMERGENCY clips of each phrase (recall of EMERGENCY)."""
    out = {}
    phrases = df_split["phrase"].fillna("").astype(str).str.lower().values
    for phrase in PHRASE_ORDER:
        mask = (y_true == 1) & (phrases == phrase)
        n = int(mask.sum())
        if n == 0:
            out[phrase] = {"support": 0, "recall": None, "detected": 0}
            continue
        detected = int(np.sum(y_pred[mask] == 1))
        out[phrase] = {
            "support": n,
            "detected": detected,
            "missed": n - detected,
            "recall": float(detected / n),
            "mean_emergency_prob": float(np.mean(y_prob[mask])),
        }
    return out


def resolve_local_path(rel: str) -> Path:
    p = Path(rel)
    if not p.is_absolute():
        p = ROOT / p
    return p


def main():
    started = datetime.now()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    SPLITS_DIR.mkdir(parents=True, exist_ok=True)

    log_path = LOG_DIR / "speech_v2_training_latest.log"
    summary_path = LOG_DIR / "speech_v2_training_summary.md"
    log = Logger(log_path)
    status = "FAILED"
    results: dict = {}

    try:
        log.log("=" * 70)
        log.log("SafeHer SPEECH v2 training — binary EMERGENCY vs NORMAL")
        log.log(f"Dataset: {PREP}")
        log.log("NOT connected to SOS. Original audio files will not be modified.")
        log.log("=" * 70)
        log.log(f"Start: {started.isoformat()}")
        log.log(f"Python: {sys.version}")
        log.log(f"Platform: {platform.platform()}")
        import sklearn

        log.log(
            f"numpy={np.__version__} pandas={pd.__version__} "
            f"sklearn={sklearn.__version__} librosa={librosa.__version__}"
        )

        if not META_CSV.exists():
            raise FileNotFoundError(f"Missing prepared metadata: {META_CSV}")

        df = pd.read_csv(META_CSV)
        df = df[df["status"].astype(str).str.upper().isin(["COPIED", "OK", "READY"])].copy()
        df = df[df["safeher_label"].isin(["EMERGENCY", "NORMAL"])].copy()
        log.log(f"Loaded metadata rows: {len(df)}")
        log.log(f"Label counts: {df['safeher_label'].value_counts().to_dict()}")
        log.log(f"Language counts: {df.groupby(['safeher_label','language']).size().to_dict()}")

        n_em = int((df.safeher_label == "EMERGENCY").sum())
        n_nm = int((df.safeher_label == "NORMAL").sum())
        if n_em != 191:
            log.log(f"WARNING: expected 191 EMERGENCY, found {n_em}")
        if n_nm != 4500:
            log.log(f"WARNING: expected 4500 NORMAL, found {n_nm}")

        # Leakage-aware splits
        df = split_groups_stratified(df, log)
        split_csv = SPLITS_DIR / "speech_v2_splits.csv"
        df[
            [
                "clip_id",
                "safeher_label",
                "language",
                "phrase",
                "group_key",
                "split",
                "local_path",
                "source_path",
                "speaker_id",
                "original_id",
            ]
        ].to_csv(split_csv, index=False)
        log.log(f"Wrote split table: {split_csv}")

        # Verify no group leakage across splits
        g2s = df.groupby("group_key")["split"].nunique()
        if (g2s > 1).any():
            raise RuntimeError("Leakage detected: group appears in multiple splits")
        log.log("Leakage check OK: each group_key in exactly one split")

        # Feature extract (unaugmented) for all splits from derived local_path only
        log.log("Extracting MFCC features from derived prep WAVs (originals untouched)...")
        feats = []
        keep = []
        corrupt = []
        for i, row in df.iterrows():
            path = resolve_local_path(row["local_path"])
            try:
                audio = load_wave(path)
                feat = mfcc_features_from_audio(audio)
                feats.append(feat)
                keep.append(i)
            except Exception as e:
                corrupt.append((row["clip_id"], str(e)))
        if corrupt:
            log.log(f"Corrupt/unreadable: {len(corrupt)}")
            for c in corrupt[:20]:
                log.log(f"  {c}")
        df = df.loc[keep].reset_index(drop=True)
        X_all = np.vstack(feats)
        y_all = (df["safeher_label"].values == "EMERGENCY").astype(np.int64)
        log.log(f"Usable clips after feature extract: {len(df)}")

        train_mask = df["split"].values == "train"
        val_mask = df["split"].values == "validation"
        test_mask = df["split"].values == "test"

        X_train_base = X_all[train_mask]
        y_train_base = y_all[train_mask]
        df_train = df[train_mask].reset_index(drop=True)
        X_val = X_all[val_mask]
        y_val = y_all[val_mask]
        df_val = df[val_mask].reset_index(drop=True)
        X_test = X_all[test_mask]
        y_test = y_all[test_mask]
        df_test = df[test_mask].reset_index(drop=True)

        log.log(
            f"Base split sizes: train={len(df_train)} val={len(df_val)} test={len(df_test)}"
        )

        # Train-only augmentation on EMERGENCY (existing 8x pipeline); originals not written
        np.random.seed(RANDOM_STATE)
        bank = build_noise_bank(log)
        log.log("Applying 8x augmentation ONLY to TRAIN EMERGENCY (in-memory features)...")
        aug_feats = []
        aug_y = []
        em_train = df_train[df_train["safeher_label"] == "EMERGENCY"]
        for _, row in em_train.iterrows():
            path = resolve_local_path(row["local_path"])
            chunk = to_chunk(load_wave(path))
            versions = augment_chunk(chunk, bank)
            # versions[0] is original — already in X_train_base; add augs 1..7 only
            for ver in versions[1:]:
                aug_feats.append(mfcc_features_from_audio(ver))
                aug_y.append(1)
        log.log(f"Augmented EMERGENCY feature rows added: {len(aug_feats)} (7x per train EM clip)")
        log.log("Validation/test: NO augmentation")

        if aug_feats:
            X_train = np.vstack([X_train_base, np.vstack(aug_feats)])
            y_train = np.concatenate([y_train_base, np.array(aug_y, dtype=np.int64)])
        else:
            X_train = X_train_base
            y_train = y_train_base
        log.log(
            f"Final TRAIN size: {len(y_train)} "
            f"(EM={int(y_train.sum())} NM={int((y_train==0).sum())})"
        )

        scaler = StandardScaler()
        Xtr = scaler.fit_transform(X_train)
        Xva = scaler.transform(X_val)
        Xte = scaler.transform(X_test)

        model_cfg = {
            "model": "RandomForestClassifier",
            "n_estimators": 400,
            "max_depth": 24,
            "min_samples_leaf": 2,
            "class_weight": "balanced_subsample",
            "random_state": RANDOM_STATE,
            "features": f"MFCC({N_MFCC}) mean/std/min/max over {MAX_SECONDS}s @ {SAMPLE_RATE}Hz",
            "task": "binary EMERGENCY vs NORMAL",
            "augmentation": {
                "recipe": "8x (orig+3 noise+pitch±2+speed 1.1/0.9)",
                "applied_to": "train EMERGENCY only (augs 1-7; orig already in train)",
                "val_test_augmented": False,
            },
            "dataset": str(PREP.as_posix()),
            "split_ratios": {"train": TRAIN_RATIO, "validation": VAL_RATIO, "test": TEST_RATIO},
            "leakage_control": "group_key = emergency base-recording OR speaker_id OR clip_id",
        }
        log.log(f"Model config: {json.dumps(model_cfg)}")

        clf = RandomForestClassifier(
            n_estimators=400,
            max_depth=24,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
        t0 = datetime.now()
        clf.fit(Xtr, y_train)
        train_secs = (datetime.now() - t0).total_seconds()
        log.log(f"Training duration seconds: {train_secs:.2f}")

        # Validation (threshold selection optional — use 0.5 default)
        val_prob = clf.predict_proba(Xva)[:, 1]
        val_pred = (val_prob >= 0.5).astype(np.int64)
        val_metrics = binary_metrics(y_val, val_pred, val_prob)
        log.log(f"VALIDATION metrics: {json.dumps(val_metrics)}")

        # Untouched test
        test_prob = clf.predict_proba(Xte)[:, 1]
        test_pred = (test_prob >= 0.5).astype(np.int64)
        test_metrics = binary_metrics(y_test, test_pred, test_prob)
        lang_metrics = per_language_metrics(df_test, y_test, test_pred, test_prob)
        phrase_metrics = per_phrase_metrics(df_test, y_test, test_pred, test_prob)

        log.log(f"TEST metrics: {json.dumps(test_metrics)}")
        log.log(f"Per-language: {json.dumps(lang_metrics)}")
        log.log(f"Per-phrase: {json.dumps(phrase_metrics)}")

        # Synthetic low-volume robustness on TEST EMERGENCY (existing pipeline supports gain probe)
        log.log("LOW-VOLUME EVAL: synthetic gain reduction on TEST EMERGENCY (derived features only)")
        volume_results = {}
        em_test = df_test[df_test["safeher_label"] == "EMERGENCY"].reset_index(drop=True)
        for db in VOLUME_DB_LEVELS:
            gain = float(10 ** (db / 20.0))
            feats_v = []
            y_v = []
            phrases_v = []
            for _, row in em_test.iterrows():
                audio = load_wave(resolve_local_path(row["local_path"]))
                quiet = (audio * gain).astype(np.float32)
                # Do NOT re-peak-normalize before features — preserve lower volume
                quiet_chunk = to_chunk(quiet)
                mfcc = librosa.feature.mfcc(y=quiet_chunk, sr=SAMPLE_RATE, n_mfcc=N_MFCC)
                feat = np.concatenate(
                    [mfcc.mean(axis=1), mfcc.std(axis=1), mfcc.min(axis=1), mfcc.max(axis=1)]
                ).astype(np.float32)
                feats_v.append(feat)
                y_v.append(1)
                phrases_v.append(str(row.get("phrase") or "").lower())
            if not feats_v:
                volume_results[f"{db:g}dB"] = {"available": False}
                continue
            Xv = scaler.transform(np.vstack(feats_v))
            pv = clf.predict_proba(Xv)[:, 1]
            predv = (pv >= 0.5).astype(np.int64)
            recall = float(np.mean(predv == 1))
            per_ph = {}
            for ph in PHRASE_ORDER:
                m = np.array(phrases_v) == ph
                if m.sum() == 0:
                    continue
                per_ph[ph] = float(np.mean(predv[m] == 1))
            volume_results[f"{db:g}dB"] = {
                "available": True,
                "gain_linear": gain,
                "emergency_support": len(y_v),
                "recall": recall,
                "mean_prob": float(np.mean(pv)),
                "per_phrase_recall": per_ph,
                "note": "Synthetic attenuation after load; not a labeled whisper corpus",
            }
            log.log(
                f"  volume {db:g}dB: recall={recall:.4f} mean_prob={float(np.mean(pv)):.4f} "
                f"per_phrase={per_ph}"
            )

        # Save model artifacts (overwrite speech_v2 folder with new binary model)
        joblib.dump(clf, MODEL_DIR / "speech_binary_model.joblib")
        joblib.dump(scaler, MODEL_DIR / "scaler.joblib")
        # Keep phrase encoder stub removed; write label map for binary
        label_map = {"NORMAL": 0, "EMERGENCY": 1}
        (MODEL_DIR / "label_map.json").write_text(json.dumps(label_map, indent=2), encoding="utf-8")

        metrics_blob = {
            "version": "speech_v2",
            "task": "binary EMERGENCY vs NORMAL",
            "connected_to_sos": False,
            "dataset": "data/derived/speech_v2_prep",
            "counts": {
                "emergency_total": n_em,
                "normal_total": n_nm,
                "train_base": int(len(df_train)),
                "train_with_aug": int(len(y_train)),
                "validation": int(len(df_val)),
                "test": int(len(df_test)),
                "train_aug_emergency_extra": int(len(aug_feats)),
            },
            "model": model_cfg,
            "train_seconds": train_secs,
            "validation": val_metrics,
            "test": test_metrics,
            "per_language_test": lang_metrics,
            "per_emergency_phrase_test": phrase_metrics,
            "low_volume_synthetic_test": volume_results,
            "threshold": 0.5,
        }
        (MODEL_DIR / "metrics.json").write_text(json.dumps(metrics_blob, indent=2), encoding="utf-8")
        (MODEL_DIR / "confusion_matrix.json").write_text(
            json.dumps(test_metrics["confusion_matrix"], indent=2), encoding="utf-8"
        )
        (MODEL_DIR / "feature_config.json").write_text(
            json.dumps(
                {
                    "sample_rate": SAMPLE_RATE,
                    "max_seconds": MAX_SECONDS,
                    "n_mfcc": N_MFCC,
                    "feature_dim": int(X_train.shape[1]),
                    "stats": ["mean", "std", "min", "max"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (MODEL_DIR / "model_metadata.json").write_text(
            json.dumps(
                {
                    "name": "speech_v2",
                    "created": started.isoformat(),
                    "task": "binary EMERGENCY vs NORMAL",
                    "languages": LANG_ORDER,
                    "phrases": PHRASE_ORDER,
                    "connected_to_sos": False,
                    "artifacts": [
                        "speech_binary_model.joblib",
                        "scaler.joblib",
                        "label_map.json",
                        "metrics.json",
                        "feature_config.json",
                        "confusion_matrix.json",
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (MODEL_DIR / "LIMITATIONS.txt").write_text(
            "\n".join(
                [
                    "Speech v2 binary EMERGENCY vs NORMAL.",
                    "Trained on SafeHer emergency phrases + Google FLEURS normals.",
                    "Speaker IDs mostly unavailable; leakage controlled via group_key.",
                    "Low-volume results are synthetic attenuation, not whisper-labeled data.",
                    "NOT connected to SOS.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        # Remove obsolete multi-class-only artifacts if present (optional cleanup note)
        old_phrase = MODEL_DIR / "speech_phrase_model.joblib"
        if old_phrase.exists():
            log.log(f"Note: previous multi-class artifact remains: {old_phrase.name} (new primary is speech_binary_model.joblib)")

        status = "SUCCESS"
        results = metrics_blob

        # Markdown summary
        cm = test_metrics["confusion_matrix"]
        md = f"""# Speech v2 Training Summary

**STATUS:** {status}  
**Started:** {started.isoformat()}  
**Finished:** {datetime.now().isoformat()}  
**Model dir:** `safeher_ai/data/models/speech_v2/`  
**Connected to SOS:** NO

## Dataset

| Class | Count |
|-------|------:|
| EMERGENCY | {n_em} |
| NORMAL | {n_nm} |

Source: `safeher_ai/data/derived/speech_v2_prep/` only.  
Original audio files were **not** modified. Augmentation applied **only** to TRAIN EMERGENCY (in-memory).

## Splits (leakage-aware)

| Split | Clips | EM | NM |
|-------|------:|---:|---:|
| train (base) | {len(df_train)} | {int((df_train.safeher_label=='EMERGENCY').sum())} | {int((df_train.safeher_label=='NORMAL').sum())} |
| train (+aug EM) | {len(y_train)} | {int(y_train.sum())} | {int((y_train==0).sum())} |
| validation | {len(df_val)} | {int(y_val.sum())} | {int((y_val==0).sum())} |
| test | {len(df_test)} | {int(y_test.sum())} | {int((y_test==0).sum())} |

Group key: emergency base-recording (Copy variants collapsed) / speaker_id if present / else clip_id.

## Test metrics (untouched)

| Metric | Value |
|--------|------:|
| Accuracy | {test_metrics['accuracy']:.4f} |
| Precision | {test_metrics['precision']:.4f} |
| Recall | {test_metrics['recall']:.4f} |
| F1 | {test_metrics['f1']:.4f} |
| FPR | {test_metrics['fpr']:.4f} |
| FNR | {test_metrics['fnr']:.4f} |
| PR-AUC | {test_metrics['pr_auc']} |
| ROC-AUC | {test_metrics['roc_auc']} |

### Confusion matrix

```
labels: {cm['labels']}
TN={cm['tn']} FP={cm['fp']}
FN={cm['fn']} TP={cm['tp']}
matrix={cm['matrix']}
```

## Per-language (test)

"""
        for lang in LANG_ORDER:
            m = lang_metrics.get(lang)
            if not m:
                md += f"- **{lang}:** no test samples\n"
                continue
            md += (
                f"- **{lang}** (n={m['support']}, EM={m['emergency_support']}): "
                f"acc={m['accuracy']:.4f} P={m['precision']:.4f} R={m['recall']:.4f} "
                f"F1={m['f1']:.4f} FPR={m['fpr']:.4f} FNR={m['fnr']:.4f} "
                f"PR-AUC={m['pr_auc']} ROC-AUC={m['roc_auc']}\n"
            )

        md += "\n## Per-emergency-phrase (test EMERGENCY recall)\n\n"
        for ph in PHRASE_ORDER:
            m = phrase_metrics.get(ph, {})
            md += (
                f"- **{ph}**: support={m.get('support')} detected={m.get('detected')} "
                f"recall={m.get('recall')} mean_prob={m.get('mean_emergency_prob')}\n"
            )

        md += "\n## Low-volume synthetic evaluation (TEST EMERGENCY)\n\n"
        md += "Pipeline supports synthetic attenuation probe (not a labeled whisper set).\n\n"
        for k, v in volume_results.items():
            md += (
                f"- **{k}**: recall={v.get('recall')} mean_prob={v.get('mean_prob')} "
                f"per_phrase={v.get('per_phrase_recall')}\n"
            )

        md += f"""

## Validation snapshot

acc={val_metrics['accuracy']:.4f} P={val_metrics['precision']:.4f} R={val_metrics['recall']:.4f} F1={val_metrics['f1']:.4f}

## Artifacts

- `speech_binary_model.joblib`
- `scaler.joblib`
- `label_map.json`
- `metrics.json`
- `feature_config.json`
- `confusion_matrix.json`
- Splits: `data/derived/speech_v2_prep/splits/speech_v2_splits.csv`
- Log: `data/training_logs/speech_v2_training_latest.log`

Train seconds: {train_secs:.2f}
"""
        summary_path.write_text(md, encoding="utf-8")
        log.log(f"Wrote summary: {summary_path}")
        log.log(f"STATUS={status}")

    except Exception as e:
        status = "FAILED"
        log.log(f"ERROR: {e}")
        log.log(traceback.format_exc())
        summary_path.write_text(
            f"# Speech v2 Training Summary\n\n**STATUS:** FAILED\n\n```\n{e}\n```\n",
            encoding="utf-8",
        )
        raise
    finally:
        log.close()

    # Print concise results for the agent/user
    print("\n" + "=" * 70)
    print(f"STATUS={status}")
    if results:
        tm = results["test"]
        print(
            f"TEST acc={tm['accuracy']:.4f} P={tm['precision']:.4f} "
            f"R={tm['recall']:.4f} F1={tm['f1']:.4f} "
            f"FPR={tm['fpr']:.4f} FNR={tm['fnr']:.4f} "
            f"PR-AUC={tm['pr_auc']} ROC-AUC={tm['roc_auc']}"
        )
        print(f"CM={tm['confusion_matrix']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
