"""
Fetch YouTube metadata (title/description/tags/categories) for downloaded
AudioSet SCREAMING clips, to support the content audit.

Metadata only — no audio/video is downloaded here.
Results are cached incrementally to metadata/youtube_metadata.jsonl (resumable).

This does NOT label anything and does NOT modify SafeHer datasets.

Run:
  ..\\venv311\\Scripts\\python.exe training\\fetch_audioset_screaming_titles.py
"""

from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "derived" / "audioset_screaming"
META_DIR = OUT / "metadata"
CACHE = META_DIR / "youtube_metadata.jsonl"
LOG = OUT / "logs" / "youtube_metadata_fetch.log"

MAX_DESC_CHARS = 1200


# Throttling / transient extractor failures worth a slower retry pass.
# "Video unavailable" is included because every ID here downloaded successfully
# during the audio pass, so it indicates rate limiting rather than a dead video.
TRANSIENT_PATTERNS = [
    "try again later",
    "sign in to confirm you're not a bot",
    "unable to download",
    "temporary",
    "timed out",
    "connection",
    "http error 5",
    "failed to extract",
    "player response",
    "page needs to be reloaded",
    "video unavailable",
    "content isn't available",
]
MAX_RETRY_PASSES = 2


def load_cache_records() -> dict[str, dict]:
    recs = {}
    if CACHE.exists():
        with open(CACHE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    recs[r["ytid"]] = r
                except Exception:
                    continue
    return recs


def write_cache(recs: dict[str, dict]) -> None:
    tmp = CACHE.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in recs.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(CACHE)


def is_transient(rec: dict) -> bool:
    if rec.get("status") == "OK":
        return False
    if int(rec.get("retry_count") or 0) >= MAX_RETRY_PASSES:
        return False
    err = (rec.get("error") or "").lower()
    return any(p in err for p in TRANSIENT_PATTERNS)


def successful_ytids() -> list[str]:
    meta = META_DIR / "screaming_metadata.csv"
    ids, order = set(), []
    with open(meta, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("downloaded_status") != "SUCCESS":
                continue
            y = row["ytid"]
            if y not in ids:
                ids.add(y)
                order.append(y)
    return order


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    logf = open(LOG, "a", encoding="utf-8")

    def log(msg: str):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    import yt_dlp

    retry_mode = "--retry-errors" in sys.argv
    ids = successful_ytids()
    cache = load_cache_records()

    if retry_mode:
        todo = [y for y in ids if y in cache and is_transient(cache[y])]
        pace = 2.0  # slow down hard; the previous pass tripped rate limiting
        log(f"RETRY MODE - transient failures to re-fetch: {len(todo)}")
    else:
        todo = [y for y in ids if y not in cache]
        pace = 0.2
        log(f"Unique successful video IDs: {len(ids)} | cached: {len(cache)} | to fetch: {len(todo)}")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "skip_download": True,
        "socket_timeout": 20,
        "retries": 1,
        "extractor_args": {"youtube": {"player_skip": ["configs"]}},
    }

    ok = err = 0
    results: dict[str, dict] = {}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for i, ytid in enumerate(todo, 1):
            rec = {"ytid": ytid, "fetched_at": datetime.now().isoformat(timespec="seconds")}
            try:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={ytid}", download=False)
                rec.update({
                    "status": "OK",
                    "title": info.get("title") or "",
                    "description": (info.get("description") or "")[:MAX_DESC_CHARS],
                    "categories": info.get("categories") or [],
                    "tags": (info.get("tags") or [])[:40],
                    "channel": info.get("channel") or info.get("uploader") or "",
                    "video_duration": info.get("duration"),
                    "language": info.get("language") or "",
                    "age_limit": info.get("age_limit"),
                })
                ok += 1
            except Exception as e:
                rec.update({"status": "ERROR", "error": str(e)[:300], "title": "", "description": "",
                            "categories": [], "tags": [], "channel": "",
                            "retry_count": int((cache.get(ytid) or {}).get("retry_count") or 0) + 1})
                err += 1
            results[ytid] = rec
            if i % 25 == 0:
                # Persist progress so the pass stays resumable
                cache.update(results)
                write_cache(cache)
                log(f"Progress {i}/{len(todo)} ok={ok} err={err}")
            time.sleep(pace)

    cache.update(results)
    write_cache(cache)
    total_ok = sum(1 for r in cache.values() if r.get("status") == "OK")
    log(f"DONE this pass: ok={ok} err={err} | cache total OK={total_ok}/{len(cache)}")
    log("STATUS=METADATA_FETCH_COMPLETE")


if __name__ == "__main__":
    main()
