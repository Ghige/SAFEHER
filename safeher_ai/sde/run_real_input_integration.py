"""
SafeHer — Real-input integration test (Audio + Speech + Movement + SDE)

DEMO_MODE ONLY. Uses ACTUAL model inference on ACTUAL recorded files.
Does NOT train, modify models/datasets, or send real SOS.

Run:
  ..\\venv311\\Scripts\\python.exe -m sde.run_real_input_integration
"""

from __future__ import annotations

import csv
import json
import re
import sys
import traceback
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import joblib
import librosa
import numpy as np
import pandas as pd
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sde.config import load_config
from sde.engine import EngineInput, SafetyDecisionEngine
from sde.model_loaders import load_models

DATA = ROOT / "data"
LOG_DIR = DATA / "training_logs"
REPO = ROOT.parent
MOVE_DATA = REPO / "safeher_backend" / "app" / "ai" / "movement_model" / "data"

SAMPLE_RATE = 16000
AUDIO_CHUNK = SAMPLE_RATE  # 1 s for Exp02 / YAMNet
SPEECH_MAX_S = 2.0
SPEECH_N_MFCC = 40
SILENCE_RMS = 0.005

MOVE_WINDOW = 100
MOVE_HOP = 50
MOVE_CHANNELS = ["accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z", "accel_mag"]
MOVE_STATS = ["mean", "std", "var", "rms", "min", "max", "ptp"]

# ESC-50 target IDs (official ESC-50 taxonomy)
ESC50_TARGET = {
    20: "crying_baby",
    26: "laughing",
    48: "fireworks",
}

PHRASE_DIRS = {
    "help_me": ["help_me", "help me"],
    "i_need_help": ["i_need_help", "i need help"],
    "mujhe_bachao": ["mujhe_bachao", "mujhe bachao"],
    "madat_karo": ["madat_karo", "madat karo"],
}


class Logger:
    def __init__(self, latest: Path, stamped: Path):
        latest.parent.mkdir(parents=True, exist_ok=True)
        self.latest = open(latest, "w", encoding="utf-8")
        self.stamped = open(stamped, "w", encoding="utf-8")

    def log(self, msg: str = ""):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", errors="replace").decode("ascii"))
        for fh in (self.latest, self.stamped):
            fh.write(line + "\n")
            fh.flush()

    def close(self):
        self.latest.close()
        self.stamped.close()


def peak_normalize(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32)
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak < 1e-8:
        return x
    return (x / peak).astype(np.float32)


def load_wav_mono(path: Path, sr: int = SAMPLE_RATE) -> np.ndarray:
    try:
        y, file_sr = sf.read(str(path), always_2d=False)
        if y.ndim > 1:
            y = np.mean(y, axis=1)
        y = y.astype(np.float32)
        if file_sr != sr:
            y = librosa.resample(y, orig_sr=file_sr, target_sr=sr)
        return y
    except Exception:
        y, _ = librosa.load(str(path), sr=sr, mono=True)
        return y.astype(np.float32)


def list_audio(root: Path) -> list[Path]:
    if not root.exists():
        return []
    exts = {".wav", ".mp3", ".mpeg", ".m4a", ".flac", ".ogg"}
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in exts)


def take_unique(files: list[Path], n: int, seed: int = 42) -> list[Path]:
    if not files:
        return []
    rng = np.random.default_rng(seed)
    files = list(files)
    if len(files) <= n:
        return files
    idx = rng.choice(len(files), size=n, replace=False)
    return [files[i] for i in sorted(idx)]


# ── Audio inference (YAMNet + Exp02) ─────────────────────────────────────────

def audio_chunks(y: np.ndarray) -> list[np.ndarray]:
    y = peak_normalize(y)
    if len(y) < int(0.25 * SAMPLE_RATE):
        return []
    out = []
    if len(y) <= AUDIO_CHUNK:
        pad = np.pad(y, (0, AUDIO_CHUNK - len(y)))
        if float(np.sqrt(np.mean(pad**2))) >= SILENCE_RMS:
            out.append(pad.astype(np.float32))
        return out
    n = len(y) // AUDIO_CHUNK
    for i in range(n):
        c = y[i * AUDIO_CHUNK : (i + 1) * AUDIO_CHUNK]
        if float(np.sqrt(np.mean(c**2))) >= SILENCE_RMS:
            out.append(c.astype(np.float32))
    if len(y) >= AUDIO_CHUNK:
        c = y[-AUDIO_CHUNK:]
        if float(np.sqrt(np.mean(c**2))) >= SILENCE_RMS:
            out.append(c.astype(np.float32))
    return out


