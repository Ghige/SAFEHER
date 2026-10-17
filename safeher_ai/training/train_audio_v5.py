"""
SafeHer Audio v5 — train on existing SafeHer distress + new commercial-safe candidates.

Does NOT modify:
  - audio_v2 / audio_v3 / audio_v4 / audio_v4_exp*
  - raw audio, SOS, Speech, Movement, Android, backend

Does NOT connect Audio v5 to SOS.

Data policy for this run (documented in the training log):
  - Existing SafeHer distress + approved hard-negatives: kept from audio_v3_prep
    (frozen val/test source keys so comparison vs Audio v4 Exp02 is fair).
  - NEW distress positives: FSD50K LIKELY_DISTRESS only (audit-promoted;
    manual review currently has 0 DISTRESS verdicts).
  - NEW hard-negatives: FSD50K NON_DISTRESS_SCREAM / MOVIE_OR_MEDIA / MUSIC_RELATED,
    AudioSet Screaming (all), BERSt manual HARD_NEGATIVE verdicts, and a capped
    sample of BERSt preliminary HARD_NEGATIVE (speaker-split).
  - BERSt LIKELY_DISTRESS is NOT used as DISTRESS — the two listened examples
    already contradicted that heuristic.

Pipeline:
  1) Split NEW sources by source/speaker BEFORE augmentation.
  2) Augment TRAIN distress only (same 8x recipe as audio_v3_prep).
  3) Embed new windows with YAMNet; reuse cached embeddings for v3_prep rows.
  4) Train Dense classifier (same arch as v4); sample weights like Exp02.
  5) Evaluate + compare vs audio_v4_exp02 on the frozen v3 test set.

Run:
  ..\\venv311\\Scripts\\python.exe training\\train_audio_v5.py
"""

from __future__ import annotations

import csv
import json
import platform
import re
import shutil
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

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
V3 = DATA / "derived" / "audio_v3_prep"
V3_SPLITS = V3 / "splits"
V3_EMB = V3 / "embeddings"
V3_AGG = V3 / "aggregation"

DERIVED = DATA / "derived" / "audio_v5_prep"
CHUNKS = DERIVED / "chunks"
SPLITS = DERIVED / "splits"
EMB_DIR = DERIVED / "embeddings"
META = DERIVED / "metadata"
LOGS_DER = DERIVED / "logs"

MODEL_DIR = DATA / "models" / "audio_v5"
EXP02_DIR = DATA / "models" / "audio_v4_exp02"
LOG_DIR = DATA / "training_logs"

FSD_AUDIT = DATA / "derived" / "fsd50k_distress" / "metadata" / "quality_audit.csv"
FSD_AUDIO = DATA / "derived" / "fsd50k_distress" / "audio"
AS_META = DATA / "derived" / "audioset_screaming" / "metadata" / "screaming_metadata.csv"
AS_ROOT = DATA / "derived" / "audioset_screaming"
BERST_META = DATA / "derived" / "distress_collection_v2" / "metadata" / "collection_metadata.csv"
BERST_VERDICTS = DATA / "derived" / "distress_collection_v2" / "metadata" / "manual_review_verdicts.csv"
FSD_VERDICTS = DATA / "derived" / "fsd50k_distress" / "metadata" / "manual_review_verdicts.csv"

SAMPLE_RATE = 16000
CHUNK_SAMPLES = SAMPLE_RATE
NOISE_LEVELS = [0.10, 0.20, 0.35]
RANDOM_STATE = 42
SILENCE_RMS = 0.005
YAMNET_URL = "https://tfhub.dev/google/yamnet/1"
EMBED_DIM = 1024

# Cap BERSt preliminary HN files so they do not drown SafeHer data.
BERST_HN_FILE_CAP = 800

