"""
SafeHer distress collection v2 - acquire additional genuine distress vocalizations.

Investigates candidate datasets against a strict legal/content filter, then downloads
ONLY the sources that pass. Every investigated source (accepted or rejected) is
recorded with its reason in metadata/source_registry.csv.

ACCEPTED SOURCE
  source_01_berst - BERSt (Rosie-Lab/BERSt on Hugging Face), CC-BY-4.0.
  4,523 smartphone recordings from 98 professional actors, 7 affects x
  shout/no-shout, 19 phone positions including obstructions and other rooms.
  Uniquely domain-matched: real phone microphones at realistic distances, which is
  what SafeHer actually runs on.

Everything is written to a NEW directory tree. No existing SafeHer data is touched,
nothing is merged into training, and no model is trained. `source_label` keeps the
ORIGINAL dataset label; `preliminary_category` is an advisory guess only.

Run:
  ..\\venv311\\Scripts\\python.exe training\\collect_distress_v2.py
  ..\\venv311\\Scripts\\python.exe training\\collect_distress_v2.py --report-only
"""

from __future__ import annotations

import csv
import io
import json
import sys
import time
import traceback
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "derived" / "distress_collection_v2"
META = OUT / "metadata"
LOGS = OUT / "logs"
S1 = OUT / "source_01_berst"
S1_AUDIO = S1 / "audio"
SHARDS = OUT / "_shards"

TRAIN_LOG = ROOT / "data" / "training_logs" / "distress_collection_v2.log"
SUMMARY_MD = ROOT / "data" / "training_logs" / "distress_collection_v2_summary.md"

REPO = "Rosie-Lab/BERSt"
TREE_API = f"https://huggingface.co/api/datasets/{REPO}/tree/main/data"
RESOLVE = f"https://huggingface.co/datasets/{REPO}/resolve/main/{{}}"

TARGET_SR = 16000
SRC_SR = 48000
CHUNK = 1 << 20
MAX_ATTEMPTS = 8
# Shards are kept until the whole run finishes so an interrupted run resumes
# instead of re-downloading a gigabyte.
STALL_GRACE_S = 90
STALL_MIN_BPS = 64 * 1024

# --report-only regenerates metadata/summary from the clips already downloaded.
REPORT_ONLY = "--report-only" in sys.argv