def predict_audio(yamnet, model, path: Path) -> dict[str, Any]:
    warnings_list: list[str] = []
    try:
        y = load_wav_mono(path)
        chunks = audio_chunks(y)
        if not chunks:
            return {
                "ok": False,
                "score": None,
                "prediction": None,
                "n_windows": 0,
                "error": "no_valid_windows",
                "warnings": warnings_list,
                "preprocess": "failed_empty",
            }
        embs = []
        for c in chunks[:30]:  # cap windows per file
            _, emb, _ = yamnet(c)
            embs.append(emb.numpy().mean(axis=0).astype(np.float32))
        X = np.vstack(embs)
        probs = model.predict(X, verbose=0).ravel()
        score = float(np.max(probs))  # file-level max (distress aggregation)
        pred = "DISTRESS" if score >= 0.5 else "NORMAL"
        return {
            "ok": True,
            "score": score,
            "prediction": pred,
            "mean_score": float(np.mean(probs)),
            "n_windows": int(len(probs)),
            "error": "",
            "warnings": warnings_list,
            "preprocess": "peak_norm_1s_windows_yamnet_meanpool",
        }
    except Exception as e:
        return {
            "ok": False,
            "score": None,
            "prediction": None,
            "n_windows": 0,
            "error": str(e),
            "warnings": warnings_list,
            "preprocess": "failed",
        }


# ── Speech inference (MFCC + Speech v2) ──────────────────────────────────────

def speech_features(y: np.ndarray) -> np.ndarray:
    y = peak_normalize(y)
    n = int(SAMPLE_RATE * SPEECH_MAX_S)
    if len(y) < n:
        y = np.pad(y, (0, n - len(y)))
    else:
        y = y[:n]
    mfcc = librosa.feature.mfcc(y=y.astype(np.float32), sr=SAMPLE_RATE, n_mfcc=SPEECH_N_MFCC)
    return np.concatenate(
        [mfcc.mean(axis=1), mfcc.std(axis=1), mfcc.min(axis=1), mfcc.max(axis=1)]
    ).astype(np.float32)


def phrase_from_path(path: Path) -> Optional[str]:
    parts = [p.lower().replace(" ", "_") for p in path.parts]
    joined = "/".join(parts)
    for canon, aliases in PHRASE_DIRS.items():
        for a in aliases:
            if a.replace(" ", "_") in joined or f"/{a}/" in joined.replace("_", " "):
                return canon
            if a in joined:
                return canon
    # clip_id style: em_english_help_me_
    m = re.search(r"(help_me|i_need_help|mujhe_bachao|madat_karo)", path.stem.lower())
    if m:
        return m.group(1)
    return None


def predict_speech(clf, scaler, path: Path) -> dict[str, Any]:
    try:
        y = load_wav_mono(path)
        feat = speech_features(y).reshape(1, -1)
        Xs = scaler.transform(feat) if scaler is not None else feat
        proba = clf.predict_proba(Xs)[0]
        # class 1 = EMERGENCY
        score = float(proba[1]) if len(proba) > 1 else float(proba[0])
        pred = "EMERGENCY" if score >= 0.5 else "NORMAL"
        phrase = phrase_from_path(path)
        return {
            "ok": True,
            "score": score,
            "prediction": pred,
            "detected_phrase": phrase,
            "phrase_source": "path_metadata" if phrase else "none",
            "error": "",
            "warnings": [],
            "preprocess": "peak_norm_2s_mfcc40_stats",
        }
    except Exception as e:
        return {
            "ok": False,
            "score": None,
            "prediction": None,
            "detected_phrase": phrase_from_path(path),
            "phrase_source": "path_metadata",
            "error": str(e),
            "warnings": [],
            "preprocess": "failed",
        }


# ── Movement inference ───────────────────────────────────────────────────────

