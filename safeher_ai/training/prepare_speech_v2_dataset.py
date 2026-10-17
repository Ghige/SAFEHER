"""
SafeHer — prepare Speech v2 derived dataset (NO TRAINING).

Creates:
  data/derived/speech_v2_prep/
    emergency/{english,hindi,marathi}/...
    normal/{english,hindi,marathi}/...
    metadata/

Preserves existing emergency WAVs under data/speech/emergency_phrases/
(copies into derived only; originals untouched).

Normal speech source:
  Google FLEURS (CC-BY-4.0) — en_us / hi_in / mr_in train splits.
  Read / conversational ASR prompts (not music, not emotional-distress labels).
  Capped per language for balance inside the 2k–5k target.

Does NOT:
  - train Speech v2
  - create train/val/test splits
  - augment
  - modify Audio / Movement / SOS / Android / backend
  - modify existing speech or raw data

Run:
  ..\\venv311\\Scripts\\python.exe training\\prepare_speech_v2_dataset.py
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import traceback
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SRC_EMERGENCY = DATA / "speech" / "emergency_phrases"
SRC_NORMAL = DATA / "speech" / "normal"

OUT = DATA / "derived" / "speech_v2_prep"
OUT_EM = OUT / "emergency"
OUT_NM = OUT / "normal"
META = OUT / "metadata"
LOG_DIR = DATA / "training_logs"

TARGET_SR = 16000
MAX_PER_LANG = 1500          # balance EN/HI/MR inside 2k–5k total
MIN_DUR_S = 0.4
MAX_DUR_S = 30.0
RANDOM_STATE = 42

LANG_MAP = {
    "english": "english",
    "hindi": "hindi",
    "marathi": "marathi",
}

FLEURS_CFGS = {
    "english": "en_us",
    "hindi": "hi_in",
    "marathi": "mr_in",
}

GENDER_MAP = {0: "male", 1: "female", 2: "other"}

# Reject NORMAL clips whose transcript looks like an emergency phrase.
EMERGENCY_PATTERNS = [
    re.compile(r"\bhelp\s*me\b", re.I),
    re.compile(r"\bi\s*need\s*help\b", re.I),
    re.compile(r"\bcall\s*police\b", re.I),
    re.compile(r"\bcall\s*911\b", re.I),
    re.compile(r"\bemergency\b", re.I),
    re.compile(r"मुझे\s*बचाओ"),
    re.compile(r"मदद\s*करो"),
    re.compile(r"मदत\s*करो"),
    re.compile(r"bachao", re.I),
    re.compile(r"madat\s*karo", re.I),
    re.compile(r"mujhe\s*bachao", re.I),
]


class Logger:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(path, "w", encoding="utf-8")
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def log(self, msg: str = ""):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        try:
            print(line, flush=True)
        except UnicodeEncodeError:
            print(line.encode("ascii", "replace").decode("ascii"), flush=True)
        self.fh.write(line + "\n")
        self.fh.flush()

    def warn(self, msg: str):
        self.warnings.append(msg)
        self.log(f"WARNING: {msg}")

    def error(self, msg: str):
        self.errors.append(msg)
        self.log(f"ERROR: {msg}")

    def close(self):
        self.fh.close()


def ensure_dirs():
    for lang in LANG_MAP:
        (OUT_EM / lang).mkdir(parents=True, exist_ok=True)
        (OUT_NM / lang).mkdir(parents=True, exist_ok=True)
    META.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def phrase_slug(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def to_16k_mono(y: np.ndarray, sr: int) -> np.ndarray:
    if y.ndim > 1:
        y = np.mean(y, axis=1)
    y = y.astype(np.float32)
    if sr != TARGET_SR:
        y = librosa.resample(y, orig_sr=sr, target_sr=TARGET_SR)
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    if peak > 1e-8:
        y = y / peak
    return y.astype(np.float32)


def write_wav(path: Path, y: np.ndarray):
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), y, TARGET_SR, subtype="PCM_16")


def looks_emergency(text: str) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in EMERGENCY_PATTERNS)


def copy_emergency(log: Logger) -> list[dict]:
    rows: list[dict] = []
    if not SRC_EMERGENCY.exists():
        raise FileNotFoundError(f"Missing {SRC_EMERGENCY}")

    for lang_dir in sorted(p for p in SRC_EMERGENCY.iterdir() if p.is_dir()):
        lang = LANG_MAP.get(lang_dir.name.lower())
        if not lang:
            log.warn(f"Skip unknown emergency language folder: {lang_dir.name}")
            continue
        for phrase_dir in sorted(p for p in lang_dir.iterdir() if p.is_dir()):
            phrase = phrase_slug(phrase_dir.name)
            wavs = sorted(phrase_dir.glob("*.wav"))
            log.log(f"Emergency source {lang}/{phrase}: {len(wavs)} wavs")
            for i, src in enumerate(wavs, 1):
                try:
                    y, sr = sf.read(str(src), always_2d=False)
                    y16 = to_16k_mono(np.asarray(y), int(sr))
                    if len(y16) < int(MIN_DUR_S * TARGET_SR):
                        log.warn(f"Skip short emergency {src.name}")
                        continue
                    dest_name = f"em_{lang}_{phrase}_{i:04d}_{src.stem}.wav"
                    dest_name = re.sub(r"[^A-Za-z0-9._-]+", "_", dest_name)
                    dest = OUT_EM / lang / dest_name
                    write_wav(dest, y16)
                    rows.append({
                        "clip_id": f"em_{lang}_{phrase}_{i:04d}",
                        "source_dataset": "SafeHer_existing_emergency_phrases",
                        "original_filename": src.name,
                        "original_id": src.stem,
                        "speaker_id": "",
                        "gender": "",
                        "language": lang,
                        "phrase": phrase,
                        "original_label": phrase,
                        "safeher_label": "EMERGENCY",
                        "local_path": str(dest.relative_to(ROOT)).replace("\\", "/"),
                        "source_path": str(src.relative_to(ROOT)).replace("\\", "/"),
                        "duration_s": round(len(y16) / TARGET_SR, 3),
                        "sample_rate": TARGET_SR,
                        "channels": 1,
                        "license": "SafeHer internal emergency phrase recordings",
                        "transcription": phrase.replace("_", " "),
                        "status": "COPIED",
                        "reject_reason": "",
                    })
                except Exception as e:
                    log.error(f"Emergency copy failed {src}: {e}")
                    rows.append({
                        "clip_id": f"em_fail_{src.stem}",
                        "source_dataset": "SafeHer_existing_emergency_phrases",
                        "original_filename": src.name,
                        "original_id": src.stem,
                        "speaker_id": "",
                        "gender": "",
                        "language": lang,
                        "phrase": phrase,
                        "original_label": phrase,
                        "safeher_label": "EMERGENCY",
                        "local_path": "",
                        "source_path": str(src),
                        "duration_s": "",
                        "sample_rate": "",
                        "channels": "",
                        "license": "SafeHer internal emergency phrase recordings",
                        "transcription": "",
                        "status": "FAILED",
                        "reject_reason": str(e)[:200],
                    })
    return rows


def ingest_fleurs(log: Logger) -> tuple[list[dict], list[dict]]:
    """Return (accepted_rows, rejected_rows)."""
    from datasets import Audio, load_dataset

    rng = np.random.default_rng(RANDOM_STATE)
    accepted: list[dict] = []
    rejected: list[dict] = []

    for lang, cfg in FLEURS_CFGS.items():
        log.log(f"Loading FLEURS {cfg} train for {lang}...")
        ds = load_dataset("google/fleurs", cfg, split="train")
        ds = ds.cast_column("audio", Audio(decode=False))
        n_all = len(ds)
        log.log(f"  available clips: {n_all}")

        # Stable shuffle by index for reproducibility, then take up to MAX_PER_LANG
        # after filters. We iterate a shuffled index order.
        order = np.arange(n_all)
        rng.shuffle(order)

        kept = 0
        seen_hashes: set[str] = set()
        for idx in order:
            if kept >= MAX_PER_LANG:
                break
            ex = ds[int(idx)]
            text = (ex.get("transcription") or ex.get("raw_transcription") or "").strip()
            audio = ex.get("audio") or {}
            raw = audio.get("bytes")
            audio_name = audio.get("path") or f"{ex.get('id', idx)}.wav"
            clip_stem = Path(str(audio_name)).stem
            orig_id = str(ex.get("id", clip_stem))

            base_meta = {
                "clip_id": f"fleurs_{lang}_{clip_stem}",
                "source_dataset": "Google_FLEURS",
                "original_filename": Path(str(audio_name)).name,
                "original_id": orig_id,
                "speaker_id": "",  # not exposed in HF FLEURS packaging
                "gender": GENDER_MAP.get(int(ex.get("gender", -1)), ""),
                "language": lang,
                "phrase": "",
                "original_label": "fleurs_asr_utterance",
                "safeher_label": "NORMAL",
                "local_path": "",
                "source_path": f"hf:google/fleurs/{cfg}/train/{clip_stem}",
                "duration_s": "",
                "sample_rate": TARGET_SR,
                "channels": 1,
                "license": "CC-BY-4.0",
                "transcription": text,
                "status": "REJECTED",
                "reject_reason": "",
            }

            if looks_emergency(text):
                base_meta["reject_reason"] = "transcript_matches_emergency_phrase"
                rejected.append(base_meta)
                continue
            if raw is None:
                base_meta["reject_reason"] = "missing_audio_bytes"
                rejected.append(base_meta)
                continue

            try:
                y, sr = sf.read(io.BytesIO(raw), always_2d=False)
                y16 = to_16k_mono(np.asarray(y), int(sr))
                dur = len(y16) / TARGET_SR
                if dur < MIN_DUR_S:
                    base_meta["reject_reason"] = f"too_short:{dur:.2f}s"
                    rejected.append(base_meta)
                    continue
                if dur > MAX_DUR_S:
                    base_meta["reject_reason"] = f"too_long:{dur:.2f}s"
                    rejected.append(base_meta)
                    continue
                # Dedup by audio hash of first 1s
                h = hashlib.md5(y16[:TARGET_SR].tobytes()).hexdigest()
                if h in seen_hashes:
                    base_meta["reject_reason"] = "duplicate_audio_hash"
                    rejected.append(base_meta)
                    continue
                seen_hashes.add(h)

                dest_name = f"nm_fleurs_{lang}_{kept+1:04d}_{clip_stem}.wav"
                dest_name = re.sub(r"[^A-Za-z0-9._-]+", "_", dest_name)
                dest = OUT_NM / lang / dest_name
                write_wav(dest, y16)

                base_meta.update({
                    "local_path": str(dest.relative_to(ROOT)).replace("\\", "/"),
                    "duration_s": round(dur, 3),
                    "status": "COPIED",
                    "reject_reason": "",
                })
                accepted.append(base_meta)
                kept += 1
            except Exception as e:
                base_meta["reject_reason"] = f"decode_error:{str(e)[:160]}"
                rejected.append(base_meta)

        log.log(f"  kept {kept}/{n_all} for {lang} (cap={MAX_PER_LANG})")

    return accepted, rejected


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / "speech_v2_dataset_prep.log"
    summary_path = LOG_DIR / "speech_v2_dataset_prep_summary.md"
    log = Logger(log_path)
    started = datetime.now()

    try:
        log.log("=" * 72)
        log.log("SafeHer Speech v2 dataset preparation (NO TRAINING)")
        log.log(f"Start: {started.isoformat()}")
        log.log(f"Output: {OUT}")
        log.log("Will NOT modify: existing speech files, Audio v2-v5, Movement, SOS, Android, backend")
        log.log("Will NOT train. Will NOT augment. Will NOT create train/val/test splits.")

        # Existing normal folder check (do not invent from it — currently empty)
        existing_normal = list(SRC_NORMAL.rglob("*.wav")) if SRC_NORMAL.exists() else []
        log.log(f"Existing data/speech/normal wavs: {len(existing_normal)} (not used as source; FLEURS is primary)")

        # --- emergency ---
        em_rows = copy_emergency(log)
        em_ok = [r for r in em_rows if r["status"] == "COPIED"]
        em_fail = [r for r in em_rows if r["status"] != "COPIED"]
        log.log(f"Emergency copied: {len(em_ok)}  failed: {len(em_fail)}")

        # --- normal from FLEURS ---
        nm_ok, nm_rej = ingest_fleurs(log)
        log.log(f"Normal accepted: {len(nm_ok)}  rejected: {len(nm_rej)}")

        # --- metadata ---
        fields = [
            "clip_id", "source_dataset", "original_filename", "original_id",
            "speaker_id", "gender", "language", "phrase", "original_label",
            "safeher_label", "local_path", "source_path", "duration_s",
            "sample_rate", "channels", "license", "transcription",
            "status", "reject_reason",
        ]
        all_ok = em_ok + nm_ok
        write_csv(META / "speech_metadata.csv", all_ok, fields)
        write_csv(META / "rejected.csv", em_fail + nm_rej, fields)
        write_csv(META / "emergency_metadata.csv", em_ok, fields)
        write_csv(META / "normal_metadata.csv", nm_ok, fields)

        # license summary
        (META / "LICENSE_SUMMARY.md").write_text(
            f"""# Speech v2 prep — license summary

