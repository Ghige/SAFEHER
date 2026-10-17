"""
Download Google AudioSet SCREAMING clips (Balanced + Unbalanced train ONLY).

Destination: safeher_ai/data/derived/audioset_screaming/
Does NOT touch SafeHer raw/models/SOS. Does NOT train. Does NOT use Evaluation split.
source_label = SCREAMING (NOT DISTRESS).

Run:
  ..\\venv311\\Scripts\\python.exe training\\download_audioset_screaming.py
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "derived" / "audioset_screaming"
BAL_DIR = OUT / "balanced_train"
UNBAL_DIR = OUT / "unbalanced_train"
META_DIR = OUT / "metadata"
LOG_DIR_LOCAL = OUT / "logs"
BIN_DIR = OUT / "bin"
TRAIN_LOG = DATA / "training_logs"

# Official AudioSet CSVs
CSV_URLS = {
    "balanced_train": "http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/balanced_train_segments.csv",
    "unbalanced_train": "http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/unbalanced_train_segments.csv",
    "class_labels": "http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv",
}
SCREAMING_MID = "/m/03qc9zr"
SOURCE_LABEL = "SCREAMING"
TARGET_SR = 16000  # SafeHer pipeline sample rate
MAX_RETRIES = 1  # do not retry indefinitely


def _resolve_ffmpeg() -> str:
    """Ensure an ffmpeg.exe exists (yt-dlp looks for that exact name)."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    local = BIN_DIR / "ffmpeg.exe"
    if local.exists() and local.stat().st_size > 0:
        return str(local)
    try:
        import imageio_ffmpeg
        src = imageio_ffmpeg.get_ffmpeg_exe()
        shutil.copy2(src, local)
        return str(local)
    except Exception:
        return "ffmpeg"


FFMPEG = _resolve_ffmpeg()
# Make discoverable for yt-dlp download_ranges / any child tools
os.environ["PATH"] = str(BIN_DIR) + os.pathsep + os.environ.get("PATH", "")


def log_line(fh, msg: str):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", errors="replace").decode("ascii"))
    fh.write(line + "\n")
    fh.flush()


def download_file(url: str, dest: Path, logfh) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        log_line(logfh, f"Metadata already present: {dest}")
        return dest
    log_line(logfh, f"Downloading {url} -> {dest}")
    urllib.request.urlretrieve(url, dest)
    return dest


def parse_audioset_csv(path: Path, split_name: str):
    """Parse AudioSet segment CSV; skip # comment lines.

    Official AudioSet format uses ', ' separators:
      YTID, start_seconds, end_seconds, positive_labels
    with positive_labels quoted and comma-separated inside.
    """
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                ytid, start, end, labels = line.split(", ", 3)
            except ValueError:
                # Fallback for odd rows
                parts = next(csv.reader([line]))
                if len(parts) < 4:
                    continue
                ytid, start, end, labels = parts[0], parts[1], parts[2], ",".join(parts[3:])
            labels_clean = labels.strip().strip('"')
            label_set = {x.strip() for x in labels_clean.split(",")}
            if SCREAMING_MID not in label_set:
                continue
            rows.append({
                "ytid": ytid.strip(),
                "start_seconds": float(start),
                "end_seconds": float(end),
                "positive_labels": labels_clean,
                "source_split": split_name,
                "audioset_class": "Screaming",
                "audioset_mid": SCREAMING_MID,
                "source_label": SOURCE_LABEL,
            })
    return rows


def classify_error(msg: str) -> str:
    m = (msg or "").lower()
    unavailable_keys = [
        "private video", "video unavailable", "has been removed", "not available",
        "copyright", "blocked", "sign in", "confirm your age", "http error 404",
        "http error 410", "unavailable", "account associated with this video has been terminated",
        "this video is not available", "region", "who has blocked it",
    ]
    if any(k in m for k in unavailable_keys):
        return "UNAVAILABLE"
    return "FAILED"