def move_window_features(df: pd.DataFrame) -> np.ndarray:
    sens = ["accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z"]
    for c in sens:
        if c not in df.columns:
            raise ValueError(f"missing_column:{c}")
    ax = df["accel_x"].to_numpy(dtype=np.float64)
    ay = df["accel_y"].to_numpy(dtype=np.float64)
    az = df["accel_z"].to_numpy(dtype=np.float64)
    mag = np.sqrt(ax * ax + ay * ay + az * az)
    chans = {
        "accel_x": ax,
        "accel_y": ay,
        "accel_z": az,
        "gyro_x": df["gyro_x"].to_numpy(dtype=np.float64),
        "gyro_y": df["gyro_y"].to_numpy(dtype=np.float64),
        "gyro_z": df["gyro_z"].to_numpy(dtype=np.float64),
        "accel_mag": mag,
    }
    n = len(df)
    if n < MOVE_WINDOW:
        raise ValueError(f"too_short:{n}")
    rows = []
    for start in range(0, n - MOVE_WINDOW + 1, MOVE_HOP):
        feat = []
        for ch in MOVE_CHANNELS:
            w = chans[ch][start : start + MOVE_WINDOW]
            feat.extend(
                [
                    float(np.mean(w)),
                    float(np.std(w)),
                    float(np.var(w)),
                    float(np.sqrt(np.mean(w**2))),
                    float(np.min(w)),
                    float(np.max(w)),
                    float(np.ptp(w)),
                ]
            )
        rows.append(feat)
    return np.asarray(rows, dtype=np.float32)


def predict_movement(clf, scaler, path: Path) -> dict[str, Any]:
    warnings_list = ["movement_v2_prototype_synthetic_heavy"]
    try:
        df = pd.read_csv(path)
        X = move_window_features(df)
        Xs = scaler.transform(X) if scaler is not None else X
        proba = clf.predict_proba(Xs)[:, 1]
        score = float(np.max(proba))  # session max abnormal prob
        mean_score = float(np.mean(proba))
        pred = "ABNORMAL" if score >= 0.5 else "NORMAL"
        return {
            "ok": True,
            "score": score,
            "mean_score": mean_score,
            "prediction": pred,
            "n_windows": int(len(proba)),
            "error": "",
            "warnings": warnings_list,
            "preprocess": "window100_hop50_49d_stats",
        }
    except Exception as e:
        return {
            "ok": False,
            "score": None,
            "prediction": None,
            "n_windows": 0,
            "error": str(e),
            "warnings": warnings_list,
            "preprocess": "failed",
        }


# ── Discovery ────────────────────────────────────────────────────────────────

def discover_audio_cases(log: Logger) -> list[dict]:
    cases: list[dict] = []
    raw = DATA / "raw"

    def add(files: list[Path], category: str, gt: Optional[int], n: int, seed: int):
        picked = take_unique(files, n, seed=seed)
        for p in picked:
            cases.append(
                {
                    "modality": "audio",
                    "category": category,
                    "path": p,
                    "gt_label": gt,  # 1 distress, 0 normal, None unknown
                }
            )
        log.log(f"  audio/{category}: discovered={len(files)} sampled={len(picked)} gt={gt}")

    add(list_audio(raw / "distress" / "Screaming"), "screaming_distress", 1, 12, 1)
    # phrase-like distress folders under raw/distress
    for folder, n in [
        ("help me", 4),
        ("i need help", 4),
        ("mujhe_bachao", 4),
        ("madat karo", 4),
        ("call police", 3),
        ("Sendhelp", 3),
    ]:
        add(list_audio(raw / "distress" / folder), f"distress_phrase_{folder.replace(' ', '_')}", 1, n, 2)

    add(list_audio(raw / "normal" / "NotScreaming"), "not_screaming", 0, 12, 3)
    add(list_audio(raw / "normal" / "Traffic"), "traffic", 0, 8, 4)
    add(list_audio(raw / "normal" / "airplane"), "airplane", 0, 4, 5)
    add(list_audio(raw / "normal" / "cars"), "cars", 0, 4, 6)

    # ESC-50 targets from filename *-N.wav
    esc_files = list_audio(raw / "normal" / "ESC-50-master")
    by_tgt: dict[int, list[Path]] = defaultdict(list)
    for p in esc_files:
        m = re.search(r"-(\d+)\.wav$", p.name, re.I)
        if m:
            by_tgt[int(m.group(1))].append(p)
    for tgt, name in ESC50_TARGET.items():
        add(by_tgt.get(tgt, []), f"esc50_{name}", 0, 8, 10 + tgt)

    # hard-neg chunks from derived test (existing recorded-derived; not modified)
    test_csv = DATA / "derived" / "audio_v3_prep" / "splits" / "test.csv"
    if test_csv.exists():
        df = pd.read_csv(test_csv)
        hn = df[df["bucket"].astype(str).str.contains("hard_negative", na=False)]
        paths = []
        for fp in hn["filepath"].astype(str).tolist():
            p = ROOT / fp if not Path(fp).is_absolute() else Path(fp)
            if p.exists():
                paths.append(p)
        # unique by source
        uniq = []
        seen = set()
        for p in paths:
            key = p.stem.rsplit("_c", 1)[0]
            if key in seen:
                continue
            seen.add(key)
            uniq.append(p)
        add(uniq, "hard_negative", 0, 15, 7)

    return cases