## Emergency phrases (SafeHer existing)

- Source: `data/speech/emergency_phrases/` (copied into derived; originals preserved)
- Count: {len(em_ok)}
- License: SafeHer internal recordings
- SafeHer label: **EMERGENCY**

## Normal speech — Google FLEURS

- Source: https://huggingface.co/datasets/google/fleurs
- Configs used: `en_us`, `hi_in`, `mr_in` (train split only)
- License: **Creative Commons Attribution 4.0 (CC-BY-4.0)**
- Commercial use: permitted with attribution
- SafeHer label: **NORMAL** (original FLEURS label preserved as `fleurs_asr_utterance`)
- Speaker IDs: **not available** in the Hugging Face FLEURS packaging used here
  (gender is recorded when present). No train/val/test split was created.

### Required attribution

> Contains material from the FLEURS dataset (Google), used under CC-BY-4.0.
> https://huggingface.co/datasets/google/fleurs

## Rejected / not used

- Mozilla Common Voice: primary HF hosts redirected to Mozilla Data Collective;
  not used in this run to avoid unclear/gated redistribution paths.
- IndicVoices: gated HF access; not used.
- OpenSLR MUCS Hindi/Marathi: 8 kHz story read-speech; skipped in favour of
  higher-rate FLEURS conversational/ASR prompts.