# ---------------------------------------------------------------------------
# Source registry: every dataset investigated, with the strict-filter verdict.
# Field order matches the reporting table the task asked for.
# ---------------------------------------------------------------------------
REGISTRY = [
    {
        "source_id": "source_01_berst",
        "dataset": "BERSt (B(asic) E(motion) R(andom phrase) S(hou)t(s))",
        "url": "https://huggingface.co/datasets/Rosie-Lab/BERSt",
        "access": "OPEN (direct download)",
        "license": "CC-BY-4.0",
        "commercial_use": "YES",
        "redistribution": "YES, with attribution",
        "acted_or_real": "ACTED (professional actors, but self-recorded at home)",
        "language": "English (regional + non-native accents)",
        "sample_rate": "48 kHz (resampled to 16 kHz mono)",
        "total_files": 4523,
        "speakers": 98,
        "relevant_classes": "affect=fear x shout_level=shout/no-shout",
        "useful_distress_est": "~640 fear clips (~280 shouted)",
        "labels_reliable": "YES - prompted affect + verified shout level, per-clip metadata",
        "verdict": "ACCEPTED",
        "reason": ("Only dataset found that is BOTH commercially licensed AND recorded "
                   "through real smartphone microphones at realistic distances/obstructions. "
                   "Directly addresses SafeHer's deployment domain gap."),
    },
    {
        "source_id": "-",
        "dataset": "VIVAE (Variably Intense Vocalizations of Affect and Emotion)",
        "url": "https://zenodo.org/records/4066235",
        "access": "OPEN",
        "license": "CC BY-NC 4.0",
        "commercial_use": "NO",
        "redistribution": "Non-commercial only",
        "acted_or_real": "ACTED (induced, authenticity-rated)",
        "language": "Non-verbal (language independent)",
        "sample_rate": "44.1 kHz",
        "total_files": 1085,
        "speakers": 11,
        "relevant_classes": "fear, pain (x4 intensity levels)",
        "useful_distress_est": "~360 fear+pain",
        "labels_reliable": "YES - perceptually validated",
        "verdict": "REJECTED",
        "reason": ("NonCommercial licence. Content is close to ideal (graded fear/pain "
                   "screams), so this is the single best candidate to license directly: "
                   "the authors invite requests at natalie.holz@ae.mpg.de."),
    },
    {
        "source_id": "-",
        "dataset": "ASVP-ESD (Emotional Sound Database)",
        "url": "https://zenodo.org/records/7132783",
        "access": "OPEN",
        "license": "CC-BY-4.0 (claimed)",
        "commercial_use": "UNSAFE",
        "redistribution": "UNSAFE",
        "acted_or_real": "MIXED - scraped media",
        "language": "Multiple / unrestricted",
        "sample_rate": "16 kHz",
        "total_files": 12625,
        "speakers": "unknown",
        "relevant_classes": "06 fearful/scream/panic (799), 11 pain/groan (706)",
        "useful_distress_est": "~1500 (nominally)",
        "labels_reliable": "PARTIAL - folder-level coding",
        "verdict": "REJECTED",
        "reason": ("Licence is not grantable. The dataset's own description says audio was "
                   "'collected from movies, tv shows, youtube channels and other websites'; "
                   "the uploader cannot place third-party copyrighted media under CC-BY. "
                   "Same movie-derived contamination we already found in AudioSet."),
    },
    {
        "source_id": "-",
        "dataset": "Nonspeech7k",
        "url": "https://zenodo.org/records/6967442",
        "access": "OPEN",
        "license": "CONFLICTING (Zenodo field says CC-BY-4.0; record text + paper say CC BY-NC-SA 4.0)",
        "commercial_use": "NO / UNCLEAR",
        "redistribution": "UNCLEAR",
        "acted_or_real": "MIXED (Freesound + YouTube + Aigei)",
        "language": "Non-verbal",
        "sample_rate": "32 kHz",
        "total_files": 7014,
        "speakers": "unknown",
        "relevant_classes": "scream, cry",
        "useful_distress_est": "~1000",
        "labels_reliable": "YES - manually annotated, single ground-truth label",
        "verdict": "REJECTED",
        "reason": ("Licence terms conflict with each other. Authors state explicitly "
                   "'only allowed for non-commercial and academic research purposes'. "
                   "Fails the 'terms must be clear' rule."),
    },
    {
        "source_id": "-",
        "dataset": "IUEC (IIITD Urban Environment Context)",
        "url": "https://www.iiitd.edu.in/~anils/taslp/taslp_distress_detection.html",
        "access": "RESTRICTED (request form + signed licence agreement)",
        "license": "Bespoke research agreement",
        "commercial_use": "NO (research evaluation only)",
        "redistribution": "NO",
        "acted_or_real": "MIXED - Internet, TV serials, movies, student actors",
        "language": "Mixed",
        "sample_rate": "44.1 kHz",
        "total_files": "~20 h context + 250 h volunteer",
        "speakers": "17 volunteers (no distress) + few actors",
        "relevant_classes": "scream, cry",
        "useful_distress_est": "340 two-second clips only",
        "labels_reliable": "YES for the labelled subset",
        "verdict": "REJECTED",
        "reason": ("Access gated behind a research licence agreement, and the distress "
                   "portion is only 340 two-second clips largely sourced from movies and "
                   "TV serials. Low value even if access were granted."),
    },
    {
        "source_id": "-",
        "dataset": "CEMO (real emergency call centre corpus)",
        "url": "https://catalogue.elra.info/ (LIMSI/CNRS)",
        "access": "NOT PUBLIC",
        "license": "Restricted research agreement",
        "commercial_use": "NO",
        "redistribution": "NO",
        "acted_or_real": "REAL",
        "language": "French",
        "sample_rate": "8 kHz telephony",
        "total_files": "n/a",
        "speakers": "n/a",
        "relevant_classes": "fear, stress in medical emergency calls",
        "useful_distress_est": "n/a",
        "labels_reliable": "YES",
        "verdict": "REJECTED",
        "reason": ("Not publicly obtainable. Contains identifiable real patients in "
                   "medical crisis; distribution is barred on privacy grounds."),
    },
    {
        "source_id": "-",
        "dataset": "911 Recordings (Kaggle, archival dispatch tapes)",
        "url": "https://www.kaggle.com/datasets/louisteitelbaum/911-recordings",
        "access": "Kaggle account required",
        "license": "CC0 (claimed by uploader)",
        "commercial_use": "UNSAFE",
        "redistribution": "UNSAFE",
        "acted_or_real": "REAL",
        "language": "English",
        "sample_rate": "8 kHz telephony",
        "total_files": 708,
        "speakers": "unknown",
        "relevant_classes": "real emergency calls",
        "useful_distress_est": "~700",
        "labels_reliable": "PARTIAL - hand-coded from descriptions",
        "verdict": "REJECTED",
        "reason": ("CC0 claim is not credible: an uploader cannot waive rights in third-party "
                   "recordings of identifiable people in crisis, and most jurisdictions treat "
                   "911 audio as confidential. Also acoustically wrong - 8 kHz telephony of a "
                   "caller talking to a dispatcher, not a scream into a phone mic."),
    },
    {
        "source_id": "-",
        "dataset": "PostDisasterDataset / Audio-SAR-Dataset",
        "url": "https://github.com/tuananhphamds/PostDisasterDataset",
        "access": "Google Drive link / Zenodo files RESTRICTED",
        "license": "NONE STATED (PostDisaster) / CC-BY-4.0 but files gated (SAR)",
        "commercial_use": "UNKNOWN",
        "redistribution": "UNKNOWN",
        "acted_or_real": "SYNTHETIC (30,000 clips AI-generated with AudioLDM)",
        "language": "Non-verbal",
        "sample_rate": "32 kHz",
        "total_files": "2500 reference + 30000 generated",
        "speakers": "n/a",
        "relevant_classes": "screaming, crying",
        "useful_distress_est": "0 usable",
        "labels_reliable": "N/A",
        "verdict": "REJECTED",
        "reason": ("No licence stated on the source dataset, and the bulk of it is "
                   "AI-generated audio rather than recordings of humans. The derived "
                   "SAR dataset's files are access-restricted."),
    },
    {
        "source_id": "-",
        "dataset": "SESA (Sound Events for Surveillance Applications)",
        "url": "https://zenodo.org/records/3519845",
        "access": "OPEN",
        "license": "CC-BY-4.0",
        "commercial_use": "YES",
        "redistribution": "YES",
        "acted_or_real": "REAL (from Freesound)",
        "language": "n/a",
        "sample_rate": "16 kHz",
        "total_files": 585,
        "speakers": "n/a",
        "relevant_classes": "casual, gunshot, explosion, siren",
        "useful_distress_est": "0",
        "labels_reliable": "YES",
        "verdict": "REJECTED",
        "reason": ("No human vocalization classes at all. Its classes (gunshot, explosion, "
                   "siren) are on the task's explicit exclusion list."),
    },
    {
        "source_id": "-",
        "dataset": "CREMA-D",
        "url": "https://github.com/CheyneyComputerScience/CREMA-D",
        "access": "OPEN (git-lfs, ~7.5 GB)",
        "license": "ODbL v1.0 + DbCL v1.0",
        "commercial_use": "YES",
        "redistribution": "YES, share-alike on derived databases",
        "acted_or_real": "ACTED (studio, scripted sentences)",
        "language": "English",
        "sample_rate": "16 kHz",
        "total_files": 7442,
        "speakers": 91,
        "relevant_classes": "Fear, Anger (x4 intensity levels)",
        "useful_distress_est": "~1240 fear, but conversational volume",
        "labels_reliable": "YES - crowd-sourced, 95% of clips have >7 ratings",
        "verdict": "REJECTED (for distress positives; retained as a future option)",
        "reason": ("Licence is fine and labels are excellent, but the content is scripted "
                   "sentences read at conversational volume in a studio - frightened speech, "
                   "not distress vocalization. Including it would be collecting on the word "
                   "'emotion' rather than on content. Worth revisiting later purely as a "
                   "91-speaker hard-negative pool of normal speech."),
    },
    {
        "source_id": "-",
        "dataset": "JVNV / JNV (Japanese nonverbal vocalization corpora)",
        "url": "https://sites.google.com/site/shinnosuketakamichi/research-topics/jvnv_corpus",
        "access": "OPEN",
        "license": "CC BY-SA 4.0",
        "commercial_use": "YES (share-alike)",
        "redistribution": "YES, share-alike",
        "acted_or_real": "ACTED",
        "language": "Japanese",
        "sample_rate": "48 kHz",
        "total_files": "~1600 (JVNV)",
        "speakers": 4,
        "relevant_classes": "fear, sadness NVs (scream, sobbing)",
        "useful_distress_est": "low hundreds",
        "labels_reliable": "YES",
        "verdict": "REJECTED",
        "reason": ("Only 4 speakers, so it adds almost no speaker diversity, and the "
                   "nonverbal bursts are embedded inside spoken sentences. ShareAlike also "
                   "raises unresolved questions for a commercial model."),
    },
    {
        "source_id": "-",
        "dataset": "ReCANVo",
        "url": "https://zenodo.org/records/5786860",
        "access": "OPEN",
        "license": "CC BY 3.0 US",
        "commercial_use": "YES",
        "redistribution": "YES",
        "acted_or_real": "REAL",
        "language": "Non-verbal",
        "sample_rate": "44.1 kHz",
        "total_files": 7077,
        "speakers": 8,
        "relevant_classes": "frustrated, dysregulated, delighted, request",
        "useful_distress_est": "0 for emergency distress",
        "labels_reliable": "YES - caregiver labelled in real time",
        "verdict": "REJECTED",
        "reason": ("Vocalizations of minimally-verbal individuals communicating in daily "
                   "life. Not emergency distress, and repurposing disability-related vocal "
                   "data for a threat detector raises ethical problems beyond the licence."),
    },
    {
        "source_id": "-",
        "dataset": "DroneAudioset",
        "url": "https://huggingface.co/datasets/ahlab-drone-project/DroneAudioSet",
        "access": "OPEN",
        "license": "MIT",
        "commercial_use": "YES",
        "redistribution": "YES",
        "acted_or_real": "RE-RECORDED (played through a speaker under drone noise)",
        "language": "Mixed",
        "sample_rate": "varies",
        "total_files": "~15 h",
        "speakers": "n/a",
        "relevant_classes": "human vocal (screams, cries) + drone ego-noise",
        "useful_distress_est": "0 clean",
        "labels_reliable": "YES",
        "verdict": "REJECTED",
        "reason": ("Every clip is dominated by drone ego-noise above 80 dBA, and the source "
                   "vocalizations were themselves taken from AudioSet/Freesound, which we "
                   "already hold. Wrong noise domain for a phone in a pocket."),
    },
]


