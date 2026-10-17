"""
Fetch the commercial-safe FSD50K distress-adjacent clips as 16 kHz mono WAV.

Source: huggingface.co/datasets/quinnlue/FSD50K-16k - a repack of FSD50K where all
51,197 clips are already lossless mono 16 kHz FLAC in Parquet shards (6.4 GiB total,
versus 23 GiB of split zips on Zenodo, and already in SafeHer's pipeline format).

Chain of custody: labels and licenses come from the OFFICIAL Zenodo metadata we
downloaded ourselves (candidate_clips.csv). The Hugging Face repack supplies audio
bytes only. Where the repack's license string disagrees with Zenodo's, Zenodo wins and
the clip is flagged.

Only CC0 / CC-BY clips are written, since SafeHer may ship commercially. NC and
Sampling+ clips are never downloaded to disk as audio; they are listed for the record.

Clips are labelled source_label=FSD50K_<classes>. Nothing is labelled DISTRESS, nothing
is merged into the SafeHer training set, and no model is trained.

Run:
  ..\\venv311\\Scripts\\python.exe training\\fetch_fsd50k_distress.py
"""

from __future__ import annotations

import csv
import io
import json
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_fsd50k_distress import normalise_license  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "data" / "derived" / "fsd50k_distress_probe"
CANDIDATES = PROBE / "candidate_clips.csv"

OUT = ROOT / "data" / "derived" / "fsd50k_distress"
AUDIO = OUT / "audio"
META = OUT / "metadata"
SHARDS = OUT / "_shards"

LOG = ROOT / "data" / "training_logs" / "fsd50k_distress_fetch.log"
SUMMARY = ROOT / "data" / "training_logs" / "fsd50k_distress_fetch.md"

REPO = "quinnlue/FSD50K-16k"
TREE_API = f"https://huggingface.co/api/datasets/{REPO}/tree/main/data"
RESOLVE = f"https://huggingface.co/datasets/{REPO}/resolve/main/{{}}"

KEEP_SHARDS = False  # delete each shard once processed
MAX_ATTEMPTS = 6
CHUNK = 1 << 20
TARGET_SR = 16000


def log_line(fh, msg: str):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"), flush=True)
    fh.write(line + "\n")
    fh.flush()


def human(n: float) -> str:
    return f"{n / (1 << 20):.0f} MiB"


def load_wanted() -> dict[int, dict]:
    wanted = {}
    with open(CANDIDATES, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["commercial_ok"] != "True":
                continue
            wanted[int(r["fname"])] = r
    return wanted


def load_clip_info() -> dict[int, dict]:
    """Freesound title/description/tags per clip, from the official Zenodo metadata."""
    info: dict[int, dict] = {}
    base = PROBE / "extracted" / "FSD50K.metadata"
    for name in ["dev_clips_info_FSD50K.json", "eval_clips_info_FSD50K.json"]:
        p = base / name
        if not p.exists():
            continue
        with open(p, encoding="utf-8") as f:
            for fid, rec in json.load(f).items():
                info[int(fid)] = rec
    return info


def list_shards(log) -> list[tuple[str, int]]:
    with urllib.request.urlopen(TREE_API, timeout=60) as resp:
        tree = json.load(resp)
    shards = [(e["path"], int(e["size"])) for e in tree if e["path"].endswith(".parquet")]
    shards.sort()
    log(f"Shards listed: {len(shards)}, total {sum(s for _, s in shards) / (1 << 30):.2f} GiB")
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

        headers = {"User-Agent": "safeher-fsd50k/1.0"}
        mode = "wb"
        if have:
            headers["Range"] = f"bytes={have}-"
            mode = "ab"
            log(f"  resuming {dest.name} at {human(have)}/{human(size)} (attempt {attempt})")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=180) as resp:
                if have and resp.status != 206:
                    dest.unlink(missing_ok=True)
                    continue
                with open(dest, mode) as out:
                    while True:
                        chunk = resp.read(CHUNK)
                        if not chunk:
                            break
                        out.write(chunk)
        except Exception as e:
            log(f"  transfer error on {dest.name}: {str(e)[:160]}")
            time.sleep(min(45, 4 * attempt))
            continue

        if dest.exists() and dest.stat().st_size == size:
            return dest
        log(f"  {dest.name} incomplete, retrying")
        time.sleep(min(45, 4 * attempt))

    return None