- Emotional corpora (e.g. RAVDESS): not labelled EMERGENCY; not ingested here.
""",
            encoding="utf-8",
        )

        # stats
        by_label = Counter(r["safeher_label"] for r in all_ok)
        by_lang = Counter(r["language"] for r in all_ok)
        by_lang_label = Counter((r["language"], r["safeher_label"]) for r in all_ok)
        by_source = Counter(r["source_dataset"] for r in all_ok)
        speakers = {r["speaker_id"] for r in all_ok if r.get("speaker_id")}
        total_dur = sum(float(r["duration_s"]) for r in all_ok if r.get("duration_s") != "")

        em_lang = Counter(r["language"] for r in em_ok)
        nm_lang = Counter(r["language"] for r in nm_ok)
        em_phrase = Counter(r["phrase"] for r in em_ok)

        # verify originals untouched
        orig_count = len(list(SRC_EMERGENCY.rglob("*.wav")))
        log.log(f"Original emergency wavs still on disk: {orig_count}")

        summary = f"""# Speech v2 dataset preparation summary

Run: {started.isoformat(timespec='seconds')} → {datetime.now().isoformat(timespec='seconds')}  
Dataset: `safeher_ai/data/derived/speech_v2_prep/`

**NO TRAINING. Existing speech / Audio / Movement / SOS / Android / backend untouched.**