def log_factory(fh):
    def log(msg: str):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        try:
            print(line, flush=True)
        except UnicodeEncodeError:
            print(line.encode("ascii", "replace").decode("ascii"), flush=True)
        fh.write(line + "\n")
        fh.flush()
    return log


def human(n: float) -> str:
    return f"{n / (1 << 20):.0f} MiB"


def list_shards(log) -> list[tuple[str, int]]:
    with urllib.request.urlopen(TREE_API, timeout=90) as r:
        tree = json.load(r)
    shards = sorted((e["path"], int(e["size"])) for e in tree
                    if e["path"].endswith(".parquet"))
    log(f"BERSt shards: {len(shards)}, total {sum(s for _, s in shards)/(1<<30):.2f} GiB")
    return shards


def download_shard(path: str, size: int, log) -> Path | None:
    dest = SHARDS / Path(path).name
    url = RESOLVE.format(path)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        have = dest.stat().st_size if dest.exists() else 0
        if have == size:
            return dest
        if have > size:
            dest.unlink()
            have = 0
        headers = {"User-Agent": "safeher-distress-v2/1.0"}
        mode = "wb"
        if have:
            headers["Range"] = f"bytes={have}-"
            mode = "ab"
            log(f"  resuming {dest.name} at {human(have)}/{human(size)}")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                if have and resp.status != 206:
                    dest.unlink(missing_ok=True)
                    continue
                t0 = time.time()
                got = 0
                with open(dest, mode) as out:
                    while True:
                        c = resp.read(CHUNK)
                        if not c:
                            break
                        out.write(c)
                        got += len(c)
                        # HF occasionally accepts the connection then trickles
                        # bytes forever; a read timeout never fires, so bail out
                        # on throughput instead and let the resume logic retry.
                        el = time.time() - t0
                        if el > STALL_GRACE_S and got / el < STALL_MIN_BPS:
                            raise TimeoutError(
                                f"stalled at {got/(1<<20):.1f} MiB "
                                f"({got/el/1024:.0f} KiB/s)")
        except Exception as e:
            log(f"  transfer error {dest.name}: {str(e)[:160]}")
            time.sleep(min(45, 4 * attempt))
            continue
        if dest.exists() and dest.stat().st_size == size:
            return dest
        time.sleep(min(45, 4 * attempt))
    return None