def verify_wav(path: Path) -> dict:
    try:
        info = sf.info(str(path))
        data, sr = sf.read(str(path), always_2d=False)
        if getattr(data, "ndim", 1) > 1:
            data = np.mean(data, axis=1)
        dur = float(len(data) / sr) if sr else 0.0
        peak = float(np.max(np.abs(data))) if len(data) else 0.0
        ok = dur > 0.05 and peak > 1e-6 and info.frames > 0
        return {
            "ok": ok,
            "duration": dur,
            "sample_rate": int(sr),
            "channels": int(info.channels),
            "frames": int(info.frames),
            "error": None if ok else "empty_or_silent_or_too_short",
        }
    except Exception as e:
        return {"ok": False, "duration": None, "sample_rate": None, "channels": None, "frames": None, "error": str(e)}


def download_segment(ytid: str, start: float, end: float, out_wav: Path, logfh) -> tuple[str, str]:
    """
    Download YouTube segment to WAV @ 16 kHz mono.
    Returns (status, reason) where status in SUCCESS|FAILED|UNAVAILABLE
    """
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if out_wav.exists() and out_wav.stat().st_size > 1000:
        v = verify_wav(out_wav)
        if v["ok"]:
            return "SUCCESS", "already_present"
        try:
            out_wav.unlink()
        except Exception:
            pass

    url = f"https://www.youtube.com/watch?v={ytid}"
    tmp_dir = out_wav.parent / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{ytid}_{int(start * 10)}_{int(end * 10)}"
    tmp_tmpl = str(tmp_dir / f"{stem}.%(ext)s")
    ffmpeg_dir = str(BIN_DIR)

    try:
        import yt_dlp

        def ranges(info, ydl):
            return [{"start_time": float(start), "end_time": float(end)}]

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "format": "bestaudio/best",
            "outtmpl": tmp_tmpl,
            "download_ranges": ranges,
            "force_keyframes_at_cuts": True,
            "retries": MAX_RETRIES,
            "fragment_retries": MAX_RETRIES,
            "socket_timeout": 30,
            "ffmpeg_location": ffmpeg_dir,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        err = str(e)
        # If ranges path still can't find ffmpeg, fall back to full audio + cut
        if "ffmpeg is not installed" in err.lower() or "ffmpeg" in err.lower():
            try:
                import yt_dlp
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "noprogress": True,
                    "format": "bestaudio/best",
                    "outtmpl": tmp_tmpl,
                    "retries": MAX_RETRIES,
                    "fragment_retries": MAX_RETRIES,
                    "socket_timeout": 30,
                    "ffmpeg_location": ffmpeg_dir,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as e2:
                for c in tmp_dir.glob(f"{stem}.*"):
                    try:
                        c.unlink()
                    except Exception:
                        pass
                return classify_error(str(e2)), str(e2)[:500]
        else:
            for c in tmp_dir.glob(f"{stem}.*"):
                try:
                    c.unlink()
                except Exception:
                    pass
            return classify_error(err), err[:500]

    candidates = [c for c in tmp_dir.glob(f"{stem}.*") if c.suffix.lower() not in {".part", ".ytdl"}]
    if not candidates:
        return "FAILED", "no_temp_file_after_yt_dlp"

    src = max(candidates, key=lambda p: p.stat().st_mtime)
    duration = max(0.1, float(end) - float(start))
    # Always re-encode to SafeHer WAV format; if src is already a short segment,
    # -ss beyond length yields empty — so only seek when source is longer.
    cmd = [
        FFMPEG, "-y",
        "-i", str(src),
        "-ss", str(start),
        "-t", str(duration),
        "-ac", "1", "-ar", str(TARGET_SR),
        "-sample_fmt", "s16",
        str(out_wav),
    ]
    # If download_ranges already cut the segment, seeking to absolute start fails.
    # Detect short temp files and convert without re-seeking.
    try:
        probe = subprocess.run(
            [FFMPEG, "-i", str(src)], capture_output=True, text=True, timeout=30
        )
        # ffmpeg prints duration to stderr
        already_segment = False
        stderr = probe.stderr or ""
        # heuristic: if file is ~10s or less, treat as pre-cut segment
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
        if m:
            hh, mm, ss = int(m.group(1)), int(m.group(2)), float(m.group(3))
            src_dur = hh * 3600 + mm * 60 + ss
            if src_dur <= duration + 2.0:
                already_segment = True
        if already_segment:
            cmd = [
                FFMPEG, "-y", "-i", str(src),
                "-ac", "1", "-ar", str(TARGET_SR),
                "-sample_fmt", "s16",
                str(out_wav),
            ]
    except Exception:
        pass

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            # last-chance: convert whole temp without seek
            cmd2 = [
                FFMPEG, "-y", "-i", str(src),
                "-ac", "1", "-ar", str(TARGET_SR),
                "-sample_fmt", "s16",
                str(out_wav),
            ]
            proc2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=180)
            if proc2.returncode != 0:
                return "FAILED", f"ffmpeg_error: {(proc.stderr or '')[-400:]}"
    except Exception as e:
        return "FAILED", f"ffmpeg_exception: {e}"
    finally:
        for c in candidates:
            try:
                c.unlink()
            except Exception:
                pass

    v = verify_wav(out_wav)
    if not v["ok"]:
        try:
            out_wav.unlink()
        except Exception:
            pass
        return "FAILED", f"corrupt_wav: {v.get('error')}"
    return "SUCCESS", "ok"