## Existing emergency recordings

| Phrase | Language | Count |
|---|---|---:|
| help_me | english | {em_phrase.get('help_me', 0)} |
| i_need_help | english | {em_phrase.get('i_need_help', 0)} |
| mujhe_bachao | hindi | {em_phrase.get('mujhe_bachao', 0)} |
| madat_karo | marathi | {em_phrase.get('madat_karo', 0)} |
| **Total emergency** | | **{len(em_ok)}** |

Originals remain under `data/speech/emergency_phrases/` ({orig_count} wavs). Derived copies are 16 kHz mono.

## New normal recordings (Google FLEURS, CC-BY-4.0)

| Language | Count | Cap |
|---|---:|---:|
| english | {nm_lang.get('english', 0)} | {MAX_PER_LANG} |
| hindi | {nm_lang.get('hindi', 0)} | {MAX_PER_LANG} |
| marathi | {nm_lang.get('marathi', 0)} | {MAX_PER_LANG} |
| **Total normal** | **{len(nm_ok)}** | |

FLEURS utterances are everyday / news-style spoken sentences (ASR prompts). They are mapped to SafeHer **NORMAL** only. Emotional intensity is ignored. Transcripts matching emergency phrases were rejected.

## Totals by language (all labels)

| Language | EMERGENCY | NORMAL | Total |
|---|---:|---:|---:|
| english | {by_lang_label.get(('english','EMERGENCY'),0)} | {by_lang_label.get(('english','NORMAL'),0)} | {by_lang.get('english',0)} |
| hindi | {by_lang_label.get(('hindi','EMERGENCY'),0)} | {by_lang_label.get(('hindi','NORMAL'),0)} | {by_lang.get('hindi',0)} |
| marathi | {by_lang_label.get(('marathi','EMERGENCY'),0)} | {by_lang_label.get(('marathi','NORMAL'),0)} | {by_lang.get('marathi',0)} |
| **All** | **{by_label.get('EMERGENCY',0)}** | **{by_label.get('NORMAL',0)}** | **{len(all_ok)}** |