# Exp02 operating point
DISTRESS_W = 1.5
HARD_NEG_W = 1.0
THRESHOLDS = [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
K_VALUES = [1, 2, 3, 4, 5]

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

sys.path.insert(0, str(V3_AGG))
from aggregate_scores import k_of_n  # noqa: E402


class Logger:
    def __init__(self, path: Path, also: Path | None = None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(path, "w", encoding="utf-8")
        self.also = open(also, "w", encoding="utf-8") if also else None

    def log(self, msg: str = ""):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        try:
            print(line, flush=True)
        except UnicodeEncodeError:
            print(line.encode("ascii", "replace").decode("ascii"), flush=True)
        self.fh.write(line + "\n")
        self.fh.flush()
        if self.also:
            self.also.write(line + "\n")
            self.also.flush()

    def close(self):
        self.fh.close()
        if self.also:
            self.also.close()


def peak_normalize(x: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak < 1e-8:
        return x.astype(np.float32)
    return (x / peak).astype(np.float32)


def load_audio(path: Path) -> np.ndarray:
    y, _ = librosa.load(str(path), sr=SAMPLE_RATE, mono=True)
    return y.astype(np.float32)


def save_wav(y: np.ndarray, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), peak_normalize(y), SAMPLE_RATE, subtype="PCM_16")


def list_audio(root: Path):
    if not root.exists():
        return []
    exts = {".wav", ".mp3", ".mpeg", ".m4a", ".flac", ".ogg"}
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in exts)


def build_noise_bank(log: Logger) -> list[np.ndarray]:
    bank: list[np.ndarray] = []
    noise_dir = DATA / "raw" / "noise"
    if noise_dir.exists():
        for p in list_audio(noise_dir)[:20]:
            try:
                bank.append(peak_normalize(load_audio(p)[: CHUNK_SAMPLES * 5]))
            except Exception:
                pass
    for rel in ["Traffic", "airplane", "cars", "Truck"]:
        d = DATA / "raw" / "normal" / rel
        if not d.exists():
            continue
        for p in list_audio(d)[:6]:
            try:
                bank.append(peak_normalize(load_audio(p)[: CHUNK_SAMPLES * 5]))
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
    """Same 8x recipe as prepare_audio_v3_dataset / 01_prepare_dataset."""
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


def youtube_key(name: str) -> str:
    stem = Path(name).stem
    return re.sub(r"_out$", "", stem)


def make_source_key_row(row) -> str:
    folder = str(row.get("folder", ""))
    if folder in {"Screaming", "NotScreaming"}:
        return f"yt::{youtube_key(str(row['source']))}"
    if str(row.get("source_dataset", "")).startswith("BERSt"):
        return f"berst_spk::{row.get('speaker', row.get('speaker_id', 'unk'))}"
    if str(row.get("source_dataset", "")).startswith("FSD50K"):
        return f"fsd::{row.get('source', '')}"
    if str(row.get("source_dataset", "")).startswith("AudioSet"):
        return f"as::{row.get('source', '')}"
    return f"path::{row.get('original_path', row.get('source', ''))}"


def chunk_file(path: Path) -> list[np.ndarray]:
    y = load_audio(path)
    if len(y) < int(0.25 * SAMPLE_RATE):
        return []
    chunks = []
    if len(y) <= CHUNK_SAMPLES:
        pad = np.pad(y, (0, CHUNK_SAMPLES - len(y)))
        if float(np.sqrt(np.mean(pad ** 2))) >= SILENCE_RMS:
            chunks.append(pad.astype(np.float32))
        return chunks
    n = len(y) // CHUNK_SAMPLES
    for i in range(n):
        c = y[i * CHUNK_SAMPLES:(i + 1) * CHUNK_SAMPLES]
        if float(np.sqrt(np.mean(c ** 2))) >= SILENCE_RMS:
            chunks.append(c.astype(np.float32))
    rem = len(y) - n * CHUNK_SAMPLES
    if rem >= int(0.5 * SAMPLE_RATE):
        c = np.pad(y[-CHUNK_SAMPLES:], (0, 0)) if len(y) >= CHUNK_SAMPLES else np.pad(y, (0, CHUNK_SAMPLES - len(y)))
        # last full-ish window ending at EOF
        c = y[-CHUNK_SAMPLES:] if len(y) >= CHUNK_SAMPLES else np.pad(y, (0, CHUNK_SAMPLES - len(y)))
        if float(np.sqrt(np.mean(c ** 2))) >= SILENCE_RMS:
            chunks.append(c.astype(np.float32))
    return chunks


def write_chunks_for_file(
    path: Path,
    *,
    label: int,
    source: str,
    folder: str,
    stratum: str,
    bucket: str,
    source_dataset: str,
    speaker: str,
    source_label: str,
    license_name: str,
    out_rows: list[dict],
):
    chunks = chunk_file(path)
    lab_name = "distress" if label == 1 else "normal"
    for c_idx, chunk in enumerate(chunks):
        out_name = f"v5_{source_dataset}_{Path(source).stem}_c{c_idx:03d}_a0.wav"
        out_name = re.sub(r"[^A-Za-z0-9._-]+", "_", out_name)
        out_path = CHUNKS / lab_name / out_name
        save_wav(chunk, out_path)
        out_rows.append({
            "filepath": str(out_path.relative_to(ROOT)).replace("\\", "/"),
            "label": int(label),
            "source": source,
            "original_path": str(path),
            "folder": folder,
            "stratum": stratum,
            "kind": "distress" if label == 1 else "normal",
            "speaker": speaker or "spk000",
            "chunk_idx": c_idx,
            "aug_idx": 0,
            "bucket": bucket,
            "decision": "v5_added",
            "label_rule": f"{source_dataset}:{source_label}",
            "use_in_binary_train": True,
            "source_dataset": source_dataset,
            "source_label": source_label,
            "license": license_name,
            "scream_likeness": None,
            "is_new": True,
        })


def load_verdicts(path: Path, id_col: str) -> dict[str, str]:
    if not path.exists():
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = r.get(id_col) or r.get("clip_id") or r.get("freesound_id")
            if key and r.get("verdict"):
                out[str(key)] = r["verdict"]
    return out


def collect_new_sources(log: Logger, forbidden_keys: set[str]) -> pd.DataFrame:
    """Build a0 windows for new sources. Split by source/speaker happens after."""
    rows: list[dict] = []
    fsd_verdicts = load_verdicts(FSD_VERDICTS, "freesound_id")
    berst_verdicts = load_verdicts(BERST_VERDICTS, "clip_id")
    log.log(f"Manual verdicts: FSD50K={len(fsd_verdicts)} BERSt={len(berst_verdicts)}")
    log.log(f"FSD50K verdicts: {dict(Counter(fsd_verdicts.values())) if fsd_verdicts else {}}")
    log.log(f"BERSt verdicts: {dict(Counter(berst_verdicts.values())) if berst_verdicts else {}}")

    # --- FSD50K ---
    fsd = list(csv.DictReader(open(FSD_AUDIT, encoding="utf-8")))
    distress_cats = {"LIKELY_DISTRESS"}
    hn_cats = {"NON_DISTRESS_SCREAM", "MOVIE_OR_MEDIA", "MUSIC_RELATED"}
    n_fsd_pos = n_fsd_hn = n_fsd_skip = 0
    for r in fsd:
        fid = str(r["freesound_id"])
        cat = r.get("content_category", "")
        verdict = fsd_verdicts.get(fid, "")
        # Manual verdict overrides audit category.
        if verdict == "DISTRESS":
            label, bucket, keep = 1, "verified_distress", True
        elif verdict == "HARD_NEGATIVE":
            label, bucket, keep = 0, "verified_hard_negative", True
        elif verdict in {"REJECT", "AMBIGUOUS"}:
            keep = False
            label, bucket = 0, "rejected"
        elif cat in distress_cats:
            label, bucket, keep = 1, "fsd50k_likely_distress", True
        elif cat in hn_cats:
            label, bucket, keep = 0, "fsd50k_hard_negative", True
        else:
            keep = False
            label, bucket = 0, "fsd50k_skipped"
        if not keep:
            n_fsd_skip += 1
            continue
        wav = ROOT / r["wav_path"] if not Path(r["wav_path"]).is_absolute() else Path(r["wav_path"])
        if not wav.exists():
            wav = FSD_AUDIO / f"{fid}.wav"
        if not wav.exists():
            n_fsd_skip += 1
            continue
        before = len(rows)
        write_chunks_for_file(
            wav,
            label=label,
            source=fid,
            folder="FSD50K",
            stratum=f"{'distress' if label==1 else 'normal'}/FSD50K/{bucket}",
            bucket=bucket,
            source_dataset="FSD50K",
            speaker=r.get("uploader", "unk"),
            source_label=r.get("source_label", cat),
            license_name=r.get("license", ""),
            out_rows=rows,
        )
        added = len(rows) - before
        if label == 1:
            n_fsd_pos += added
        else:
            n_fsd_hn += added
    log.log(f"FSD50K windows: distress={n_fsd_pos} hard_neg={n_fsd_hn} skipped_files≈{n_fsd_skip}")

    # --- AudioSet Screaming as HARD_NEGATIVE ---
    n_as = 0
    if AS_META.exists():
        as_rows = list(csv.DictReader(open(AS_META, encoding="utf-8")))
        for r in as_rows:
            if (r.get("downloaded_status") or "").upper() != "SUCCESS":
                continue
            local = r.get("local_wav_path") or ""
            if not local:
                continue
            wav = ROOT / local if not Path(local).is_absolute() else Path(local)
            if not wav.exists():
                continue
            vid = r.get("ytid") or r.get("clip_id") or wav.stem
            before = len(rows)
            write_chunks_for_file(
                wav,
                label=0,
                source=str(vid),
                folder="AudioSet_Screaming",
                stratum="normal/AudioSet_Screaming/hard_negative",
                bucket="audioset_hard_negative",
                source_dataset="AudioSet_Screaming",
                speaker="as_unk",
                source_label=r.get("source_label", "SCREAMING"),
                license_name="AudioSet (YouTube-derived; internal research use)",
                out_rows=rows,
            )
            n_as += len(rows) - before
    log.log(f"AudioSet Screaming hard-neg windows: {n_as}")

    # --- BERSt ---
    berst = list(csv.DictReader(open(BERST_META, encoding="utf-8")))
    # Prefer manual HARD_NEGATIVE; otherwise sample preliminary HARD_NEGATIVE.
    manual_hn = [r for r in berst if berst_verdicts.get(r["clip_id"]) == "HARD_NEGATIVE"]
    manual_rej = {r["clip_id"] for r in berst if berst_verdicts.get(r["clip_id"]) in {"REJECT", "AMBIGUOUS"}}
    prelim_hn = [
        r for r in berst
        if r.get("preliminary_category") == "HARD_NEGATIVE"
        and r["clip_id"] not in berst_verdicts
        and r["clip_id"] not in manual_rej
    ]
    rng = np.random.default_rng(RANDOM_STATE)
    if len(prelim_hn) > BERST_HN_FILE_CAP:
        idx = rng.choice(len(prelim_hn), size=BERST_HN_FILE_CAP, replace=False)
        prelim_hn = [prelim_hn[i] for i in sorted(idx)]
    berst_sel = manual_hn + prelim_hn
    # Never add BERSt LIKELY/POSSIBLE as DISTRESS without DISTRESS verdict.
    manual_distress = [r for r in berst if berst_verdicts.get(r["clip_id"]) == "DISTRESS"]
    n_berst_hn = n_berst_pos = 0
    for r in manual_distress:
        wav = ROOT / r["local_path"] if not Path(r["local_path"]).is_absolute() else Path(r["local_path"])
        if not wav.exists():
            continue
        before = len(rows)
        write_chunks_for_file(
            wav, label=1, source=r["clip_id"], folder="BERSt",
            stratum="distress/BERSt/verified",
            bucket="verified_distress",
            source_dataset="BERSt",
            speaker=r.get("speaker_id", "unk"),
            source_label=r.get("source_label", ""),
            license_name=r.get("license", "CC-BY-4.0"),
            out_rows=rows,
        )
        n_berst_pos += len(rows) - before
    for r in berst_sel:
        wav = ROOT / r["local_path"] if not Path(r["local_path"]).is_absolute() else Path(r["local_path"])
        if not wav.exists():
            continue
        bucket = "verified_hard_negative" if r["clip_id"] in berst_verdicts else "berst_hard_negative"
        before = len(rows)
        write_chunks_for_file(
            wav, label=0, source=r["clip_id"], folder="BERSt",
            stratum=f"normal/BERSt/{bucket}",
            bucket=bucket,
            source_dataset="BERSt",
            speaker=r.get("speaker_id", "unk"),
            source_label=r.get("source_label", ""),
            license_name=r.get("license", "CC-BY-4.0"),
            out_rows=rows,
        )
        n_berst_hn += len(rows) - before
    log.log(
        f"BERSt windows: verified_distress={n_berst_pos} hard_neg={n_berst_hn} "
        f"(manual_hn_files={len(manual_hn)} prelim_hn_files={len(prelim_hn)})"
    )

    df = pd.DataFrame(rows)
    if df.empty:
        log.log("WARNING: no new windows collected")
        return df
    df["source_key"] = df.apply(make_source_key_row, axis=1)
    # Drop any accidental overlap with frozen val/test keys
    before = len(df)
    df = df[~df["source_key"].isin(forbidden_keys)].reset_index(drop=True)
    log.log(f"New windows after forbidden-key filter: {len(df)} (dropped {before - len(df)})")
    return df


def split_new_by_source(df: pd.DataFrame, log: Logger) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """75/15/10 by source_key within stratum, BEFORE augmentation."""
    from sklearn.model_selection import train_test_split

    if df.empty:
        return df.copy(), df.copy(), df.copy()

    train_keys, val_keys, test_keys = set(), set(), set()
    for stratum, g in df.groupby(df["stratum"].astype(str)):
        keys = sorted(g["source_key"].unique())
        n = len(keys)
        if n == 1:
            train_keys.add(keys[0])
            log.log(f"NEW SPLIT {stratum}: 1 key → train")
            continue
        if n == 2:
            train_keys.add(keys[0])
            test_keys.add(keys[1])
            log.log(f"NEW SPLIT {stratum}: 2 keys → train+test")
            continue
        if n < 10:
            test_keys.add(keys[0])
            val_keys.add(keys[1])
            train_keys.update(keys[2:])
            log.log(f"NEW SPLIT {stratum}: n={n} → 1 test, 1 val, rest train")
            continue
        tr, vt = train_test_split(keys, test_size=0.25, random_state=RANDOM_STATE)
        va, te = train_test_split(vt, test_size=0.4, random_state=RANDOM_STATE)  # 15% val / 10% test of total
        train_keys.update(tr)
        val_keys.update(va)
        test_keys.update(te)
        log.log(f"NEW SPLIT {stratum}: n={n} → train={len(tr)} val={len(va)} test={len(te)}")

    assert not (train_keys & val_keys or train_keys & test_keys or val_keys & test_keys)

    def take(keys, name):
        out = df[df["source_key"].isin(keys)].copy()
        out["split"] = name
        return out.reset_index(drop=True)

    return take(train_keys, "train"), take(val_keys, "new_val"), take(test_keys, "new_test")


def augment_train_distress(train_df: pd.DataFrame, bank: list[np.ndarray], log: Logger) -> pd.DataFrame:
    base = train_df[(train_df["label"] == 1) & (train_df["aug_idx"] == 0) & (train_df.get("is_new", False) == True)].copy()
    # is_new may be bool or missing for v3 rows — only augment NEW distress here;
    # existing v3 train already carries its augs.
    if "is_new" in train_df.columns:
        base = train_df[(train_df["label"] == 1) & (train_df["aug_idx"] == 0) & (train_df["is_new"] == True)].copy()
    else:
        base = train_df.iloc[0:0].copy()
    log.log(f"Augmenting {len(base)} NEW train distress a0 windows (8x pipeline)")
    np.random.seed(RANDOM_STATE)
    new_rows = []
    for _, row in base.iterrows():
        src = ROOT / row["filepath"]
        try:
            chunk, _ = sf.read(str(src), always_2d=False)
            if getattr(chunk, "ndim", 1) > 1:
                chunk = np.mean(chunk, axis=1)
            chunk = chunk.astype(np.float32)
            if len(chunk) < CHUNK_SAMPLES:
                chunk = np.pad(chunk, (0, CHUNK_SAMPLES - len(chunk)))
            else:
                chunk = chunk[:CHUNK_SAMPLES]
        except Exception as e:
            log.log(f"AUG skip {src}: {e}")
            continue
        versions = augment_chunk(chunk, bank)
        for a_idx, version in enumerate(versions):
            if a_idx == 0:
                continue
            out_name = Path(row["filepath"]).name.replace("_a0.wav", f"_a{a_idx}.wav")
            out_path = CHUNKS / "distress" / out_name
            save_wav(version, out_path)
            r = row.to_dict()
            r["filepath"] = str(out_path.relative_to(ROOT)).replace("\\", "/")
            r["aug_idx"] = int(a_idx)
            new_rows.append(r)
    log.log(f"Created {len(new_rows)} augmented NEW distress windows")
    if new_rows:
        train_df = pd.concat([train_df, pd.DataFrame(new_rows)], ignore_index=True)
    return train_df


def esc50_cat(source: str) -> str:
    try:
        tid = int(Path(source).stem.split("-")[-1])
        return ESC50_CLASSES.get(tid, f"unknown_{tid}")
    except Exception:
        return "unknown"


def is_hard_negative_row(row) -> bool:
    bucket = str(row.get("bucket", ""))
    if bucket.startswith("hard_negative") or "hard_negative" in bucket or bucket.startswith("verified_hard"):
        return True
    if bucket.startswith("fsd50k_hard") or bucket.startswith("audioset_hard") or bucket.startswith("berst_hard"):
        return True
    folder = str(row.get("folder", ""))
    like = row.get("scream_likeness")
    try:
        like = float(like) if like is not None and str(like) not in {"", "nan", "None"} else 0.0
    except Exception:
        like = 0.0
    if folder == "NotScreaming" and like >= 0.55:
        return True
    if folder == "ESC-50-master" and esc50_cat(str(row.get("source", ""))) in ESC50_HARD_CATS:
        return True
    if folder == "Traffic" and like >= 0.50:
        return True
    return False


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
    from sklearn.metrics import average_precision_score, roc_auc_score
    return {
        "pr_auc": float(average_precision_score(y_true, proba)),
        "roc_auc": float(roc_auc_score(y_true, proba)),
    }


def slice_metrics(test_df, y, proba, thr):
    pred = (proba >= thr).astype(int)
    folder = test_df["folder"].astype(str)
    stratum = test_df["stratum"].astype(str)
    bucket = test_df["bucket"].astype(str)
    scream = (folder == "Screaming") & (y == 1)
    phrase = stratum.str.startswith("distress/") & (folder != "Screaming") & (y == 1)
    hard = ((bucket.str.contains("hard_negative", na=False)) |
            (bucket.str.startswith("verified_hard")) |
            (bucket.str.startswith("fsd50k_hard")) |
            (bucket.str.startswith("audioset_hard")) |
            (bucket.str.startswith("berst_hard"))) & (y == 0)
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


def score_operating_point(m: dict) -> float:
    rec = float(m["recall"])
    fpr = float(m["false_positive_rate"])
    f1 = float(m["f1"])
    hn = m.get("hard_negative_fpr")
    hn = float(hn) if hn is not None else fpr
    return float(
        2.0 * rec + 1.2 * f1 - 2.5 * fpr - 1.0 * hn
        + (0.4 if rec >= 0.85 else -0.6)
        + (0.4 if fpr <= 0.12 else (-0.3 if fpr <= 0.15 else -0.8))
    )


def embed_paths(yamnet, filepaths: list[str], log: Logger) -> np.ndarray:
    import tensorflow as tf
    X = np.zeros((len(filepaths), EMBED_DIM), dtype=np.float32)
    for i, fp in enumerate(filepaths):
        path = ROOT / fp if not Path(fp).is_absolute() else Path(fp)
        try:
            audio = tf.io.read_file(str(path))
            wav, _ = tf.audio.decode_wav(audio, desired_channels=1)
            waveform = tf.squeeze(wav, axis=-1).numpy().astype(np.float32)
            if len(waveform) < CHUNK_SAMPLES:
                waveform = np.pad(waveform, (0, CHUNK_SAMPLES - len(waveform)))
            else:
                waveform = waveform[:CHUNK_SAMPLES]
            _, emb, _ = yamnet(waveform)
            X[i] = emb.numpy().mean(axis=0).astype(np.float32)
        except Exception as e:
            log.log(f"embed fail {fp}: {e}")
        if (i + 1) % 500 == 0:
            log.log(f"  embedded {i+1}/{len(filepaths)}")
    return X


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
        name="audio_v5_distress_classifier",
    )
    model.compile(
        optimizer=keras.optimizers.Adam(1e-3),
        loss="binary_crossentropy",
        metrics=["accuracy", keras.metrics.Precision(name="precision"), keras.metrics.Recall(name="recall")],
    )
    return model


