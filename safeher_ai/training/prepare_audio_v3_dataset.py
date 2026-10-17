"""
SafeHer — Audio v3 PRETRAINING dataset/pipeline corrections

Creates a NEW derived dataset under data/derived/audio_v3_prep/.
Does NOT modify raw audio, does NOT overwrite audio_v2 / models/final,
does NOT train a model, does NOT connect to SOS.

Run:
  ..\\venv311\\Scripts\\python.exe training\\prepare_audio_v3_dataset.py
"""

from __future__ import annotations

import hashlib
import json
import math
import traceback
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import librosa
import numpy as np
import pandas as pd
import soundfile as sf
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_DISTRESS = DATA / "raw" / "distress"
RAW_NORMAL = DATA / "raw" / "normal"
RAW_NOISE = DATA / "raw" / "noise"
ERROR_JSON = DATA / "training_logs" / "audio_error_analysis.json"
DERIVED = DATA / "derived" / "audio_v3_prep"
CHUNKS = DERIVED / "chunks"
SPLITS = DERIVED / "splits"
LABELS = DERIVED / "labels"
HARD_NEG = DERIVED / "hard_negatives"
AGG = DERIVED / "aggregation"
LOG_DIR = DATA / "training_logs"
CHANGE_LOG_JSON = DERIVED / "change_log.json"
REPORT_MD = LOG_DIR / "audio_v3_pretraining_changes.md"

SAMPLE_RATE = 16000
CHUNK_SECONDS = 1
CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_SECONDS
SILENCE_RMS = 0.005
NOISE_LEVELS = [0.10, 0.20, 0.35]
TRAIN_RATIO, VAL_RATIO, TEST_RATIO = 0.75, 0.15, 0.10
AUDIO_EXTS = {".wav", ".mp3", ".mpeg", ".m4a", ".flac", ".ogg"}
RANDOM_STATE = 42

# Chunk-level scream-likeness gates (from audio_v2 error analysis heuristics)
SCREAM_KEEP_MIN = 0.45          # Screaming folder: keep as DISTRESS
SCREAM_EXCLUDE_MAX = 0.30       # Screaming folder: exclude weak windows from binary train
NOTSCREAM_HARD_MIN = 0.70       # NotScreaming: tag hard-negative if score >= this


class ChangeLogger:
    def __init__(self):
        self.events = []
        self.created = []
        self.copied = []
        self.warnings = []
        self.errors = []
        self.assumptions = []
        self.label_changes = []
        self.split_notes = []
        self.preprocess_notes = []
        self.embedding_notes = []
        self.derived_datasets = []

    def log(self, kind: str, msg: str, **extra):
        rec = {"ts": datetime.now().isoformat(timespec="seconds"), "kind": kind, "msg": msg, **extra}
        self.events.append(rec)
        print(f"[{kind}] {msg}")

    def assume(self, msg: str):
        self.assumptions.append(msg)
        self.log("ASSUMPTION", msg)

    def warn(self, msg: str):
        self.warnings.append(msg)
        self.log("WARNING", msg)

    def error(self, msg: str):
        self.errors.append(msg)
        self.log("ERROR", msg)

    def created_file(self, path: Path, reason: str):
        self.created.append({"path": str(path), "reason": reason})
        self.log("CREATED", f"{path} — {reason}")


LOG = ChangeLogger()


def ensure_dirs():
    for d in [DERIVED, CHUNKS / "distress", CHUNKS / "normal", CHUNKS / "excluded",
              SPLITS, LABELS, HARD_NEG, AGG, LOG_DIR]:
        d.mkdir(parents=True, exist_ok=True)
        LOG.created_file(d, "Create derived directory")


def list_audio(root: Path):
    if not root.exists():
        return []
    return sorted([p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTS])


def folder_of(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root)
        return rel.parts[0] if len(rel.parts) > 1 else "(root)"
    except Exception:
        return "unknown"


def load_audio(path: Path) -> np.ndarray:
    y, _ = librosa.load(str(path), sr=SAMPLE_RATE, mono=True)
    return y.astype(np.float32)


def peak_normalize(audio: np.ndarray, peak_target: float = 0.9) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0:
        audio = audio / peak * peak_target
    return audio.astype(np.float32)


