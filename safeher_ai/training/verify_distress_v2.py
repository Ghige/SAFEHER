"""
Integrity check for data/derived/distress_collection_v2.

Removes any WAV on disk that the metadata does not reference (orphans left by an
interrupted run), confirms every referenced clip opens and matches its recorded
duration/rate/channels, and prints the category breakdown.

Read-only with respect to everything outside distress_collection_v2.

Run:
  ..\\venv311\\Scripts\\python.exe training\\verify_distress_v2.py
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "derived" / "distress_collection_v2"
META_CSV = OUT / "metadata" / "collection_metadata.csv"
AUDIO = OUT / "source_01_berst" / "audio"


def main():
    rows = list(csv.DictReader(open(META_CSV, encoding="utf-8")))
    referenced = {r["clip_id"] + ".wav" for r in rows}
    on_disk = {p.name for p in AUDIO.glob("*.wav")}

    orphans = sorted(on_disk - referenced)
    missing = sorted(referenced - on_disk)

    print(f"metadata rows : {len(rows)}")
    print(f"wav on disk   : {len(on_disk)}")
    print(f"orphans       : {len(orphans)}")
    print(f"missing       : {len(missing)}")

    removed = 0
    for name in orphans:
        try:
            (AUDIO / name).unlink()
            removed += 1
        except OSError as e:
            print(f"  could not remove {name}: {e}")
    if removed:
        print(f"removed {removed} orphaned wav files")

    bad = []
    total_dur = 0.0
    for r in rows:
        p = AUDIO / (r["clip_id"] + ".wav")
        try:
            info = sf.info(p)
        except Exception as e:
            bad.append((r["clip_id"], f"unreadable: {str(e)[:80]}"))
            continue
        dur = info.frames / info.samplerate
        total_dur += dur
        if info.samplerate != 16000:
            bad.append((r["clip_id"], f"sr={info.samplerate}"))
        elif info.channels != 1:
            bad.append((r["clip_id"], f"channels={info.channels}"))
        elif abs(dur - float(r["duration_s"])) > 0.02:
            bad.append((r["clip_id"], f"duration {dur:.3f} vs {r['duration_s']}"))

    print(f"\nvalidated     : {len(rows) - len(bad)}/{len(rows)}")
    print(f"total duration: {total_dur/3600:.2f} h")
    for cid, why in bad[:20]:
        print(f"  BAD {cid}: {why}")

    print("\npreliminary categories")
    cats = Counter(r["preliminary_category"] for r in rows)
    for k, v in cats.most_common():
        print(f"  {k:<20} {v:>5}  ({100*v/len(rows):.1f}%)")

    print("\naffect x shout_level")
    cross = Counter((r["original_label"].split(";")[0].split("=")[1],
                     r["original_label"].split("shout_level=")[1]) for r in rows)
    for (a, s), v in sorted(cross.items()):
        print(f"  {a:<10} {s:<9} {v:>5}")

    print("\nspeakers:", len({r["speaker_id"] for r in rows}))
    print("gender  :", dict(Counter(r["gender"] for r in rows)))


if __name__ == "__main__":
    main()