def main():
    for d in [DERIVED, CHUNKS / "distress", CHUNKS / "normal", SPLITS, EMB_DIR, META, LOGS_DER, MODEL_DIR, LOG_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = Logger(LOG_DIR / f"audio_v5_training_{ts}.log", LOG_DIR / "audio_v5_training_latest.log")
    started = datetime.now()
    try:
        log.log("=" * 72)
        log.log("SafeHer Audio v5 training")
        log.log(f"Start: {started.isoformat()}")
        log.log(f"Python: {sys.version}")
        log.log(f"Platform: {platform.platform()}")
        log.log("NO SOS connection. audio_v2/v3/v4 untouched.")

        # ---- load frozen v3 splits (Exp02 comparison basis)
        v3_train = pd.read_csv(V3_SPLITS / "train.csv")
        v3_val = pd.read_csv(V3_SPLITS / "val.csv")
        v3_test = pd.read_csv(V3_SPLITS / "test.csv")
        for df in (v3_train, v3_val, v3_test):
            if "source_key" not in df.columns:
                df["source_key"] = df.apply(make_source_key_row, axis=1)
            df["is_new"] = False
            if "source_dataset" not in df.columns:
                df["source_dataset"] = "SafeHer_v3"
            else:
                df["source_dataset"] = df["source_dataset"].fillna("SafeHer_v3")

        forbidden = set(v3_val["source_key"]) | set(v3_test["source_key"])
        log.log(f"Frozen v3: train={len(v3_train)} val={len(v3_val)} test={len(v3_test)}")
        log.log(f"Forbidden source keys (val∪test): {len(forbidden)}")

        # ---- collect + source-split NEW data before aug
        bank = build_noise_bank(log)
        new_df = collect_new_sources(log, forbidden)
        new_train, new_val, new_test = split_new_by_source(new_df, log)
        log.log(f"New split windows: train={len(new_train)} new_val={len(new_val)} new_test={len(new_test)}")
        log.log(f"New train labels: {dict(Counter(new_train['label'])) if len(new_train) else {}}")

        # Augment only NEW train distress
        new_train = augment_train_distress(new_train, bank, log)

        # Combine: frozen v3 + new
        train_df = pd.concat([v3_train, new_train], ignore_index=True)
        # Keep frozen val/test for Exp02 apples-to-apples; also keep new holdouts for reporting
        val_df = v3_val.copy()
        test_df = v3_test.copy()
        new_val_df = new_val.copy()
        new_test_df = new_test.copy()

        # Leakage checks
        assert len(set(train_df["source_key"]) & set(test_df["source_key"])) == 0
        assert len(set(train_df["source_key"]) & set(val_df["source_key"])) == 0
        log.log(f"Combined train={len(train_df)} (v3={len(v3_train)} + new={len(new_train)})")
        log.log(f"Train label counts: {dict(Counter(train_df['label']))}")
        log.log(f"Train buckets top: {Counter(train_df['bucket']).most_common(12)}")

        train_df.to_csv(SPLITS / "train.csv", index=False)
        val_df.to_csv(SPLITS / "val.csv", index=False)
        test_df.to_csv(SPLITS / "test.csv", index=False)
        new_val_df.to_csv(SPLITS / "new_val.csv", index=False)
        new_test_df.to_csv(SPLITS / "new_test.csv", index=False)
        (META / "data_policy.json").write_text(json.dumps({
            "existing_safeher": "audio_v3_prep frozen val/test; full train including prior augs",
            "new_distress": "FSD50K LIKELY_DISTRESS + any manual DISTRESS verdicts",
            "new_hard_negatives": [
                "FSD50K NON_DISTRESS_SCREAM/MOVIE_OR_MEDIA/MUSIC_RELATED",
                "AudioSet Screaming",
                "BERSt manual HARD_NEGATIVE",
                f"BERSt preliminary HARD_NEGATIVE (capped at {BERST_HN_FILE_CAP} files)",
            ],
            "excluded_as_distress": [
                "BERSt LIKELY/POSSIBLE without DISTRESS verdict",
                "FSD50K POSSIBLE/AMBIGUOUS without DISTRESS verdict",
            ],
            "split_rule": "new sources split by source/speaker before augmentation; v3 val/test frozen",
            "augmentation": "8x distress aug on NEW train distress only; v3 train augs reused",
        }, indent=2), encoding="utf-8")

        # ---- embeddings: reuse v3 cache, embed new rows
        import tensorflow as tf
        import tensorflow_hub as hub
        from tensorflow import keras
        from tensorflow.keras import layers
        import sklearn

        log.log(f"numpy={np.__version__} pandas={pd.__version__} sklearn={sklearn.__version__} tf={tf.__version__}")
        log.log("Loading YAMNet...")
        yamnet = hub.load(YAMNET_URL)

        def load_v3_emb(split: str, df: pd.DataFrame) -> np.ndarray:
            z = np.load(V3_EMB / f"{split}.npz")
            X = z["X"].astype(np.float32)
            assert len(X) == len(df), f"{split} emb {len(X)} != df {len(df)}"
            return X

        Xtr_v3 = load_v3_emb("train", v3_train)
        Xva = load_v3_emb("val", val_df)
        Xte = load_v3_emb("test", test_df)

        new_train_part = train_df.iloc[len(v3_train):].reset_index(drop=True)
        log.log(f"Embedding {len(new_train_part)} new train windows...")
        Xtr_new = embed_paths(yamnet, new_train_part["filepath"].tolist(), log) if len(new_train_part) else np.zeros((0, EMBED_DIM), np.float32)
        Xtr = np.concatenate([Xtr_v3, Xtr_new], axis=0)
        assert len(Xtr) == len(train_df)

        X_new_val = embed_paths(yamnet, new_val_df["filepath"].tolist(), log) if len(new_val_df) else np.zeros((0, EMBED_DIM), np.float32)
        X_new_test = embed_paths(yamnet, new_test_df["filepath"].tolist(), log) if len(new_test_df) else np.zeros((0, EMBED_DIM), np.float32)

        np.savez_compressed(EMB_DIR / "train.npz", X=Xtr, y=train_df["label"].to_numpy(np.int32))
        np.savez_compressed(EMB_DIR / "val.npz", X=Xva, y=val_df["label"].to_numpy(np.int32))
        np.savez_compressed(EMB_DIR / "test.npz", X=Xte, y=test_df["label"].to_numpy(np.int32))
        if len(new_val_df):
            np.savez_compressed(EMB_DIR / "new_val.npz", X=X_new_val, y=new_val_df["label"].to_numpy(np.int32))
        if len(new_test_df):
            np.savez_compressed(EMB_DIR / "new_test.npz", X=X_new_test, y=new_test_df["label"].to_numpy(np.int32))
        log.log(f"Embedding shapes train={Xtr.shape} val={Xva.shape} test={Xte.shape}")

        # ---- sample weights (Exp02 recipe)
        ytr = train_df["label"].astype(np.int32).to_numpy()
        yva = val_df["label"].astype(np.int32).to_numpy()
        yte = test_df["label"].astype(np.int32).to_numpy()
        hard_mask = train_df.apply(is_hard_negative_row, axis=1).to_numpy()
        sw = np.ones(len(train_df), dtype=np.float32)
        sw[ytr == 1] = float(DISTRESS_W)
        sw[(ytr == 0) & hard_mask] = float(HARD_NEG_W)
        log.log(f"Sample weights: distress_w={DISTRESS_W} hard_neg_w={HARD_NEG_W} "
                f"hard_assigned={int(((ytr==0)&hard_mask).sum())} mean={sw.mean():.3f}")

        # ---- train
        model = build_model(keras, layers)
        ckpt = MODEL_DIR / "best_weights.weights.h5"
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
        log.log(f"Train seconds: {train_secs:.1f} epochs={len(hist.history.get('loss', []))}")

        keras_path = MODEL_DIR / "audio_distress_classifier.keras"
        model.save(keras_path)

        # ---- evaluate v5
        proba_te = model.predict(Xte, verbose=0).ravel()
        proba_va = model.predict(Xva, verbose=0).ravel()

        val_cands = []
        for t in THRESHOLDS:
            m = slice_metrics(val_df, yva, proba_va, t)
            m["selection_score"] = score_operating_point(m)
            val_cands.append(m)
        best_val = max(val_cands, key=lambda x: x["selection_score"])

        at_0_5 = slice_metrics(test_df, yte, proba_te, 0.5)
        selected = slice_metrics(test_df, yte, proba_te, best_val["threshold"])
        selected["chosen_on"] = "validation_selection_score"
        selected["selection_score"] = score_operating_point(selected)

        thr_sweep = []
        for t in THRESHOLDS:
            m = slice_metrics(test_df, yte, proba_te, t)
            m["selection_score"] = score_operating_point(m)
            thr_sweep.append(m)

        kn_rows = []
        for thr in sorted({0.5, float(best_val["threshold"])}):
            for K in K_VALUES:
                m = file_kofn(test_df, yte, proba_te, thr=thr, K=K, N=5)
                m.update({"threshold": thr, "K": K, "N": 5, "mode": "k_of_n"})
                m["selection_score"] = score_operating_point({**m, "hard_negative_fpr": m["false_positive_rate"]})
                kn_rows.append(m)
        best_kn = max(kn_rows, key=lambda x: x["selection_score"])

        # new-data holdout metrics (if any)
        new_holdout = {}
        if len(new_test_df):
            ynt = new_test_df["label"].astype(np.int32).to_numpy()
            pnt = model.predict(X_new_test, verbose=0).ravel()
            new_holdout = {
                "at_0.5": slice_metrics(new_test_df, ynt, pnt, 0.5),
                "at_selected": slice_metrics(new_test_df, ynt, pnt, best_val["threshold"]),
                "n": int(len(new_test_df)),
                "label_counts": dict(Counter(ynt.tolist())),
            }

        # ---- Exp02 on SAME frozen test
        log.log("Evaluating Audio v4 Exp02 on frozen test set...")
        exp02 = keras.models.load_model(EXP02_DIR / "audio_distress_classifier.keras")
        p02 = exp02.predict(Xte, verbose=0).ravel()
        exp02_at_0_5 = slice_metrics(test_df, yte, p02, 0.5)
        exp02_metrics = json.loads((EXP02_DIR / "metrics.json").read_text(encoding="utf-8"))

        def delta(a, b, key):
            if a.get(key) is None or b.get(key) is None:
                return None
            return float(a[key]) - float(b[key])

        comparison = {
            "test_set": "audio_v3_prep frozen test (identical windows/embeddings)",
            "audio_v4_exp02_at_0.5": exp02_at_0_5,
            "audio_v5_at_0.5": at_0_5,
            "audio_v5_at_val_selected": selected,
            "deltas_v5_minus_exp02_at_0.5": {
                k: delta(at_0_5, exp02_at_0_5, k)
                for k in ["accuracy", "precision", "recall", "f1", "false_positive_rate",
                          "false_negative_rate", "pr_auc", "roc_auc",
                          "screaming_recall", "phrase_recall", "hard_negative_fpr"]
            },
            "exp02_published_metrics_note": "Re-scored Exp02 weights on this run's frozen test for fairness.",
            "exp02_original_metrics_at_0.5": exp02_metrics.get("test_window_at_0.5"),
        }

        # ---- save artifacts
        from sklearn.preprocessing import LabelEncoder
        le = LabelEncoder()
        le.fit(["NORMAL", "DISTRESS"])
        joblib.dump(le, MODEL_DIR / "label_encoder.joblib")
        shutil.copy2(V3_AGG / "aggregation_config.json", MODEL_DIR / "aggregation_config.json")
        shutil.copy2(V3_AGG / "aggregate_scores.py", MODEL_DIR / "aggregate_scores.py")

        cfg = {
            "name": "audio_v5",
            "architecture": "Dense(256)-Dropout(0.4)-Dense(64)-Dropout(0.3)-Dense(1,sigmoid)",
            "input_dim": 1024,
            "feature_type": "YAMNet_embedding_1024",
            "distress_w": DISTRESS_W,
            "hard_neg_w": HARD_NEG_W,
            "train_seconds": train_secs,
            "epochs_ran": len(hist.history.get("loss", [])),
            "dataset": str(DERIVED),
            "parent_v3_prep": str(V3),
            "connected_to_sos": False,
            "not_production_ready": True,
        }
        (MODEL_DIR / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        (MODEL_DIR / "feature_config.json").write_text(json.dumps({
            "feature_type": "YAMNet_embedding_1024",
            "threshold_default": 0.5,
            "threshold_selected_on_val": best_val["threshold"],
            "scaler": None,
        }, indent=2), encoding="utf-8")

        metrics = {
            "note": "Audio v5. Not connected to SOS. Does not overwrite v2/v3/v4.",
            "test_window_at_0.5": at_0_5,
            "test_window_at_val_selected_threshold": selected,
            "validation_selected_threshold": best_val,
            "threshold_sweep_test": thr_sweep,
            "k_of_n_sweep_test": kn_rows,
            "best_k_of_n_test": best_kn,
            "new_data_holdout": new_holdout,
            "comparison_vs_audio_v4_exp02": comparison,
            "connected_to_sos": False,
            "data_counts": {
                "train": int(len(train_df)),
                "val": int(len(val_df)),
                "test": int(len(test_df)),
                "new_train": int(len(new_train)),
                "new_val": int(len(new_val_df)),
                "new_test": int(len(new_test_df)),
                "train_distress": int((train_df.label == 1).sum()),
                "train_normal": int((train_df.label == 0).sum()),
            },
        }
        (MODEL_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        (MODEL_DIR / "confusion_matrix.json").write_text(json.dumps({
            "window_0.5": {"tp": at_0_5["tp"], "tn": at_0_5["tn"], "fp": at_0_5["fp"], "fn": at_0_5["fn"]},
            "window_selected": {
                "threshold": selected["threshold"],
                "tp": selected["tp"], "tn": selected["tn"],
                "fp": selected["fp"], "fn": selected["fn"],
            },
        }, indent=2), encoding="utf-8")
        (MODEL_DIR / "model_metadata.json").write_text(json.dumps({
            "name": "audio_v5",
            "created": datetime.now().isoformat(timespec="seconds"),
            "compared_to": "audio_v4_exp02",
            "not_production_ready": True,
            "connected_to_sos": False,
        }, indent=2), encoding="utf-8")
        (MODEL_DIR / "comparison_vs_exp02.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
        np.savez_compressed(MODEL_DIR / "test_probabilities.npz", proba=proba_te, y=yte, proba_exp02=p02)

        # ---- markdown summary
        def fmt(m, k):
            v = m.get(k)
            return "—" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v))

        md = f"""# Audio v5 training summary

Run: {started.isoformat(timespec='seconds')} → {datetime.now().isoformat(timespec='seconds')}  
Model: `data/models/audio_v5/`  
**Not connected to SOS. audio_v2 / v3 / v4 untouched.**

## Data policy

| Source | Role |
|---|---|
| Existing SafeHer (audio_v3_prep) | Full train (incl. prior augs); **frozen** val/test for Exp02 comparison |
| FSD50K LIKELY_DISTRESS | NEW distress positives (audit-promoted; 0 manual DISTRESS verdicts available) |
| FSD50K NON_DISTRESS_SCREAM / MOVIE / MUSIC | NEW hard-negatives |
| AudioSet Screaming | NEW hard-negatives |
| BERSt manual HARD_NEGATIVE | NEW hard-negatives |
| BERSt preliminary HARD_NEGATIVE (capped {BERST_HN_FILE_CAP} files) | NEW hard-negatives |
| BERSt LIKELY/POSSIBLE | **Excluded** as distress (2 listened clips contradicted the heuristic) |

New sources were split by source/speaker **before** augmentation. Augmentation (8×) applied only to **new train distress**.

| Split | Windows |
|---|---:|
| Train (combined) | {len(train_df)} |
| Val (frozen v3) | {len(val_df)} |
| Test (frozen v3) | {len(test_df)} |
| New train added | {len(new_train)} |
| New holdout test | {len(new_test_df)} |

## Metrics — Audio v5 (frozen test @ 0.5)

| Metric | Value |
|---|---:|
| Accuracy | {fmt(at_0_5,'accuracy')} |
| Precision | {fmt(at_0_5,'precision')} |
| Recall | {fmt(at_0_5,'recall')} |
| F1 | {fmt(at_0_5,'f1')} |
| FPR | {fmt(at_0_5,'false_positive_rate')} |
| FNR | {fmt(at_0_5,'false_negative_rate')} |
| PR-AUC | {fmt(at_0_5,'pr_auc')} |
| ROC-AUC | {fmt(at_0_5,'roc_auc')} |
| Screaming recall | {fmt(at_0_5,'screaming_recall')} |
| Phrase recall | {fmt(at_0_5,'phrase_recall')} |
| Hard-negative FPR | {fmt(at_0_5,'hard_negative_fpr')} |
| Confusion (TP/TN/FP/FN) | {at_0_5['tp']}/{at_0_5['tn']}/{at_0_5['fp']}/{at_0_5['fn']} |

Val-selected threshold: **{best_val['threshold']}**  
At selected: recall={fmt(selected,'recall')} FPR={fmt(selected,'false_positive_rate')} F1={fmt(selected,'f1')} HN_FPR={fmt(selected,'hard_negative_fpr')}

Best K-of-N: K={best_kn.get('K')} thr={best_kn.get('threshold')} recall={fmt(best_kn,'recall')} FPR={fmt(best_kn,'false_positive_rate')}

## Comparison vs Audio v4 Exp02 (same frozen test @ 0.5)

| Metric | Exp02 | v5 | Δ (v5−Exp02) |
|---|---:|---:|---:|
| Accuracy | {fmt(exp02_at_0_5,'accuracy')} | {fmt(at_0_5,'accuracy')} | {comparison['deltas_v5_minus_exp02_at_0.5']['accuracy']:.4f} |
| Precision | {fmt(exp02_at_0_5,'precision')} | {fmt(at_0_5,'precision')} | {comparison['deltas_v5_minus_exp02_at_0.5']['precision']:.4f} |
| Recall | {fmt(exp02_at_0_5,'recall')} | {fmt(at_0_5,'recall')} | {comparison['deltas_v5_minus_exp02_at_0.5']['recall']:.4f} |
| F1 | {fmt(exp02_at_0_5,'f1')} | {fmt(at_0_5,'f1')} | {comparison['deltas_v5_minus_exp02_at_0.5']['f1']:.4f} |
| FPR | {fmt(exp02_at_0_5,'false_positive_rate')} | {fmt(at_0_5,'false_positive_rate')} | {comparison['deltas_v5_minus_exp02_at_0.5']['false_positive_rate']:.4f} |
| FNR | {fmt(exp02_at_0_5,'false_negative_rate')} | {fmt(at_0_5,'false_negative_rate')} | {comparison['deltas_v5_minus_exp02_at_0.5']['false_negative_rate']:.4f} |
| PR-AUC | {fmt(exp02_at_0_5,'pr_auc')} | {fmt(at_0_5,'pr_auc')} | {comparison['deltas_v5_minus_exp02_at_0.5']['pr_auc']:.4f} |
| ROC-AUC | {fmt(exp02_at_0_5,'roc_auc')} | {fmt(at_0_5,'roc_auc')} | {comparison['deltas_v5_minus_exp02_at_0.5']['roc_auc']:.4f} |
| Screaming recall | {fmt(exp02_at_0_5,'screaming_recall')} | {fmt(at_0_5,'screaming_recall')} | {comparison['deltas_v5_minus_exp02_at_0.5']['screaming_recall']:.4f} |
| Phrase recall | {fmt(exp02_at_0_5,'phrase_recall')} | {fmt(at_0_5,'phrase_recall')} | {comparison['deltas_v5_minus_exp02_at_0.5']['phrase_recall']:.4f} |
| Hard-neg FPR | {fmt(exp02_at_0_5,'hard_negative_fpr')} | {fmt(at_0_5,'hard_negative_fpr')} | {comparison['deltas_v5_minus_exp02_at_0.5']['hard_negative_fpr']:.4f} |

## Outputs

- `data/models/audio_v5/audio_distress_classifier.keras`
- `data/models/audio_v5/metrics.json`
- `data/models/audio_v5/comparison_vs_exp02.json`
- `data/derived/audio_v5_prep/`
- `data/training_logs/audio_v5_training_{ts}.log`
"""
        summary_path = LOG_DIR / "audio_v5_training_summary.md"
        summary_path.write_text(md, encoding="utf-8")
        (MODEL_DIR / "README.md").write_text(md, encoding="utf-8")
        log.log(f"Wrote {summary_path}")
        log.log(f"v5 @0.5: rec={at_0_5['recall']:.3f} FPR={at_0_5['false_positive_rate']:.3f} "
                f"F1={at_0_5['f1']:.3f} HN_FPR={at_0_5['hard_negative_fpr']}")
        log.log(f"Exp02 @0.5: rec={exp02_at_0_5['recall']:.3f} FPR={exp02_at_0_5['false_positive_rate']:.3f} "
                f"F1={exp02_at_0_5['f1']:.3f} HN_FPR={exp02_at_0_5['hard_negative_fpr']}")
        log.log("STATUS=AUDIO_V5_COMPLETE")
        print("===AUDIO_V5===")
        print(json.dumps({
            "train": len(train_df), "new_train": len(new_train),
            "v5_at_0.5": {k: at_0_5[k] for k in
                          ["accuracy", "precision", "recall", "f1", "false_positive_rate",
                           "false_negative_rate", "pr_auc", "roc_auc",
                           "screaming_recall", "phrase_recall", "hard_negative_fpr"]},
            "exp02_at_0.5": {k: exp02_at_0_5[k] for k in
                             ["accuracy", "precision", "recall", "f1", "false_positive_rate",
                              "false_negative_rate", "pr_auc", "roc_auc",
                              "screaming_recall", "phrase_recall", "hard_negative_fpr"]},
            "model_dir": str(MODEL_DIR),
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