def categorise_berst(affect: str, shout: str) -> tuple[str, str]:
    """
    Preliminary, advisory category for a BERSt clip.
    Never overwrites the dataset's own label (kept as source_label).
    """
    a = (affect or "").strip().lower()
    s = (shout or "").strip().lower()
    if s not in ("shout", "no-shout"):
        return "AMBIGUOUS", f"prompted {a}, shout level not recorded ({s or 'blank'})"
    shouted = s == "shout"

    if a == "fear":
        if shouted:
            return "LIKELY_DISTRESS", "prompted fear, shouted through a phone mic"
        return "POSSIBLE_DISTRESS", "prompted fear at conversational volume"
    if a in ("sadness", "surprise") and shouted:
        # A startled yell and a sad cry both overlap acoustically with fear screams
        # but neither is reliably a call for help.
        return "AMBIGUOUS", f"prompted {a}, shouted - overlaps fear acoustically"
    if a == "anger" and shouted:
        return "HARD_NEGATIVE", ("angry shouting - loud but not a call for help "
                                 "(review: an attacker's shouting may co-occur with a "
                                 "real emergency)")
    if shouted:
        return "HARD_NEGATIVE", f"prompted {a}, shouted - loud voice that must not trigger SOS"
    return "HARD_NEGATIVE", f"prompted {a}, normal volume - ordinary speech"