def split_chunks(audio: np.ndarray):
    chunks = []
    for start in range(0, len(audio), CHUNK_SAMPLES):
        chunk = audio[start : start + CHUNK_SAMPLES]
        if len(chunk) < CHUNK_SAMPLES:
            chunk = np.pad(chunk, (0, CHUNK_SAMPLES - len(chunk)))
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        if rms < SILENCE_RMS:
            continue
        chunks.append(chunk.astype(np.float32))
    return chunks


def save_wav(chunk: np.ndarray, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), chunk, SAMPLE_RATE, subtype="PCM_16")


def scream_likeness(chunk: np.ndarray, sr: int = SAMPLE_RATE) -> dict:
    """Heuristic scream-likeness in [0,1] from spectral/energy cues (no model train)."""
    rms = float(np.sqrt(np.mean(np.square(chunk.astype(np.float64)))))
    db = 20.0 * math.log10(rms + 1e-12)
    cent = float(np.mean(librosa.feature.spectral_centroid(y=chunk, sr=sr)))
    S = np.abs(librosa.stft(chunk, n_fft=512))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=512)
    total = float(np.sum(S) + 1e-12)
    high = float(np.sum(S[freqs >= 2000]) / total)
    flat = float(np.mean(librosa.feature.spectral_flatness(y=chunk)))

    def sig(x):
        return 1.0 / (1.0 + math.exp(-x))

    score = (
        0.40 * sig((high - 0.30) / 0.10)
        + 0.35 * sig((cent - 1800.0) / 400.0)
        + 0.25 * sig((db + 20.0) / 8.0)
    )
    return {
        "scream_likeness": float(score),
        "rms": rms,
        "db": db,
        "spectral_centroid_hz": cent,
        "highband_ge2khz": high,
        "spectral_flatness": flat,
    }


def synthetic_noise(n: int) -> np.ndarray:
    # Pink-ish via brownian-ish filter on white noise (derived only; no raw writes)
    white = np.random.randn(n).astype(np.float32)
    # simple leaking integrator
    pink = np.cumsum(white)
    pink = pink / (np.max(np.abs(pink)) + 1e-8)
    return pink.astype(np.float32)


def load_ambient_noise_bank() -> list[np.ndarray]:
    bank = []
    if RAW_NOISE.exists():
        for p in list(RAW_NOISE.glob("*.wav"))[:50]:
            try:
                bank.append(peak_normalize(load_audio(p)[: CHUNK_SAMPLES * 5]))
            except Exception:
                pass
    # Fallback: sample a few ambient normals (read-only) for mix backgrounds
    for sub in ["Traffic", "airplane", "cars", "Truck"]:
        d = RAW_NORMAL / sub
        if not d.exists():
            continue
        for p in list_audio(d)[:8]:
            try:
                bank.append(peak_normalize(load_audio(p)[: CHUNK_SAMPLES * 5]))
            except Exception:
                pass
    if not bank:
        LOG.warn("No ambient noise bank available; using synthetic noise only for augmentation.")
        bank = [synthetic_noise(CHUNK_SAMPLES * 5)]
    else:
        LOG.assume(
            "raw/noise missing or empty — augmentation mixes synthetic noise and "
            "read-only ambient snippets from Traffic/airplane/cars/Truck (not copied as new raw)."
        )
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
    """8 versions: original + 3 noise + 2 pitch + 2 speed (matches 01_prepare_dataset)."""
    versions = [chunk.copy()]
    for level in NOISE_LEVELS:
        noise = noise_chunk(bank)
        mixed = peak_normalize((1 - level) * chunk + level * noise)
        versions.append(mixed)
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


def load_fp_hard_neg_sources() -> dict:
    """From audio_v2 error analysis: NotScreaming/ESC-50 FP sources."""
    out = {"notscreaming": {}, "esc50": {}, "all_sources": set()}
    if not ERROR_JSON.exists():
        LOG.warn(f"Missing {ERROR_JSON}; hard-neg audit will rely on scream_likeness only.")
        return out
    data = json.loads(ERROR_JSON.read_text(encoding="utf-8"))
    for src, cnt in data.get("fp", {}).get("top_error_sources", []):
        out["all_sources"].add(src)
        # classify later by folder when we see the file
        out["notscreaming"][src] = {"fp_chunks_in_audio_v2_test": cnt}
    # also scan examples for folder tags
    for ex in data.get("fp", {}).get("examples", []):
        src = ex.get("source")
        folder = ex.get("folder", "")
        if not src:
            continue
        out["all_sources"].add(src)
        bucket = out["esc50"] if "ESC-50" in folder else out["notscreaming"]
        bucket.setdefault(src, {})["fp_chunks_in_audio_v2_test"] = bucket.get(src, {}).get(
            "fp_chunks_in_audio_v2_test", 0
        )
    LOG.log("AUDIT", f"Loaded {len(out['all_sources'])} unique FP sources from audio_v2 error analysis")
    return out