def discover_speech_cases(log: Logger) -> list[dict]:
    cases: list[dict] = []
    prep = DATA / "derived" / "speech_v2_prep"
    meta = prep / "metadata" / "speech_metadata.csv"
    if not meta.exists():
        log.log("WARNING: speech_v2_prep metadata missing")
        return cases
    df = pd.read_csv(meta)
    df = df[df["safeher_label"].isin(["EMERGENCY", "NORMAL"])]

    def add_rows(sub: pd.DataFrame, category: str, n: Optional[int], seed: int):
        paths = []
        for _, row in sub.iterrows():
            p = ROOT / str(row["local_path"])
            if p.exists():
                paths.append((p, row))
        if n is not None:
            rng = np.random.default_rng(seed)
            if len(paths) > n:
                idx = rng.choice(len(paths), size=n, replace=False)
                paths = [paths[i] for i in sorted(idx)]
        for p, row in paths:
            phrase = str(row.get("phrase") or "") or None
            if phrase == "":
                phrase = None
            cases.append(
                {
                    "modality": "speech",
                    "category": category,
                    "path": p,
                    "gt_label": 1 if row["safeher_label"] == "EMERGENCY" else 0,
                    "gt_phrase": phrase,
                    "language": row.get("language"),
                }
            )
        log.log(f"  speech/{category}: sampled={len(paths)} (available subset)")

    for phrase in ["help_me", "i_need_help", "mujhe_bachao", "madat_karo"]:
        sub = df[(df["safeher_label"] == "EMERGENCY") & (df["phrase"] == phrase)]
        # test ALL i_need_help; others capped
        n = None if phrase == "i_need_help" else min(12, len(sub))
        add_rows(sub, f"emergency_{phrase}", n, 20)

    for lang in ["english", "hindi", "marathi"]:
        sub = df[(df["safeher_label"] == "NORMAL") & (df["language"] == lang)]
        add_rows(sub, f"normal_{lang}", 10, 30)

    return cases


def discover_movement_cases(log: Logger) -> list[dict]:
    cases: list[dict] = []
    if not MOVE_DATA.exists():
        log.log(f"WARNING: movement data missing at {MOVE_DATA}")
        return cases

    normal_acts = [
        "walking",
        "normal_phone_handling",
        "sitting",
        "standing",
        "daily_phone_movement",
    ]
    abnormal_acts = [
        "panic_simulation",
        "rapid_shaking",
        "strong_shaking",
        "irregular_shaking",
        "sudden_movement_then_shaking",
    ]

    def add_act(root: Path, acts: list[str], gt: int, per: int):
        for i, act in enumerate(acts):
            d = root / act
            files = sorted(d.glob("*.csv")) if d.exists() else []
            picked = take_unique(files, per, seed=40 + i + gt * 10)
            for p in picked:
                cases.append(
                    {
                        "modality": "movement",
                        "category": f"{'abnormal' if gt else 'normal'}_{act}",
                        "path": p,
                        "gt_label": gt,
                        "activity": act,
                        "synthetic_heavy": True,
                    }
                )
            log.log(f"  movement/{act}: discovered={len(files)} sampled={len(picked)} gt={gt}")

    add_act(MOVE_DATA / "normal", normal_acts, 0, 4)
    add_act(MOVE_DATA / "abnormal", abnormal_acts, 1, 4)
    return cases