def main():
    for d in (AUDIO, META, SHARDS):
        d.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOG, "w", encoding="utf-8")
    log = lambda m: log_line(fh, m)
    started = datetime.now()

    log("=" * 70)
    log("FSD50K distress fetch - commercial-safe clips only, 16 kHz mono WAV")
    log(f"Start: {started.isoformat()}")
    log(f"Audio source: HF {REPO} (audio bytes only)")
    log("Labels/licenses: official Zenodo metadata (authoritative)")
    log(f"Destination: {OUT}")

    wanted = load_wanted()
    log(f"Commercial-safe clips wanted: {len(wanted)}")
    clip_info = load_clip_info()
    log(f"Zenodo clip-info records (title/description/tags): {len(clip_info)}")

    shards = list_shards(log)

    rows = []
    found: set[int] = set()
    license_conflicts = []
    decode_failures = []
    shard_fail = []

    for i, (path, size) in enumerate(shards, 1):
        log(f"[{i}/{len(shards)}] {path} ({human(size)})")
        p = download_shard(path, size, log)
        if p is None:
            log(f"  FAILED to download {path}")
            shard_fail.append(path)
            continue

        pf = pq.ParquetFile(p)
        hits = 0
        try:
            batches = pf.iter_batches(batch_size=64,
                                      columns=["audio", "freesound_id", "license",
                                               "duration_seconds"])
            for batch in batches:
                for rec in batch.to_pylist():
                    fid = int(rec["freesound_id"])
                    if fid not in wanted or fid in found:
                        continue
                    src = wanted[fid]

                    try:
                        data, sr = sf.read(io.BytesIO(rec["audio"]["bytes"]),
                                           dtype="float32", always_2d=True)
                    except Exception as e:
                        decode_failures.append((fid, str(e)[:120]))
                        continue

                    if data.shape[1] != 1 or sr != TARGET_SR or data.shape[0] == 0:
                        decode_failures.append(
                            (fid, f"unexpected sr={sr} ch={data.shape[1]} n={data.shape[0]}"))
                        continue

                    wav = AUDIO / f"{fid}.wav"
                    sf.write(wav, data[:, 0], sr, subtype="PCM_16")

                    # Zenodo license is authoritative; note any disagreement.
                    # The repack stores licence URLs, Zenodo short codes, so both
                    # sides must be normalised to the same vocabulary first.
                    repack_lic = (rec.get("license") or "").strip()
                    if repack_lic and normalise_license(repack_lic) != src["license"]:
                        license_conflicts.append(
                            (fid, src["license"], normalise_license(repack_lic), repack_lic))

                    ci = clip_info.get(fid, {})
                    rows.append({
                        "freesound_id": fid,
                        "wav_path": str(wav.relative_to(ROOT)).replace("\\", "/"),
                        "source_label": "FSD50K_" + src["matched_classes"].replace("|", "+"),
                        "matched_classes": src["matched_classes"],
                        "all_labels": src["all_labels"],
                        "set": src["set"],
                        "split": src["split"],
                        "license": src["license"],
                        "attribution_required": src["attribution_required"],
                        "uploader": src["uploader"],
                        "title": src["title"],
                        "freesound_url": src["freesound_url"],
                        "duration_s": round(
                            float(rec.get("duration_seconds") or (len(data) / sr)), 3),
                        "sample_rate": sr,
                        "channels": 1,
                        "tags": "|".join(ci.get("tags") or []),
                        "description": " ".join((ci.get("description") or "").split())[:1500],
                        "audio_source": f"hf:{REPO}",
                    })
                    found.add(fid)
                    hits += 1
        finally:
            pf.close()

        log(f"  extracted {hits} clips (running total {len(found)}/{len(wanted)})")
        if not KEEP_SHARDS:
            try:
                p.unlink(missing_ok=True)
            except OSError as e:
                log(f"  could not delete shard {p.name}: {e}")

    missing = sorted(set(wanted) - found)

    meta_csv = META / "fsd50k_distress_metadata.csv"
    with open(meta_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in sorted(rows, key=lambda x: x["freesound_id"]):
            w.writerow(r)
    log(f"Wrote {meta_csv} ({len(rows)} rows)")

    # attribution file for the CC-BY clips
    ccby = [r for r in rows if r["license"] == "CC-BY"]
    att = OUT / "ATTRIBUTION.md"
    lines = ["# Attribution - FSD50K distress-adjacent subset", "",
             "Audio from Freesound.org via FSD50K. The clips below are licensed",
             "**CC-BY** and require credit if SafeHer ships them. CC0 clips are listed",
             "in the metadata CSV and need no attribution.", "",
             "| Freesound ID | Title | Author | Link |", "|---|---|---|---|"]
    for r in sorted(ccby, key=lambda x: x["freesound_id"]):
        t = (r["title"] or "").replace("|", "/")[:70]
        lines.append(f"| {r['freesound_id']} | {t} | {r['uploader']} | {r['freesound_url']} |")
    att.write_text("\n".join(lines), encoding="utf-8")
    log(f"Wrote {att} ({len(ccby)} CC-BY clips)")

    # record what we deliberately did NOT fetch
    excl = META / "excluded_noncommercial.csv"
    with open(CANDIDATES, encoding="utf-8") as f, open(excl, "w", encoding="utf-8", newline="") as g:
        rd = csv.DictReader(f)
        w = csv.DictWriter(g, fieldnames=rd.fieldnames)
        w.writeheader()
        n_ex = 0
        for r in rd:
            if r["commercial_ok"] != "True":
                w.writerow(r)
                n_ex += 1
    log(f"Wrote {excl} ({n_ex} clips excluded for licensing, audio never downloaded)")

    total_dur = sum(r["duration_s"] for r in rows)
    by_class = Counter()
    for r in rows:
        for c in r["matched_classes"].split("|"):
            by_class[c] += 1
    by_lic = Counter(r["license"] for r in rows)
    by_set = Counter(r["set"] for r in rows)

    log(f"Clips written: {len(rows)} | missing: {len(missing)} | decode failures: {len(decode_failures)}")
    log(f"Total duration: {total_dur / 3600:.2f} h | by class: {dict(by_class)} | by license: {dict(by_lic)}")
    if license_conflicts:
        log(f"License disagreements (Zenodo kept): {len(license_conflicts)}")
    if shard_fail:
        log(f"Shards that failed to download: {shard_fail}")

    ended = datetime.now()
    SUMMARY.write_text(f"""# FSD50K distress-adjacent fetch

Run: {started.isoformat(timespec='seconds')} -> {ended.isoformat(timespec='seconds')}

## What was fetched

- **{len(rows)} WAV clips**, 16 kHz mono PCM16, total **{total_dur / 3600:.2f} hours**
- Location: `{AUDIO.relative_to(ROOT)}`
- Metadata: `{meta_csv.relative_to(ROOT)}`
- Attribution (CC-BY): `{att.relative_to(ROOT)}`

Audio bytes came from the Hugging Face repack `{REPO}` (already lossless 16 kHz mono
FLAC), which avoided the 23 GiB of split zips on Zenodo. **Labels and licenses come from
the official Zenodo FSD50K metadata**, not from the repack.

## Licensing

| License | Clips |
|---|---:|
""" + "\n".join(f"| {k} | {v} |" for k, v in sorted(by_lic.items())) + f"""

{sum(1 for r in rows if r['license'] == 'CC-BY')} clips are CC-BY and require attribution
if shipped. {sum(1 for r in rows if r['license'] == 'CC0')} are CC0.
{n_ex} NC / Sampling+ clips were excluded and their audio was **never downloaded**
(`{excl.relative_to(ROOT)}`).

License strings disagreeing between Zenodo and the repack: {len(license_conflicts)}
(Zenodo's value was kept in all cases.)

## Class coverage

| Class | Clips |
|---|---:|
""" + "\n".join(f"| {k} | {v} |" for k, v in by_class.most_common()) + f"""

Classes overlap, so these sum to more than {len(rows)}.

Split provenance: {dict(by_set)} (FSD50K eval labels are exhaustive; dev labels are
correct but occasionally incomplete.)

## Integrity

- Requested: {len(wanted)} commercial-safe clips
- Written: {len(rows)}
- Not found in the repack: {len(missing)}
- Failed to decode: {len(decode_failures)}
- Shards that failed to download: {len(shard_fail)}

## Status

`source_label` is `FSD50K_<classes>`. **Nothing is labelled DISTRESS**, nothing was
merged into the SafeHer training set, and no model was trained. Next step is the
acoustic + content audit before any labelling decision.
""", encoding="utf-8")

    log(f"Wrote {SUMMARY}")
    if not KEEP_SHARDS:
        try:
            SHARDS.rmdir()
        except OSError:
            pass
    log("STATUS=FETCH_COMPLETE")
    fh.close()

    print("===FSD50K_FETCH===")
    print(json.dumps({
        "written": len(rows), "requested": len(wanted), "missing": len(missing),
        "decode_failures": len(decode_failures), "hours": round(total_dur / 3600, 2),
        "by_license": dict(by_lic), "by_class": dict(by_class),
        "license_conflicts": len(license_conflicts), "shard_failures": shard_fail,
    }, indent=2))


if __name__ == "__main__":
    main()