def decide_chunk_label(kind: str, folder: str, source_name: str, feats: dict, fp_sources: set):
    """
    Returns dict with binary_label (0/1/None), bucket, decision, notes.
    None binary_label => excluded from binary train/val/test.
    """
    score = feats["scream_likeness"]

    if kind == "distress":
        if folder == "Screaming":
            if score >= SCREAM_KEEP_MIN:
                return {
                    "binary_label": 1,
                    "bucket": "scream_distress_keep",
                    "decision": "keep_distress",
                    "label_rule": f"Screaming & likeness>={SCREAM_KEEP_MIN}",
                }
            if score <= SCREAM_EXCLUDE_MAX:
                return {
                    "binary_label": None,
                    "bucket": "scream_ambiguous_exclude",
                    "decision": "exclude_weak_scream_window",
                    "label_rule": f"Screaming & likeness<={SCREAM_EXCLUDE_MAX}",
                }
            return {
                "binary_label": None,
                "bucket": "scream_borderline_exclude",
                "decision": "exclude_borderline_scream_window",
                "label_rule": f"Screaming & {SCREAM_EXCLUDE_MAX}<likeness<{SCREAM_KEEP_MIN}",
            }
        # phrase / other distress folders: keep file-level DISTRESS
        return {
            "binary_label": 1,
            "bucket": "phrase_or_other_distress",
            "decision": "keep_file_level_distress",
            "label_rule": "non-Screaming distress folder → DISTRESS",
        }

    # normal
    if folder == "NotScreaming":
        hard = source_name in fp_sources or score >= NOTSCREAM_HARD_MIN
        if hard:
            reason = []
            if source_name in fp_sources:
                reason.append("audio_v2_FP_source")
            if score >= NOTSCREAM_HARD_MIN:
                reason.append(f"likeness>={NOTSCREAM_HARD_MIN}")
            return {
                "binary_label": 0,
                "bucket": "hard_negative_scream_like",
                "decision": "keep_normal_tagged_hard_neg",
                "label_rule": "+".join(reason),
            }
        return {
            "binary_label": 0,
            "bucket": "easy_normal_notscreaming",
            "decision": "keep_normal",
            "label_rule": "NotScreaming easy",
        }

    if folder == "ESC-50-master" and source_name in fp_sources:
        return {
            "binary_label": 0,
            "bucket": "hard_negative_esc50_fp",
            "decision": "keep_normal_tagged_hard_neg",
            "label_rule": "ESC-50 source appeared as audio_v2 FP",
        }

    return {
        "binary_label": 0,
        "bucket": "ambient_normal",
        "decision": "keep_normal",
        "label_rule": f"normal/{folder}",
    }