def main():
    for d in [OUT, BAL_DIR, UNBAL_DIR, META_DIR, LOG_DIR_LOCAL, TRAIN_LOG]:
        d.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = TRAIN_LOG / "audioset_screaming_download.log"
    run_log = LOG_DIR_LOCAL / f"download_{ts}.log"
    fh = open(log_path, "w", encoding="utf-8")
    fh2 = open(run_log, "w", encoding="utf-8")

    def log(msg):
        log_line(fh, msg)
        log_line(fh2, msg)

    try:
        log("=" * 70)
        log("AudioSet SCREAMING download — Balanced+Unbalanced train ONLY")
        log("Evaluation split NOT used. source_label=SCREAMING (NOT DISTRESS).")
        log("Does NOT modify SafeHer raw/models/SOS. Does NOT train.")
        log(f"Start: {datetime.now().isoformat()}")
        log(f"Python: {sys.version}")
        log(f"Destination: {OUT}")
        log(f"FFMPEG: {FFMPEG}")
        log(f"Screaming MID: {SCREAMING_MID}")
        log("Source: https://research.google.com/audioset/dataset/screaming.html")

        # Fetch official metadata
        class_csv = download_file(CSV_URLS["class_labels"], META_DIR / "class_labels_indices.csv", fh)
        bal_csv = download_file(CSV_URLS["balanced_train"], META_DIR / "balanced_train_segments.csv", fh)
        unbal_csv = download_file(CSV_URLS["unbalanced_train"], META_DIR / "unbalanced_train_segments.csv", fh)

        # Verify MID maps to Screaming
        with open(class_csv, encoding="utf-8") as f:
            for line in f:
                if SCREAMING_MID in line:
                    log(f"Class map hit: {line.strip()}")
                    break

        bal_rows = parse_audioset_csv(bal_csv, "balanced_train")
        unbal_rows = parse_audioset_csv(unbal_csv, "unbalanced_train")
        all_rows = bal_rows + unbal_rows
        log(f"Expected page counts: balanced=59 unbalanced=1126 eval=61(NOT USED)")
        log(f"Filtered from CSV: balanced={len(bal_rows)} unbalanced={len(unbal_rows)} total={len(all_rows)}")

        meta_path = META_DIR / "screaming_metadata.csv"
        status_path = META_DIR / "download_status.csv"

        # Resume: load existing status
        done = {}
        if status_path.exists():
            with open(status_path, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    done[r.get("clip_id", "")] = r

        fieldnames = [
            "clip_id", "ytid", "start_seconds", "end_seconds", "audioset_class", "audioset_mid",
            "source_label", "source_split", "downloaded_status", "local_wav_path",
            "duration", "sample_rate", "channels", "download_error",
        ]
        status_fields = ["clip_id", "ytid", "source_split", "status", "reason", "local_wav_path", "timestamp"]

        # Open CSVs for incremental write
        meta_f = open(meta_path, "w", encoding="utf-8", newline="")
        status_f = open(status_path, "w", encoding="utf-8", newline="")
        meta_w = csv.DictWriter(meta_f, fieldnames=fieldnames)
        status_w = csv.DictWriter(status_f, fieldnames=status_fields)
        meta_w.writeheader()
        status_w.writeheader()

        counts = {"SUCCESS": 0, "FAILED": 0, "UNAVAILABLE": 0, "CORRUPTED": 0, "SKIPPED_EXISTING": 0}
        total_duration = 0.0

        for i, row in enumerate(all_rows, 1):
            ytid = row["ytid"]
            start = row["start_seconds"]
            end = row["end_seconds"]
            split = row["source_split"]
            clip_id = f"{ytid}_{start:.1f}_{end:.1f}"
            out_dir = BAL_DIR if split == "balanced_train" else UNBAL_DIR
            wav_name = f"{ytid}_{int(start*10):05d}_{int(end*10):05d}.wav"
            wav_path = out_dir / wav_name
            rel_wav = str(wav_path.relative_to(ROOT)).replace("\\", "/")

            # Resume success
            prev = done.get(clip_id)
            if prev and prev.get("status") == "SUCCESS" and wav_path.exists():
                v = verify_wav(wav_path)
                if v["ok"]:
                    counts["SUCCESS"] += 1
                    counts["SKIPPED_EXISTING"] += 1
                    total_duration += float(v["duration"] or 0)
                    meta_w.writerow({
                        "clip_id": clip_id, "ytid": ytid, "start_seconds": start, "end_seconds": end,
                        "audioset_class": "Screaming", "audioset_mid": SCREAMING_MID,
                        "source_label": SOURCE_LABEL, "source_split": split,
                        "downloaded_status": "SUCCESS", "local_wav_path": rel_wav,
                        "duration": v["duration"], "sample_rate": v["sample_rate"],
                        "channels": v["channels"], "download_error": "",
                    })
                    status_w.writerow({
                        "clip_id": clip_id, "ytid": ytid, "source_split": split,
                        "status": "SUCCESS", "reason": "resume_existing",
                        "local_wav_path": rel_wav, "timestamp": datetime.now().isoformat(timespec="seconds"),
                    })
                    if i % 25 == 0:
                        meta_f.flush(); status_f.flush()
                        log(f"Progress {i}/{len(all_rows)} SUCCESS={counts['SUCCESS']} FAIL={counts['FAILED']} UNAVAIL={counts['UNAVAILABLE']}")
                    continue
            if prev and prev.get("status") in {"FAILED", "UNAVAILABLE"}:
                prev_reason = (prev.get("reason") or "").lower()
                # Retry only prior infra mistakes (missing ffmpeg); never loop forever
                # on unavailable/private/deleted YouTube videos.
                retryable = "ffmpeg is not installed" in prev_reason
                if not retryable:
                    st = prev["status"]
                    counts[st] = counts.get(st, 0) + 1
                    meta_w.writerow({
                        "clip_id": clip_id, "ytid": ytid, "start_seconds": start, "end_seconds": end,
                        "audioset_class": "Screaming", "audioset_mid": SCREAMING_MID,
                        "source_label": SOURCE_LABEL, "source_split": split,
                        "downloaded_status": st, "local_wav_path": "",
                        "duration": "", "sample_rate": "", "channels": "",
                        "download_error": prev.get("reason", "cached_failure"),
                    })
                    status_w.writerow({
                        "clip_id": clip_id, "ytid": ytid, "source_split": split,
                        "status": st, "reason": prev.get("reason", "cached_failure"),
                        "local_wav_path": "", "timestamp": datetime.now().isoformat(timespec="seconds"),
                    })
                    continue

            status, reason = download_segment(ytid, start, end, wav_path, fh)
            if status == "SUCCESS":
                v = verify_wav(wav_path)
                if not v["ok"]:
                    status = "FAILED"
                    reason = f"corrupt_after_download: {v.get('error')}"
                    counts["CORRUPTED"] += 1
                    try:
                        wav_path.unlink()
                    except Exception:
                        pass
                else:
                    counts["SUCCESS"] += 1
                    total_duration += float(v["duration"] or 0)
                    meta_w.writerow({
                        "clip_id": clip_id, "ytid": ytid, "start_seconds": start, "end_seconds": end,
                        "audioset_class": "Screaming", "audioset_mid": SCREAMING_MID,
                        "source_label": SOURCE_LABEL, "source_split": split,
                        "downloaded_status": "SUCCESS", "local_wav_path": rel_wav,
                        "duration": v["duration"], "sample_rate": v["sample_rate"],
                        "channels": v["channels"], "download_error": "",
                    })
                    status_w.writerow({
                        "clip_id": clip_id, "ytid": ytid, "source_split": split,
                        "status": "SUCCESS", "reason": reason,
                        "local_wav_path": rel_wav, "timestamp": datetime.now().isoformat(timespec="seconds"),
                    })
            if status != "SUCCESS":
                counts[status] = counts.get(status, 0) + 1
                meta_w.writerow({
                    "clip_id": clip_id, "ytid": ytid, "start_seconds": start, "end_seconds": end,
                    "audioset_class": "Screaming", "audioset_mid": SCREAMING_MID,
                    "source_label": SOURCE_LABEL, "source_split": split,
                    "downloaded_status": status, "local_wav_path": "",
                    "duration": "", "sample_rate": "", "channels": "",
                    "download_error": reason,
                })
                status_w.writerow({
                    "clip_id": clip_id, "ytid": ytid, "source_split": split,
                    "status": status, "reason": reason,
                    "local_wav_path": "", "timestamp": datetime.now().isoformat(timespec="seconds"),
                })

            if i % 10 == 0 or status != "SUCCESS":
                meta_f.flush(); status_f.flush()
            if i % 25 == 0:
                log(f"Progress {i}/{len(all_rows)} SUCCESS={counts['SUCCESS']} FAIL={counts['FAILED']} UNAVAIL={counts['UNAVAILABLE']}")

            # gentle pacing to reduce blocks
            time.sleep(0.35)

        meta_f.close()
        status_f.close()

        # Count valid wavs on disk
        wavs = list(BAL_DIR.glob("*.wav")) + list(UNBAL_DIR.glob("*.wav"))
        valid = 0
        for w in wavs:
            if verify_wav(w)["ok"]:
                valid += 1
            else:
                counts["CORRUPTED"] += 1

        summary = {
            "source": "https://research.google.com/audioset/dataset/screaming.html",
            "mid": SCREAMING_MID,
            "source_label": SOURCE_LABEL,
            "expected": {"balanced_train": 59, "unbalanced_train": 1126, "evaluation": "NOT USED"},
            "csv_filtered": {"balanced_train": len(bal_rows), "unbalanced_train": len(unbal_rows)},
            "counts": counts,
            "valid_wav_on_disk": valid,
            "total_wav_files": len(wavs),
            "total_duration_sec": total_duration,
            "total_duration_hours": total_duration / 3600.0,
            "destination": str(OUT),
            "metadata": str(meta_path),
            "download_status": str(status_path),
            "not_labeled_as_distress": True,
            "not_added_to_safeher_training": True,
            "trained": False,
        }
        (META_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        md = TRAIN_LOG / "audioset_screaming_summary.md"
        md.write_text(
            f"""# AudioSet Screaming Download Summary

Source: https://research.google.com/audioset/dataset/screaming.html  
MID: `{SCREAMING_MID}`  
**source_label = SCREAMING** (NOT DISTRESS)  
Evaluation split: **NOT USED**  
No SafeHer raw/models modified. **No training.**

## Expected
- Balanced Train: 59
- Unbalanced Train: 1,126
- Evaluation: NOT USED

## CSV filtered
- Balanced: {len(bal_rows)}
- Unbalanced: {len(unbal_rows)}

## Actual
- Successfully downloaded: {counts['SUCCESS']}
- Failed: {counts['FAILED']}
- Unavailable: {counts['UNAVAILABLE']}
- Corrupted (logged): {counts['CORRUPTED']}
- Valid WAV on disk: {valid}
- Total WAV files: {len(wavs)}
- Total duration: {total_duration/3600:.3f} hours ({total_duration:.1f} sec)

## Paths
- Dataset: `{OUT}`
- Metadata: `{meta_path}`
- Download status: `{status_path}`
- Log: `{log_path}`

## Notes
- Unavailable/private/deleted YouTube videos are recorded, not treated as hard pipeline failure.
- Clips are **not** merged into SafeHer training datasets yet.
""",
            encoding="utf-8",
        )

        log(f"SUMMARY: {json.dumps(summary)}")
        log(f"End: {datetime.now().isoformat()}")
        log("STATUS=DOWNLOAD_COMPLETE")
        print("===AUDIOSET_SCREAMING_SUMMARY===")
        print(json.dumps(summary, indent=2))
    except Exception:
        log("ERROR")
        log(traceback.format_exc())
        log("STATUS=FAILED")
        raise
    finally:
        fh.close()
        fh2.close()


if __name__ == "__main__":
    main()