def main():
    for d in (META, LOGS, S1_AUDIO, SHARDS):
        d.mkdir(parents=True, exist_ok=True)
    TRAIN_LOG.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if REPORT_ONLY else "w"
    fh = open(TRAIN_LOG, mode, encoding="utf-8")
    log = log_factory(fh)
    started = datetime.now()

    try:
        log("=" * 72)
        log("SafeHer distress collection v2 - acquisition + preliminary audit")
        log(f"Start: {started.isoformat()}")
        log(f"Destination: {OUT}")
        log("NO TRAINING. NO MERGE. Existing SafeHer data untouched.")

        acc = [r for r in REGISTRY if r["verdict"].startswith("ACCEPTED")]
        rej = [r for r in REGISTRY if not r["verdict"].startswith("ACCEPTED")]
        log(f"Datasets investigated: {len(REGISTRY)} | accepted: {len(acc)} | rejected: {len(rej)}")
        for r in REGISTRY:
            log(f"  [{r['verdict'].split()[0]:8}] {r['dataset']}  ({r['license']})")

        # ---------------------------------------------------------- registry csv
        reg_csv = META / "source_registry.csv"
        with open(reg_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(REGISTRY[0].keys()))
            w.writeheader()
            for r in REGISTRY:
                w.writerow(r)
        log(f"Wrote {reg_csv}")

        # ------------------------------------------------------- fetch BERSt
        rows = []
        failures = []
        seq = 0  # audio_id repeats across clips in BERSt, so it cannot name files

        if REPORT_ONLY:
            # Re-derive categories and regenerate reports from the clips already on
            # disk, so a categorisation change does not cost another 1 GiB download.
            meta_csv = META / "collection_metadata.csv"
            log(f"REPORT-ONLY: re-reading {meta_csv}")
            for r in csv.DictReader(open(meta_csv, encoding="utf-8")):
                affect = r["original_label"].split(";")[0].split("=", 1)[1]
                shout = r["original_label"].split("shout_level=", 1)[1]
                r["preliminary_category"], r["category_basis"] = \
                    categorise_berst(affect, shout)
                r["duration_s"] = float(r["duration_s"])
                r["sample_rate"] = int(r["sample_rate"])
                r["channels"] = int(r["channels"])
                rows.append(r)
            log(f"REPORT-ONLY: recategorised {len(rows)} clips")

        shards = [] if REPORT_ONLY else list_shards(log)
        for i, (path, size) in enumerate(shards, 1):
            log(f"[{i}/{len(shards)}] {path} ({human(size)})")
            p = download_shard(path, size, log)
            if p is None:
                log(f"  FAILED to download {path}")
                failures.append(path)
                continue
            split = Path(path).name.split("-")[0]

            pf = pq.ParquetFile(p)
            n = 0
            try:
                for batch in pf.iter_batches(batch_size=32):
                    for rec in batch.to_pylist():
                        aid = str(rec.get("audio_id") or "").strip()
                        try:
                            data, sr = sf.read(io.BytesIO(rec["audio"]["bytes"]),
                                               dtype="float32", always_2d=True)
                        except Exception as e:
                            failures.append((aid, f"decode: {str(e)[:100]}"))
                            continue

                        y = data.mean(axis=1)
                        if sr != TARGET_SR:
                            if sr % TARGET_SR == 0:
                                y = resample_poly(y, 1, sr // TARGET_SR)
                            else:
                                g = np.gcd(int(sr), TARGET_SR)
                                y = resample_poly(y, TARGET_SR // g, sr // g)
                        y = np.clip(y, -1.0, 1.0).astype(np.float32)
                        if y.size == 0:
                            failures.append((aid, "empty after resample"))
                            continue

                        seq += 1
                        fid = f"berst_{split}_{seq:05d}"
                        wav = S1_AUDIO / f"{fid}.wav"
                        sf.write(wav, y, TARGET_SR, subtype="PCM_16")

                        cat, why = categorise_berst(rec.get("affect"),
                                                    rec.get("shout_level"))
                        rows.append({
                            "source_dataset": "BERSt",
                            "source_id": "source_01_berst",
                            "original_file_id": aid,
                            "recording_group": aid,
                            "clip_id": fid,
                            "original_label": f"affect={rec.get('affect')};"
                                              f"shout_level={rec.get('shout_level')}",
                            "source_label": f"BERST_{rec.get('affect')}_"
                                            f"{rec.get('shout_level')}",
                            "speaker_id": rec.get("user_id", ""),
                            "gender": rec.get("gender", ""),
                            "age_band": rec.get("age", ""),
                            "language": rec.get("current_language", ""),
                            "first_language": rec.get("first_language", ""),
                            "acted_or_real": "ACTED",
                            "license": "CC-BY-4.0",
                            "attribution": "BERSt, Rosie-Lab (CC-BY-4.0)",
                            "source_url": f"https://huggingface.co/datasets/{REPO}",
                            "local_path": str(wav.relative_to(ROOT)).replace("\\", "/"),
                            "split": split,
                            "phone_model": rec.get("phone_model", ""),
                            "phone_position": rec.get("phone_position", ""),
                            "script": rec.get("script", ""),
                            "duration_s": round(len(y) / TARGET_SR, 3),
                            "sample_rate": TARGET_SR,
                            "channels": 1,
                            "download_status": "SUCCESS",
                            "preliminary_category": cat,
                            "category_basis": why,
                        })
                        n += 1
            finally:
                pf.close()

            log(f"  converted {n} clips (running total {len(rows)})")

        # ------------------------------------------------------------ metadata
        ids = [r["clip_id"] for r in rows]
        if len(set(ids)) != len(ids):
            raise RuntimeError(f"clip_id collision: {len(ids)} rows, {len(set(ids))} unique")
        on_disk = len(list(S1_AUDIO.glob("*.wav")))
        log(f"integrity: {len(rows)} rows, {len(set(ids))} unique ids, {on_disk} wav on disk")

        meta_csv = META / "collection_metadata.csv"
        with open(meta_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            for r in sorted(rows, key=lambda x: x["clip_id"]):
                w.writerow(r)
        log(f"Wrote {meta_csv} ({len(rows)} rows)")

        cats = Counter(r["preliminary_category"] for r in rows)
        affects = Counter(r["original_label"].split(";")[0].split("=")[1] for r in rows)
        shouts = Counter(r["original_label"].split("shout_level=")[1] for r in rows)
        genders = Counter(r["gender"] for r in rows)
        speakers = len({r["speaker_id"] for r in rows})
        total_dur = sum(r["duration_s"] for r in rows)

        log("PRELIMINARY CATEGORIES: " + json.dumps(dict(cats)))
        log(f"speakers={speakers} total_duration_h={total_dur/3600:.2f} failures={len(failures)}")

        # -------------------------------------------------- per-source licence
        (S1 / "LICENSE_SUMMARY.md").write_text(f"""# Licence summary - source_01_berst

**Dataset:** BERSt (B(asic) E(motion) R(andom phrase) S(hou)t(s))  
**Source:** https://huggingface.co/datasets/{REPO}  
**Paper:** https://arxiv.org/abs/2505.00059 (Comput. Speech Lang., 2025)  
**Licence:** Creative Commons Attribution 4.0 International (CC-BY-4.0)

## What this permits

- Commercial use: **yes**
- Redistribution and derivative works: **yes**
- Condition: **attribution required**

## Required attribution

> Contains material from the BERSt dataset (Rosie-Lab), used under CC-BY-4.0.
> https://huggingface.co/datasets/{REPO}

Attribution must be preserved anywhere SafeHer ships or publishes models or data
derived from these clips.

## Provenance and consent

Recordings come from 98 professional actors recruited through Backstage Casting who
recorded themselves in their own homes, knowingly, for dataset release. There is no
covert recording, no bystander audio, and no real-emergency material, so none of the
privacy problems attached to real 911 corpora apply here.

## What we did to it

Downsampled from 48 kHz to 16 kHz mono PCM16 to match the SafeHer audio pipeline.
No other processing. Original labels preserved verbatim in
`metadata/collection_metadata.csv` as `original_label`.
""", encoding="utf-8")

        # ------------------------------------------------------------- summary
        def table(c: Counter, header: str, total: int) -> str:
            lines = [f"| {header} | Count | % |", "|---|---:|---:|"]
            for k, v in c.most_common():
                lines.append(f"| {k} | {v} | {100.0*v/total:.1f}% |")
            return "\n".join(lines)

        reg_lines = ["| Dataset | Access | License | Commercial | Speakers | Total | Useful distress | Verdict |",
                     "|---|---|---|---|---|---|---|---|"]
        for r in REGISTRY:
            reg_lines.append(
                f"| {r['dataset'][:44]} | {r['access'][:22]} | {r['license'][:26]} | "
                f"{r['commercial_use']} | {r['speakers']} | {r['total_files']} | "
                f"{r['useful_distress_est']} | **{r['verdict'].split()[0]}** |")
        reg_table = "\n".join(reg_lines)

        rej_lines = "\n".join(
            f"- **{r['dataset']}** - {r['reason']}" for r in rej)

        ended = datetime.now()
        SUMMARY_MD.write_text(f"""# SafeHer distress collection v2

Run: {started.isoformat(timespec='seconds')} -> {ended.isoformat(timespec='seconds')}  
Destination: `data/derived/distress_collection_v2/`

**No model was trained. Nothing was merged into the SafeHer training dataset.
No existing audio, model, SOS, Android or backend code was modified.**

## Datasets investigated

{len(REGISTRY)} candidate sources were evaluated against the strict filter.
**{len(acc)} accepted, {len(rej)} rejected.**

{reg_table}

## Why the rejections

{rej_lines}

## What was collected

| Metric | Value |
|---|---:|
| Clips downloaded | **{len(rows)}** |
| Distinct speakers | **{speakers}** |
| Total duration | **{total_dur/3600:.2f} h** |
| Format | 16 kHz mono PCM16 |
| Failures | {len(failures)} |

### Preliminary categories

{table(cats, "Category", len(rows))}

These are **advisory** and derived from the dataset's own `affect` and `shout_level`
labels, not from listening. The original label is preserved in `source_label` and
`original_label`; nothing was relabelled DISTRESS.

### Source label distribution

{table(affects, "Prompted affect", len(rows))}

{table(shouts, "Shout level", len(rows))}

{table(genders, "Gender", len(rows))}

## The honest read

BERSt is **acted**, like everything else legally available. What makes it different
from AudioSet Screaming and FSD50K is the *channel*: every clip was recorded on a real
smartphone microphone in a real home, at 19 controlled positions including in a pocket,
in a bag, across the room, and behind a wall. That is SafeHer's actual deployment
condition, and no other commercially-licensed corpus we found covers it.

Its limits are equally clear. The phrases are deliberate nonsense ("snow meteor down
the chimney"), so there is no "help me" lexical content to learn. Fear is prompted
rather than experienced. And the distress-positive yield is smaller than the
1,500-3,000 target: roughly {cats.get('LIKELY_DISTRESS', 0)} likely and
{cats.get('POSSIBLE_DISTRESS', 0)} possible.

The larger finding from this search is that the target number is not reachable from
public data under a commercial licence. The datasets that contain genuinely
distress-like vocalizations are either NonCommercial (VIVAE), built from scraped
copyrighted media whose licence the uploader could not grant (ASVP-ESD, Nonspeech7k),
gated behind research agreements (IUEC, CEMO), or barred on privacy grounds (real 911
audio). The single highest-value follow-up is **licensing VIVAE directly** - its
graded fear and pain screams from 11 speakers are exactly the missing material, and
the authors invite commercial enquiries.

## Outputs

- `data/derived/distress_collection_v2/source_01_berst/audio/` - {len(rows)} WAV files
- `data/derived/distress_collection_v2/source_01_berst/LICENSE_SUMMARY.md`
- `data/derived/distress_collection_v2/metadata/collection_metadata.csv`
- `data/derived/distress_collection_v2/metadata/source_registry.csv`
- `data/training_logs/distress_collection_v2.log`
""", encoding="utf-8")
        log(f"Wrote {SUMMARY_MD}")

        for s in SHARDS.glob("*.parquet"):
            try:
                s.unlink()
            except OSError as e:
                log(f"  could not delete shard {s.name}: {e}")
        try:
            SHARDS.rmdir()
        except OSError:
            pass

        log("STATUS=COLLECTION_COMPLETE")
        print("===DISTRESS_V2===")
        print(json.dumps({
            "investigated": len(REGISTRY), "accepted": len(acc), "rejected": len(rej),
            "clips": len(rows), "speakers": speakers,
            "hours": round(total_dur / 3600, 2),
            "categories": dict(cats), "failures": len(failures),
        }, indent=2))
    except Exception:
        log("ERROR")
        log(traceback.format_exc())
        log("STATUS=FAILED")
        raise
    finally:
        fh.close()


if __name__ == "__main__":
    main()