def process_all_sources(fp_audit: dict, noise_bank: list[np.ndarray]):
    records = []
    excluded = []
    label_change_counter = Counter()
    fp_sources = set(fp_audit["all_sources"])

    jobs = []
    for p in list_audio(RAW_DISTRESS):
        jobs.append(("distress", RAW_DISTRESS, p))
    for p in list_audio(RAW_NORMAL):
        jobs.append(("normal", RAW_NORMAL, p))

    LOG.log("PREPROCESS", f"Scanning {len(jobs)} raw source files (read-only)")
    LOG.preprocess_notes.append(
        f"16 kHz mono resample, peak-normalize to 0.9, 1s chunks, drop RMS<{SILENCE_RMS}"
    )
    LOG.preprocess_notes.append(
        "Chunk-level scream_likeness gates applied only to Screaming/NotScreaming; "
        "phrase distress keeps file-level DISTRESS; other normals keep NORMAL."
    )

    for kind, root, path in jobs:
        folder = folder_of(path, root)
        stratum = f"{kind}/{folder}"
        try:
            audio = peak_normalize(load_audio(path))
            chunks = split_chunks(audio)
        except Exception as e:
            LOG.error(f"Failed to load {path}: {e}")
            continue

        for c_idx, chunk in enumerate(chunks):
            feats = scream_likeness(chunk)
            decision = decide_chunk_label(kind, folder, path.name, feats, fp_sources)
            label_change_counter[f"{folder}:{decision['decision']}"] += 1

            stem = path.stem
            if decision["binary_label"] is None:
                out_name = f"excluded_{stem}_c{c_idx:03d}_a0.wav"
                out_path = CHUNKS / "excluded" / out_name
                save_wav(chunk, out_path)
                excluded.append(
                    {
                        "filepath": str(out_path.relative_to(ROOT)),
                        "source": path.name,
                        "original_path": str(path),
                        "folder": folder,
                        "stratum": stratum,
                        "chunk_idx": c_idx,
                        "aug_idx": 0,
                        "binary_label": -1,
                        "bucket": decision["bucket"],
                        "decision": decision["decision"],
                        "label_rule": decision["label_rule"],
                        **feats,
                    }
                )
                continue

            lab_name = "distress" if decision["binary_label"] == 1 else "normal"
            out_name = f"{lab_name}_{stem}_c{c_idx:03d}_a0.wav"
            out_path = CHUNKS / lab_name / out_name
            save_wav(chunk, out_path)

            records.append(
                {
                    "filepath": str(out_path.relative_to(ROOT)),
                    "label": int(decision["binary_label"]),
                    "source": path.name,
                    "original_path": str(path),
                    "folder": folder,
                    "stratum": stratum,
                    "kind": kind,
                    "speaker": "spk000",  # true speaker IDs unavailable
                    "chunk_idx": c_idx,
                    "aug_idx": 0,
                    "bucket": decision["bucket"],
                    "decision": decision["decision"],
                    "label_rule": decision["label_rule"],
                    "use_in_binary_train": True,
                    **feats,
                }
            )

    LOG.log("LABELS", f"Kept binary windows: {len(records)}; excluded weak scream windows: {len(excluded)}")
    for k, v in label_change_counter.most_common():
        LOG.label_changes.append({"rule": k, "count": int(v)})
    return records, excluded


def youtube_key(name: str) -> str:
    import re
    stem = Path(name).stem
    return re.sub(r"_out$", "", stem)


def make_source_key(row) -> str:
    """Pair Screaming/NotScreaming by YouTube id; otherwise use original_path."""
    if row["folder"] in {"Screaming", "NotScreaming"}:
        return f"yt::{youtube_key(row['source'])}"
    return f"path::{row['original_path']}"