## Speakers

- Unique speaker IDs recorded: **{len(speakers)}**
- Note: FLEURS on Hugging Face does **not** expose `speaker_id` in this packaging; gender is stored when present. No train/val/test split was created (per brief). When speaker IDs become available, keep each speaker in one split only.

## Source datasets

| Source | Role | License | Clips used |
|---|---|---|---:|
| SafeHer emergency phrases | EMERGENCY | Internal | {len(em_ok)} |
| Google FLEURS (en_us/hi_in/mr_in) | NORMAL | CC-BY-4.0 | {len(nm_ok)} |

## Rejected files

| Category | Count |
|---|---:|
| Emergency copy failures | {len(em_fail)} |
| Normal (FLEURS) rejects | {len(nm_rej)} |
| **Total rejected rows** | **{len(em_fail)+len(nm_rej)}** |

Top reject reasons: {dict(Counter(r.get('reject_reason') or '(none)' for r in nm_rej).most_common(8))}

## Duration / format

- Total derived duration: **{total_dur/3600:.2f} hours** ({total_dur:.1f} s)
- Format: 16 kHz mono PCM16 WAV
- Augmentation: **none**
- Splits: **none**

## Warnings / errors

- Warnings ({len(log.warnings)}): {log.warnings[:20] if log.warnings else 'none'}
- Errors ({len(log.errors)}): {log.errors[:20] if log.errors else 'none'}

## Exact locations

- Dataset: `safeher_ai/data/derived/speech_v2_prep/`
- Metadata: `safeher_ai/data/derived/speech_v2_prep/metadata/speech_metadata.csv`
- License notes: `safeher_ai/data/derived/speech_v2_prep/metadata/LICENSE_SUMMARY.md`
- Log: `safeher_ai/data/training_logs/speech_v2_dataset_prep.log`
- This summary: `safeher_ai/data/training_logs/speech_v2_dataset_prep_summary.md`

## STOP

Speech dataset preparation complete. Waiting for further instructions before any Speech model training.
"""
        summary_path.write_text(summary, encoding="utf-8")
        (META / "prep_stats.json").write_text(json.dumps({
            "emergency": len(em_ok),
            "normal": len(nm_ok),
            "by_language": dict(by_lang),
            "by_label": dict(by_label),
            "by_source": dict(by_source),
            "rejected": len(em_fail) + len(nm_rej),
            "total_duration_s": total_dur,
            "unique_speakers_recorded": len(speakers),
            "max_per_lang": MAX_PER_LANG,
        }, indent=2), encoding="utf-8")

        log.log(f"Wrote {summary_path}")
        log.log(f"EMERGENCY={len(em_ok)} NORMAL={len(nm_ok)} rejected={len(em_fail)+len(nm_rej)}")
        log.log(f"Duration hours={total_dur/3600:.2f}")
        log.log("STATUS=SPEECH_V2_PREP_COMPLETE")
        print("===SPEECH_V2_PREP===")
        print(json.dumps({
            "emergency": len(em_ok),
            "normal": len(nm_ok),
            "by_language": dict(by_lang),
            "rejected": len(em_fail) + len(nm_rej),
            "hours": round(total_dur / 3600, 2),
            "out": str(OUT),
        }, indent=2))
    except Exception:
        log.error("FAILED")
        log.log(traceback.format_exc())
        log.log("STATUS=FAILED")
        raise
    finally:
        log.close()


if __name__ == "__main__":
    main()