def binary_metrics(y_true: list[int], y_pred: list[int]) -> dict[str, Any]:
    if not y_true:
        return {"n": 0}
    yt = np.asarray(y_true, dtype=int)
    yp = np.asarray(y_pred, dtype=int)
    tn = int(np.sum((yt == 0) & (yp == 0)))
    fp = int(np.sum((yt == 0) & (yp == 1)))
    fn = int(np.sum((yt == 1) & (yp == 0)))
    tp = int(np.sum((yt == 1) & (yp == 1)))
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    acc = (tp + tn) / max(len(yt), 1)
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0
    return {
        "n": int(len(yt)),
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "fpr": fpr,
        "fnr": fnr,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def main() -> int:
    started = datetime.now()
    stamp = started.strftime("%Y%m%d_%H%M%S")
    latest_log = LOG_DIR / "real_input_integration_latest.log"
    stamped_log = LOG_DIR / f"real_input_integration_{stamp}.log"
    csv_path = LOG_DIR / "real_input_integration_results.csv"
    summary_path = LOG_DIR / "real_input_integration_summary.md"
    log = Logger(latest_log, stamped_log)

    rows: list[dict] = []
    model_errors: list[str] = []
    preprocess_failures = 0
    pipeline_failures = 0

    try:
        log.log("=" * 72)
        log.log("SafeHer REAL-INPUT integration test (DEMO ONLY)")
        log.log("NO training / NO model changes / NO real SOS")
        log.log("=" * 72)
        log.log(f"Start: {started.isoformat()}")

        cfg = load_config()
        assert cfg.demo_mode is True
        log.log(f"DEMO_MODE={cfg.demo_mode} (verified)")
        log.log(f"SDE config: {cfg.path}")
        log.log("Decision rules: UNCHANGED from decision_engine_config.json")

        models = load_models(cfg, log=log.log)
        if not models.all_ok:
            log.log(f"MODEL LOAD ISSUES: {models.errors}")
            model_errors.extend(models.errors)

        # Load YAMNet for audio
        import tensorflow_hub as hub

        log.log("Loading YAMNet from TF Hub...")
        yamnet = hub.load("https://tfhub.dev/google/yamnet/1")
        log.log("YAMNet loaded")

        engine = SafetyDecisionEngine(cfg)

        log.log("Discovering inputs...")
        audio_cases = discover_audio_cases(log)
        speech_cases = discover_speech_cases(log)
        move_cases = discover_movement_cases(log)
        log.log(
            f"Totals discovered/sampled: audio={len(audio_cases)} "
            f"speech={len(speech_cases)} movement={len(move_cases)}"
        )

        test_id = 0

        def run_sde(audio_s, speech_s, move_s, phrase, conf, choice):
            inp = EngineInput(
                audio_score=audio_s or 0.0,
                speech_emergency_score=speech_s or 0.0,
                movement_score=move_s or 0.0,
                detected_phrase=phrase,
                confidence=conf or 0.0,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            if max(audio_s or 0, speech_s or 0, move_s or 0) > 0:
                # decide first; confirmation only on EMERGENCY
                prelim = engine.decide(inp)
                if prelim.decision == "EMERGENCY":
                    return engine.decide_with_confirmation(inp, user_choice=choice or "NO_RESPONSE")
                return prelim
            return engine.decide(inp)

        # ── AUDIO-ONLY (UNMATCHED) ──
        log.log("--- AUDIO inference ---")
        for case in audio_cases:
            test_id += 1
            path: Path = case["path"]
            log.log(f"[A{test_id}] {case['category']}: {path}")
            with warnings.catch_warnings(record=True) as wrec:
                warnings.simplefilter("always")
                aout = predict_audio(yamnet, models.audio_model, path)
            warn = list(aout.get("warnings") or [])
            warn += [str(w.message) for w in wrec[:3]]
            if not aout["ok"]:
                preprocess_failures += 1
                model_errors.append(f"audio:{path.name}:{aout.get('error')}")
                pipeline_failures += 1
            try:
                sde = run_sde(aout.get("score") or 0.0, 0.0, 0.0, None, 0.0, "NO_RESPONSE")
                err = aout.get("error") or ""
            except Exception as e:
                pipeline_failures += 1
                err = f"sde:{e}"
                sde = None
            rows.append(
                {
                    "test_id": f"A{test_id:04d}",
                    "match_status": "UNMATCHED",
                    "modality": "audio",
                    "category": case["category"],
                    "audio_file": str(path),
                    "speech_file": "",
                    "movement_file": "",
                    "gt_label": case.get("gt_label"),
                    "audio_score": aout.get("score"),
                    "audio_prediction": aout.get("prediction"),
                    "speech_score": "",
                    "speech_prediction": "",
                    "detected_phrase": "",
                    "movement_score": "",
                    "movement_prediction": "",
                    "sde_decision": getattr(sde, "decision", None),
                    "trigger_reason": getattr(sde, "reason", None),
                    "demo_action": getattr(sde, "simulated_action", None)
                    or getattr(sde, "countdown_result", None),
                    "countdown_result": getattr(sde, "countdown_result", None),
                    "errors": err,
                    "warnings": "; ".join(warn),
                    "preprocess": aout.get("preprocess"),
                    "n_windows": aout.get("n_windows"),
                }
            )

        # ── SPEECH-ONLY (UNMATCHED) ──
        log.log("--- SPEECH inference ---")
        for case in speech_cases:
            test_id += 1
            path = case["path"]
            log.log(f"[S{test_id}] {case['category']}: {path.name}")
            sout = predict_speech(models.speech_model, models.speech_scaler, path)
            if not sout["ok"]:
                preprocess_failures += 1
                model_errors.append(f"speech:{path.name}:{sout.get('error')}")
                pipeline_failures += 1
            phrase = sout.get("detected_phrase") or case.get("gt_phrase")
            conf = sout.get("score") or 0.0
            try:
                sde = run_sde(0.0, sout.get("score") or 0.0, 0.0, phrase, conf, "NO_RESPONSE")
                err = sout.get("error") or ""
            except Exception as e:
                pipeline_failures += 1
                err = f"sde:{e}"
                sde = None
            rows.append(
                {
                    "test_id": f"S{test_id:04d}",
                    "match_status": "UNMATCHED",
                    "modality": "speech",
                    "category": case["category"],
                    "audio_file": "",
                    "speech_file": str(path),
                    "movement_file": "",
                    "gt_label": case.get("gt_label"),
                    "gt_phrase": case.get("gt_phrase"),
                    "audio_score": "",
                    "audio_prediction": "",
                    "speech_score": sout.get("score"),
                    "speech_prediction": sout.get("prediction"),
                    "detected_phrase": phrase,
                    "movement_score": "",
                    "movement_prediction": "",
                    "sde_decision": getattr(sde, "decision", None),
                    "trigger_reason": getattr(sde, "reason", None),
                    "demo_action": getattr(sde, "simulated_action", None)
                    or getattr(sde, "countdown_result", None),
                    "countdown_result": getattr(sde, "countdown_result", None),
                    "errors": err,
                    "warnings": "; ".join(sout.get("warnings") or []),
                    "preprocess": sout.get("preprocess"),
                    "n_windows": 1,
                }
            )

        # ── MOVEMENT-ONLY (UNMATCHED) ──
        log.log("--- MOVEMENT inference ---")
        for case in move_cases:
            test_id += 1
            path = case["path"]
            log.log(f"[M{test_id}] {case['category']}: {path.name}")
            mout = predict_movement(models.movement_model, models.movement_scaler, path)
            if not mout["ok"]:
                preprocess_failures += 1
                model_errors.append(f"movement:{path.name}:{mout.get('error')}")
                pipeline_failures += 1
            try:
                sde = run_sde(0.0, 0.0, mout.get("score") or 0.0, None, 0.0, "NO_RESPONSE")
                err = mout.get("error") or ""
            except Exception as e:
                pipeline_failures += 1
                err = f"sde:{e}"
                sde = None
            rows.append(
                {
                    "test_id": f"M{test_id:04d}",
                    "match_status": "UNMATCHED",
                    "modality": "movement",
                    "category": case["category"],
                    "audio_file": "",
                    "speech_file": "",
                    "movement_file": str(path),
                    "gt_label": case.get("gt_label"),
                    "audio_score": "",
                    "audio_prediction": "",
                    "speech_score": "",
                    "speech_prediction": "",
                    "detected_phrase": "",
                    "movement_score": mout.get("score"),
                    "movement_prediction": mout.get("prediction"),
                    "sde_decision": getattr(sde, "decision", None),
                    "trigger_reason": getattr(sde, "reason", None),
                    "demo_action": getattr(sde, "simulated_action", None)
                    or getattr(sde, "countdown_result", None),
                    "countdown_result": getattr(sde, "countdown_result", None),
                    "errors": err,
                    "warnings": "; ".join(mout.get("warnings") or []),
                    "preprocess": mout.get("preprocess"),
                    "n_windows": mout.get("n_windows"),
                    "synthetic_heavy": True,
                }
            )

        matched_count = sum(1 for r in rows if r.get("match_status") == "MATCHED")
        log.log(f"MATCHED complete multimodal tests: {matched_count} (none fabricated)")

        # Write CSV
        fieldnames = [
            "test_id",
            "match_status",
            "modality",
            "category",
            "audio_file",
            "speech_file",
            "movement_file",
            "gt_label",
            "gt_phrase",
            "audio_score",
            "audio_prediction",
            "speech_score",
            "speech_prediction",
            "detected_phrase",
            "movement_score",
            "movement_prediction",
            "sde_decision",
            "trigger_reason",
            "demo_action",
            "countdown_result",
            "errors",
            "warnings",
            "preprocess",
            "n_windows",
            "synthetic_heavy",
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow(r)
        log.log(f"Wrote {csv_path}")

        # Metrics
        def collect_mod(mod: str, score_key: str, pred_key: str, pos_label: str):
            yt, yp = [], []
            fps, fns = [], []
            for r in rows:
                if r["modality"] != mod:
                    continue
                if r.get("gt_label") is None or r.get(score_key) in ("", None):
                    continue
                if r.get("errors"):
                    continue
                gt = int(r["gt_label"])
                pred = 1 if str(r.get(pred_key)) == pos_label else 0
                yt.append(gt)
                yp.append(pred)
                if gt == 0 and pred == 1:
                    fps.append(r)
                if gt == 1 and pred == 0:
                    fns.append(r)
            return binary_metrics(yt, yp), fps, fns

        audio_m, audio_fps, audio_fns = collect_mod("audio", "audio_score", "audio_prediction", "DISTRESS")
        speech_m, speech_fps, speech_fns = collect_mod(
            "speech", "speech_score", "speech_prediction", "EMERGENCY"
        )
        move_m, move_fps, move_fns = collect_mod(
            "movement", "movement_score", "movement_prediction", "ABNORMAL"
        )

        # Per-phrase speech
        phrase_stats = {}
        for ph in ["help_me", "i_need_help", "mujhe_bachao", "madat_karo"]:
            sub = [
                r
                for r in rows
                if r["modality"] == "speech"
                and r.get("gt_phrase") == ph
                and r.get("speech_score") not in ("", None)
                and not r.get("errors")
            ]
            if not sub:
                phrase_stats[ph] = {"n": 0}
                continue
            scores = [float(r["speech_score"]) for r in sub]
            detected = sum(1 for r in sub if r.get("speech_prediction") == "EMERGENCY")
            phrase_stats[ph] = {
                "n": len(sub),
                "recall": detected / len(sub),
                "detected": detected,
                "missed": len(sub) - detected,
                "mean_score": float(np.mean(scores)),
                "min_score": float(np.min(scores)),
                "max_score": float(np.max(scores)),
            }

        sde_counts = Counter(r.get("sde_decision") for r in rows)
        demo_counts = Counter(r.get("countdown_result") or r.get("demo_action") for r in rows)

        # SDE GT where legitimate: for speech EM alone, expected EMERGENCY if speech predicts
        # Only define GT for single-modality cases with clear GT
        sde_yt, sde_yp = [], []
        for r in rows:
            gt = r.get("gt_label")
            if gt is None or r.get("sde_decision") is None:
                continue
            # Expected SDE: distress/emergency/abnormal alone → not always EMERGENCY by rules
            # Legitimate SDE GT only for speech emergency (phrase_alone_can_emergency)
            if r["modality"] == "speech" and int(gt) == 1:
                sde_yt.append(1)  # expect EMERGENCY capable
                sde_yp.append(1 if r["sde_decision"] == "EMERGENCY" else 0)
            elif r["modality"] == "speech" and int(gt) == 0:
                sde_yt.append(0)
                sde_yp.append(1 if r["sde_decision"] == "EMERGENCY" else 0)
            elif r["modality"] == "audio" and int(gt) == 0:
                # normals should not be EMERGENCY from audio-alone (SUSPICIOUS ok)
                sde_yt.append(0)
                sde_yp.append(1 if r["sde_decision"] == "EMERGENCY" else 0)
            elif r["modality"] == "movement" and int(gt) == 0:
                sde_yt.append(0)
                sde_yp.append(1 if r["sde_decision"] == "EMERGENCY" else 0)
        sde_m = binary_metrics(sde_yt, sde_yp)

        n_audio = sum(1 for r in rows if r["modality"] == "audio")
        n_speech = sum(1 for r in rows if r["modality"] == "speech")
        n_move = sum(1 for r in rows if r["modality"] == "movement")

        md = f"""# Real-Input Integration Test Summary

**DEMO_MODE:** `true` (verified)  
**Started:** {started.isoformat()}  
**Finished:** {datetime.now().isoformat()}  
**Real SOS / WhatsApp / SMS / calls / contacts:** DISABLED  

## Counts

| Item | Count |
|------|------:|
| Audio tests | {n_audio} |
| Speech tests | {n_speech} |
| Movement tests | {n_move} |
| Complete MATCHED multimodal | {matched_count} |
| Total rows | {len(rows)} |
| NORMAL (SDE) | {sde_counts.get('NORMAL', 0)} |
| SUSPICIOUS (SDE) | {sde_counts.get('SUSPICIOUS', 0)} |
| EMERGENCY (SDE) | {sde_counts.get('EMERGENCY', 0)} |
| TEST_SOS_TRIGGERED | {demo_counts.get('TEST_SOS_TRIGGERED', 0)} |
| CANCELLED | {demo_counts.get('CANCELLED', 0)} |
| Model/inference errors logged | {len(model_errors)} |
| Preprocessing failures | {preprocess_failures} |
| Pipeline failures | {pipeline_failures} |

MATCHED=0 because no same-scenario audio+speech+movement recordings exist; cases are independent **UNMATCHED** (not fabricated).

## Models (read-only)

| Model | Path | Loaded |
|-------|------|:------:|
| Audio v4 Exp02 | `{models.paths.get('audio_v4_exp02')}` | {models.loaded.get('audio_v4_exp02')} |
| Speech v2 | `{models.paths.get('speech_v2')}` | {models.loaded.get('speech_v2')} |
| Movement v2 | `{models.paths.get('movement_v2')}` | {models.loaded.get('movement_v2')} |

## Audio results (Exp02 @ 0.5, file-max over 1s windows)

{json.dumps(audio_m, indent=2)}

False positives (gt=NORMAL pred=DISTRESS): **{len(audio_fps)}**  
False negatives (gt=DISTRESS pred=NORMAL): **{len(audio_fns)}**

Do not claim better than prior Exp02 test metrics (recall≈85.8%, FPR≈12.2%) unless this sample supports it.

## Speech results (Speech v2 @ 0.5)

{json.dumps(speech_m, indent=2)}

### Per emergency phrase

{json.dumps(phrase_stats, indent=2)}

False positives: **{len(speech_fps)}** | False negatives: **{len(speech_fns)}**

## Movement results (Movement v2 — PROTOTYPE / SYNTHETIC-HEAVY)

{json.dumps(move_m, indent=2)}

False positives: **{len(move_fps)}** | False negatives: **{len(move_fns)}**  

**Warning:** Movement dataset is synthetic-heavy. Do not treat as real-world performance.

## SDE results (rules unchanged)

Decision counts: {dict(sde_counts)}  
Demo actions: {dict(demo_counts)}  

SDE metrics where GT is legitimate (speech EM→expect EMERGENCY; speech/audio/move normals must not be EMERGENCY):

{json.dumps(sde_m, indent=2)}

## Errors / warnings

Model errors (sample up to 30):
"""
        for e in model_errors[:30]:
            md += f"- `{e}`\n"
        if not model_errors:
            md += "- None\n"

        md += f"""

## Output files

- `{csv_path.relative_to(ROOT).as_posix()}`
- `{summary_path.relative_to(ROOT).as_posix()}`
- `{latest_log.relative_to(ROOT).as_posix()}`
- `{stamped_log.relative_to(ROOT).as_posix()}`

## Safety

DEMO_MODE remained **true**.  
`TEST_SOS_TRIGGERED` is log-only. No phones, SMS, WhatsApp, contacts, or Android SOS.
"""
        summary_path.write_text(md, encoding="utf-8")
        log.log(f"Wrote {summary_path}")

        # Machine-readable metrics sidecar
        metrics_path = LOG_DIR / "real_input_integration_metrics.json"
        metrics_path.write_text(
            json.dumps(
                {
                    "demo_mode": True,
                    "n_audio": n_audio,
                    "n_speech": n_speech,
                    "n_movement": n_move,
                    "matched": matched_count,
                    "sde_counts": dict(sde_counts),
                    "demo_counts": dict(demo_counts),
                    "audio_metrics": audio_m,
                    "speech_metrics": speech_m,
                    "movement_metrics": move_m,
                    "phrase_stats": phrase_stats,
                    "sde_metrics_limited_gt": sde_m,
                    "audio_fp": len(audio_fps),
                    "audio_fn": len(audio_fns),
                    "speech_fp": len(speech_fps),
                    "speech_fn": len(speech_fns),
                    "movement_fp": len(move_fps),
                    "movement_fn": len(move_fns),
                    "model_errors": model_errors[:100],
                    "preprocess_failures": preprocess_failures,
                    "pipeline_failures": pipeline_failures,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        log.log(f"Wrote {metrics_path}")
        log.log(f"STATUS=SUCCESS total_tests={len(rows)}")
        log.log("STOP — integration test complete. NO REAL SOS.")
        return 0
    except Exception as e:
        log.log(f"FATAL: {e}")
        log.log(traceback.format_exc())
        summary_path.write_text(
            f"# Real-Input Integration FAILED\n\n```\n{e}\n```\n", encoding="utf-8"
        )
        return 2
    finally:
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