def stratified_source_split(df: pd.DataFrame):
    """
    Split by source_key within split_stratum:
    - paired Screaming/NotScreaming YouTube IDs stay in the same split
    - no key leakage across train/val/test
    - phrase categories appear in eval when enough keys exist
    """
    df = df.copy()
    df["source_key"] = df.apply(make_source_key, axis=1)

    key_strata = {}
    for key, g in df.groupby("source_key"):
        folders = set(g["folder"].unique())
        if "Screaming" in folders and "NotScreaming" in folders:
            key_strata[key] = "paired_scream_notscream"
        else:
            key_strata[key] = g["stratum"].value_counts().idxmax()
    df["split_stratum"] = df["source_key"].map(key_strata)

    train_keys, val_keys, test_keys = set(), set(), set()
    notes = []

    for stratum, g in df.groupby("split_stratum"):
        keys = sorted(g["source_key"].unique())
        n = len(keys)
        if n == 1:
            train_keys.add(keys[0])
            notes.append(f"{stratum}: only 1 key → train only")
            continue
        if n == 2:
            train_keys.add(keys[0])
            test_keys.add(keys[1])
            notes.append(f"{stratum}: 2 keys → train+test (no val)")
            continue
        if n < 10:
            test_keys.add(keys[0])
            val_keys.add(keys[1])
            train_keys.update(keys[2:])
            notes.append(f"{stratum}: n={n} → 1 test, 1 val, rest train")
            continue
        try:
            src_tr, src_vt = train_test_split(
                keys, test_size=(VAL_RATIO + TEST_RATIO), random_state=RANDOM_STATE
            )
            src_va, src_te = train_test_split(
                src_vt,
                test_size=TEST_RATIO / (VAL_RATIO + TEST_RATIO),
                random_state=RANDOM_STATE,
            )
        except ValueError as e:
            LOG.warn(f"Split fallback for {stratum}: {e}")
            src_tr, src_vt = keys[: int(0.75 * n)], keys[int(0.75 * n) :]
            mid = max(1, len(src_vt) // 2)
            src_va, src_te = src_vt[:mid], src_vt[mid:]
        train_keys.update(src_tr)
        val_keys.update(src_va)
        test_keys.update(src_te)
        notes.append(f"{stratum}: n={n} → train={len(src_tr)} val={len(src_va)} test={len(src_te)}")

    assert not (train_keys & val_keys | train_keys & test_keys | val_keys & test_keys)

    def subset(split_name, key_set):
        out = df[df["source_key"].isin(key_set)].copy()
        out["split"] = split_name
        return out.reset_index(drop=True)

    train_df = subset("train", train_keys)
    val_df = subset("validation", val_keys)
    test_df = subset("test", test_keys)

    assert len(set(train_df.source_key) & set(test_df.source_key)) == 0
    assert len(set(train_df.source_key) & set(val_df.source_key)) == 0
    assert len(set(val_df.source_key) & set(test_df.source_key)) == 0

    for n in notes:
        LOG.split_notes.append(n)
        LOG.log("SPLIT", n)

    return train_df, val_df, test_df


def apply_train_distress_augmentation(train_df: pd.DataFrame, noise_bank: list[np.ndarray]):
    """Create aug_idx 1..7 for train DISTRESS a0 rows only. Writes new WAVs under derived/."""
    base = train_df[(train_df["label"] == 1) & (train_df["aug_idx"] == 0)].copy()
    LOG.log("AUGMENT", f"Augmenting {len(base)} train distress base chunks → up to 8 versions each")
    LOG.preprocess_notes.append(
        "Distress augmentation restored for TRAIN only: a0=original, a1-a3=noise mix, "
        "a4-a5=pitch ±2, a6-a7=speed 1.1/0.9 (aug_idx recorded)."
    )
    new_rows = []
    np.random.seed(RANDOM_STATE)
    for _, row in base.iterrows():
        src_path = ROOT / row["filepath"]
        try:
            chunk, _ = sf.read(str(src_path), always_2d=False)
            if getattr(chunk, "ndim", 1) > 1:
                chunk = np.mean(chunk, axis=1)
            chunk = chunk.astype(np.float32)
        except Exception as e:
            LOG.error(f"Augment skip load {src_path}: {e}")
            continue
        versions = augment_chunk(chunk, noise_bank)
        # versions[0] is original already present as a0
        for a_idx, version in enumerate(versions):
            if a_idx == 0:
                continue
            out_name = Path(row["filepath"]).name.replace("_a0.wav", f"_a{a_idx}.wav")
            out_path = CHUNKS / "distress" / out_name
            save_wav(version, out_path)
            r = row.to_dict()
            r["filepath"] = str(out_path.relative_to(ROOT))
            r["aug_idx"] = int(a_idx)
            new_rows.append(r)
    LOG.log("AUGMENT", f"Created {len(new_rows)} augmented distress train windows")
    if new_rows:
        train_df = pd.concat([train_df, pd.DataFrame(new_rows)], ignore_index=True)
    return train_df


def write_hard_negative_audit(df: pd.DataFrame, fp_audit: dict):
    hard = df[df["bucket"].isin(["hard_negative_scream_like", "hard_negative_esc50_fp"])].copy()
    # source-level summary
    rows = []
    for src, g in hard.groupby("source"):
        rows.append(
            {
                "source": src,
                "folder": g["folder"].iloc[0],
                "bucket": g["bucket"].iloc[0],
                "n_chunks": int(len(g)),
                "mean_scream_likeness": float(g["scream_likeness"].mean()),
                "max_scream_likeness": float(g["scream_likeness"].max()),
                "in_audio_v2_fp_list": bool(src in fp_audit["all_sources"]),
                "audio_v2_fp_chunks": int(
                    fp_audit["notscreaming"].get(src, {}).get("fp_chunks_in_audio_v2_test")
                    or fp_audit["esc50"].get(src, {}).get("fp_chunks_in_audio_v2_test")
                    or 0
                ),
                "classification": "HARD_NEGATIVE_SCREAM_LIKE_PRESERVED",
                "action": "KEEP as NORMAL label=0; do NOT delete; oversample carefully in future training",
            }
        )
    hard_src = pd.DataFrame(rows).sort_values(["in_audio_v2_fp_list", "mean_scream_likeness"], ascending=False)
    path_csv = HARD_NEG / "hard_negative_sources.csv"
    path_chunks = HARD_NEG / "hard_negative_chunks.csv"
    path_md = HARD_NEG / "HARD_NEGATIVES.md"
    hard_src.to_csv(path_csv, index=False)
    hard.to_csv(path_chunks, index=False)
    LOG.created_file(path_csv, "Hard-negative source audit")
    LOG.created_file(path_chunks, "Hard-negative chunk audit")

    md = [
        "# Hard-negative audit (NotScreaming / ESC-50 scream-like)",
        "",
        "Original raw files were **not** deleted or modified.",
        "These recordings stay labeled **NORMAL (0)** but tagged as hard negatives for future training.",
        "",
        f"- Hard-negative sources: **{len(hard_src)}**",
        f"- Hard-negative chunks: **{len(hard)}**",
        f"- Overlap with audio_v2 FP sources: **{int(hard_src['in_audio_v2_fp_list'].sum()) if len(hard_src) else 0}**",
        "",
        "## Classification",
        "- `HARD_NEGATIVE_SCREAM_LIKE_PRESERVED`",
        "- Binary label remains NORMAL",
        "- Bucket: `hard_negative_scream_like` or `hard_negative_esc50_fp`",
        "",
        "## Top sources",
        "",
    ]
    if len(hard_src):
        md.append("| source | folder | n_chunks | mean_likeness | in_audio_v2_fp | classification |")
        md.append("|---|---|---:|---:|---|---|")
        for _, r in hard_src.head(40).iterrows():
            md.append(
                f"| {r['source']} | {r['folder']} | {r['n_chunks']} | "
                f"{r['mean_scream_likeness']:.3f} | {r['in_audio_v2_fp_list']} | {r['classification']} |"
            )
    path_md.write_text("\n".join(md), encoding="utf-8")
    LOG.created_file(path_md, "Hard-negative human-readable audit")
    return hard_src


def write_aggregation_support():
    cfg = {
        "version": "audio_v3_prep",
        "window_seconds": 1,
        "default_threshold": 0.5,
        "modes": {
            "file_max": {
                "description": "File distress if max window probability >= threshold",
                "aggregate": "max",
            },
            "k_of_n": {
                "description": "File distress if any consecutive N-window block has >= K positives",
                "K": 3,
                "N": 5,
                "aggregate": "k_of_n_consecutive",
            },
            "mean_then_threshold": {
                "description": "Mean probability across windows then threshold",
                "aggregate": "mean",
            },
        },
        "recommended_eval_mode": "k_of_n",
        "note": "Window-level metrics alone over-penalize mixed Screaming files; use file-level aggregation for SafeHer-relevant eval.",
    }
    path = AGG / "aggregation_config.json"
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    LOG.created_file(path, "K-of-N / file-level aggregation config")

    helper = AGG / "aggregate_scores.py"
    helper.write_text(
        '''"""File-level / K-of-N aggregation helpers for audio_v3 eval (no training)."""
from __future__ import annotations
import numpy as np

def file_max(probs, threshold=0.5):
    probs = np.asarray(probs, dtype=float)
    m = float(np.max(probs)) if len(probs) else 0.0
    return {"file_prob": m, "file_pred": int(m >= threshold), "mode": "file_max"}

def k_of_n(probs, threshold=0.5, K=3, N=5):
    probs = np.asarray(probs, dtype=float)
    hits = (probs >= threshold).astype(int)
    if len(hits) == 0:
        return {"file_prob": 0.0, "file_pred": 0, "mode": "k_of_n", "best_block_positives": 0}
    if len(hits) < N:
        best = int(hits.sum())
        pred = int(best >= K)
        return {"file_prob": float(np.max(probs)), "file_pred": pred, "mode": "k_of_n", "best_block_positives": best}
    best = 0
    for i in range(0, len(hits) - N + 1):
        best = max(best, int(hits[i:i+N].sum()))
    return {"file_prob": float(np.max(probs)), "file_pred": int(best >= K), "mode": "k_of_n", "best_block_positives": best}

def mean_then_threshold(probs, threshold=0.5):
    probs = np.asarray(probs, dtype=float)
    m = float(np.mean(probs)) if len(probs) else 0.0
    return {"file_prob": m, "file_pred": int(m >= threshold), "mode": "mean_then_threshold"}
''',
        encoding="utf-8",
    )
    LOG.created_file(helper, "Aggregation helper module")


def write_report(summary: dict):
    md = []
    md.append("# Audio v3 Pretraining Changes (dataset/pipeline only)")
    md.append("")
    md.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    md.append("")
    md.append("**No model training. No SOS connection. Raw audio untouched. audio_v2 / models/final untouched.**")
    md.append("")
    md.append("## Derived dataset root")
    md.append(f"`{DERIVED}`")
    md.append("")
    md.append("## Summary counts")
    md.append("```json")
    md.append(json.dumps(summary, indent=2))
    md.append("```")
    md.append("")
    md.append("## Assumptions")
    for a in LOG.assumptions:
        md.append(f"- {a}")
    md.append("")
    md.append("## Preprocessing changes")
    for p in LOG.preprocess_notes:
        md.append(f"- {p}")
    md.append("")
    md.append("## Label changes (chunk-level)")
    md.append("```json")
    md.append(json.dumps(LOG.label_changes[:80], indent=2))
    md.append("```")
    md.append("")
    md.append("## Split changes")
    for s in LOG.split_notes:
        md.append(f"- {s}")
    md.append("")
    md.append("## Embedding changes")
    for e in LOG.embedding_notes:
        md.append(f"- {e}")
    if not LOG.embedding_notes:
        md.append("- Embeddings generated by `training/embed_audio_v3.py` into `derived/audio_v3_prep/embeddings/` (separate step).")
    md.append("")
    md.append("## Hard negatives")
    md.append("- Documented under `derived/audio_v3_prep/hard_negatives/`")
    md.append("- Classification: `HARD_NEGATIVE_SCREAM_LIKE_PRESERVED` (label remains NORMAL)")
    md.append("- Original files NOT deleted")
    md.append("")
    md.append("## Aggregation support")
    md.append("- `derived/audio_v3_prep/aggregation/aggregation_config.json`")
    md.append("- Modes: file_max, k_of_n (K=3,N=5), mean_then_threshold")
    md.append("")
    md.append("## Files created (sample; full list in change_log.json)")
    md.append(f"- Total created path records: {len(LOG.created)}")
    for c in LOG.created[:40]:
        md.append(f"- {c['path']} — {c['reason']}")
    if len(LOG.created) > 40:
        md.append(f"- ... and {len(LOG.created) - 40} more directory/metadata entries (chunk WAVs counted in summary)")
    md.append("")
    md.append("## Files copied")
    if LOG.copied:
        for c in LOG.copied:
            md.append(f"- {c}")
    else:
        md.append("- None. Raw files were read in place; derived WAVs are new writes (not copies of originals).")
    md.append("")
    md.append("## Warnings")
    for w in LOG.warnings:
        md.append(f"- {w}")
    if not LOG.warnings:
        md.append("- None")
    md.append("")
    md.append("## Errors")
    for e in LOG.errors:
        md.append(f"- {e}")
    if not LOG.errors:
        md.append("- None")
    md.append("")
    md.append("## Ready for Audio v3 training?")
    md.append(summary.get("ready_status", "UNKNOWN"))
    md.append("")
    md.append("## Explicit non-changes")
    md.append("- Did not delete/modify `data/raw/**`")
    md.append("- Did not overwrite `data/models/audio_v2/**`")
    md.append("- Did not overwrite `models/final/**`")
    md.append("- Did not overwrite legacy `data/splits/**` or `data/embeddings/**`")
    md.append("- Did not train audio_v3")
    md.append("- Did not connect SOS")

    REPORT_MD.write_text("\n".join(md), encoding="utf-8")
    LOG.created_file(REPORT_MD, "Pretraining changes report")
    CHANGE_LOG_JSON.write_text(
        json.dumps(
            {
                "events": LOG.events,
                "created": LOG.created,
                "copied": LOG.copied,
                "warnings": LOG.warnings,
                "errors": LOG.errors,
                "assumptions": LOG.assumptions,
                "label_changes": LOG.label_changes,
                "split_notes": LOG.split_notes,
                "preprocess_notes": LOG.preprocess_notes,
                "embedding_notes": LOG.embedding_notes,
                "summary": summary,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    LOG.created_file(CHANGE_LOG_JSON, "Machine-readable change log")


def main():
    np.random.seed(RANDOM_STATE)
    ensure_dirs()
    LOG.derived_datasets.append(str(DERIVED))
    LOG.assume("True speaker IDs unavailable (spk000 placeholder); leakage prevention is by source filename.")
    LOG.assume("Scream-likeness gates are heuristic (centroid/highband/RMS), not a new trained model.")
    LOG.assume("Excluded weak Screaming windows are preserved under chunks/excluded/ for audit, not used in binary CSVs.")

    fp_audit = load_fp_hard_neg_sources()
    noise_bank = load_ambient_noise_bank()

    records, excluded = process_all_sources(fp_audit, noise_bank)
    if not records:
        LOG.error("No binary records produced; aborting.")
        write_report({"ready_status": "FAILED — no records"})
        return

    df = pd.DataFrame(records)
    excl_df = pd.DataFrame(excluded)
    manifest_path = LABELS / "chunk_labels_all.csv"
    excl_path = LABELS / "excluded_scream_windows.csv"
    df.to_csv(manifest_path, index=False)
    excl_df.to_csv(excl_path, index=False)
    LOG.created_file(manifest_path, "Full chunk label manifest (a0)")
    LOG.created_file(excl_path, "Excluded weak Screaming windows")

    hard_src = write_hard_negative_audit(df, fp_audit)
    write_aggregation_support()

    train_df, val_df, test_df = stratified_source_split(df)
    train_df = apply_train_distress_augmentation(train_df, noise_bank)

    train_path, val_path, test_path = SPLITS / "train.csv", SPLITS / "val.csv", SPLITS / "test.csv"
    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    test_df.to_csv(test_path, index=False)
    LOG.created_file(train_path, "New train split (source-safe, stratified)")
    LOG.created_file(val_path, "New validation split")
    LOG.created_file(test_path, "New test split")

    # Coverage tables
    def coverage(split_df):
        return {
            "rows": int(len(split_df)),
            "sources": int(split_df["source"].nunique()),
            "labels": {str(k): int(v) for k, v in Counter(split_df["label"]).items()},
            "aug_idx": {str(k): int(v) for k, v in Counter(split_df["aug_idx"]).items()},
            "strata": {str(k): int(v) for k, v in Counter(split_df["stratum"]).items()},
            "buckets": {str(k): int(v) for k, v in Counter(split_df["bucket"]).items()},
        }

    summary = {
        "derived_root": str(DERIVED),
        "raw_untouched": True,
        "audio_v2_untouched": True,
        "models_final_untouched": True,
        "binary_a0_windows": int(len(df)),
        "excluded_scream_windows": int(len(excl_df)),
        "hard_negative_sources": int(len(hard_src)),
        "hard_negative_chunks": int((df["bucket"].str.startswith("hard_negative")).sum()),
        "train": coverage(train_df),
        "validation": coverage(val_df),
        "test": coverage(test_df),
        "source_overlap_train_test": int(len(set(train_df.source) & set(test_df.source))),
        "test_distress_strata": sorted(
            [s for s in test_df.loc[test_df.label == 1, "stratum"].unique()]
        ),
        "aug_idx_nonzero_train": int((train_df.aug_idx > 0).sum()),
        "ready_status": "DATASET/SPLITS READY — run embed_audio_v3.py next for embedding cache",
    }
    summary_path = DERIVED / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    LOG.created_file(summary_path, "Derived dataset summary")

    # README
    readme = DERIVED / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# audio_v3_prep (derived)",
                "",
                "Corrected labels/splits/chunks for future Audio v3 training.",
                "Does not replace `data/splits` or `data/embeddings` used by audio_v2.",
                "",
                "Next: `python training/embed_audio_v3.py`",
                "Then (later): train audio_v3 (not done in this step).",
            ]
        ),
        encoding="utf-8",
    )
    LOG.created_file(readme, "Derived dataset README")

    write_report(summary)
    LOG.log("STATUS", summary["ready_status"])
    print(json.dumps({k: summary[k] for k in summary if k in (
        "binary_a0_windows", "excluded_scream_windows", "hard_negative_sources",
        "source_overlap_train_test", "test_distress_strata", "aug_idx_nonzero_train", "ready_status"
    )}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        LOG.error(traceback.format_exc())
        write_report({"ready_status": "FAILED", "traceback": traceback.format_exc()})
        raise
