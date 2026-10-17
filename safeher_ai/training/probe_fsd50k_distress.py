"""
FSD50K probe: how many distress-adjacent clips exist, and under which licenses?

Downloads ONLY the small metadata files (~7 MB total), never the ~23 GiB audio.
Purpose: decide whether fetching FSD50K audio is worth it, and which clips are
license-clean for a COMMERCIAL product (CC0 / CC-BY only).

Downloads nothing else. Trains nothing. Touches no existing SafeHer data.

Run:
  ..\\venv311\\Scripts\\python.exe training\\probe_fsd50k_distress.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import time
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "derived" / "fsd50k_distress_probe"
DL = OUT / "downloads"
EX = OUT / "extracted"
REPORT_MD = ROOT / "data" / "training_logs" / "fsd50k_distress_probe.md"
REPORT_LOG = ROOT / "data" / "training_logs" / "fsd50k_distress_probe.log"
CANDIDATES_CSV = OUT / "candidate_clips.csv"

ZENODO = "https://zenodo.org/api/records/4060432/files/{}/content"
# size + md5 from the Zenodo record manifest, so a truncated transfer is caught
FILES = {
    "FSD50K.ground_truth.zip": (334701, "ca27382c195e37d2269c4c866dd73485"),
    "FSD50K.metadata.zip": (6700838, "b9ea0c829a411c1d42adb9da539ed237"),
}
MAX_DL_ATTEMPTS = 5

# FSD50K uses underscore-joined AudioSet names. Screaming-adjacent + distress-adjacent.
TARGET_CLASSES = [
    "Screaming",
    "Shout",
    "Yell",
    "Bellow",
    "Crying_and_sobbing",
    "Whimper",
    "Wail_and_moan",
    "Groan",
    "Gasp",
    "Battle_cry",
    "Children_shouting",
]

# Commercial-safe vs not. CC Sampling+ is a retired, ambiguous license -> quarantine.
COMMERCIAL_OK = {"CC0", "CC-BY"}


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


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verified(path: Path, size: int, md5: str) -> bool:
    return path.exists() and path.stat().st_size == size and md5_of(path) == md5


def fetch(name: str, log) -> Path:
    """Download with retries; Zenodo truncates transfers fairly often."""
    DL.mkdir(parents=True, exist_ok=True)
    dest = DL / name
    size, md5 = FILES[name]

    if verified(dest, size, md5):
        log(f"Already present and verified: {dest.name} ({size} bytes)")
        return dest

    url = ZENODO.format(name)
    last = None
    for attempt in range(1, MAX_DL_ATTEMPTS + 1):
        try:
            log(f"Downloading {name} (attempt {attempt}/{MAX_DL_ATTEMPTS})")
            req = urllib.request.Request(url, headers={"User-Agent": "safeher-fsd50k-probe/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as out:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    out.write(chunk)
            if verified(dest, size, md5):
                log(f"Verified {dest.name} ({dest.stat().st_size} bytes, md5 ok)")
                return dest
            got = dest.stat().st_size if dest.exists() else 0
            last = f"size/md5 mismatch (got {got}, expected {size})"
            log(f"  {last}")
        except Exception as e:
            last = str(e)
            log(f"  attempt failed: {last}")
        time.sleep(2 * attempt)

    raise RuntimeError(f"Could not download {name} after {MAX_DL_ATTEMPTS} attempts: {last}")


def unzip(path: Path, log) -> None:
    EX.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as z:
        z.extractall(EX)
    log(f"Extracted {path.name}")


def find(pattern: str) -> Path | None:
    hits = sorted(EX.rglob(pattern))
    return hits[0] if hits else None


def normalise_license(raw: str) -> str:
    """Map Freesound license URLs/strings to short codes."""
    s = (raw or "").lower()
    if "publicdomain" in s or "zero" in s or "/cc0/" in s:
        return "CC0"
    if "sampling+" in s or "sampling" in s:
        return "CC Sampling+"
    if "by-nc" in s or "noncommercial" in s:
        return "CC-BY-NC"
    if "by/" in s or "attribution" in s or s.endswith("/by/3.0/"):
        return "CC-BY"
    return f"UNKNOWN({raw[:60]})"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_LOG.parent.mkdir(parents=True, exist_ok=True)
    fh = open(REPORT_LOG, "w", encoding="utf-8")
    log = log_factory(fh)
    started = datetime.now()

    try:
        log("=" * 70)
        log("FSD50K distress probe - METADATA ONLY (no audio, ~7 MB)")
        log(f"Start: {started.isoformat()}")
        log(f"Destination: {OUT}")
        log("Commercial use assumed -> CC0/CC-BY only are usable.")

        for name in FILES:
            unzip(fetch(name, log), log)

        vocab_p = find("vocabulary.csv")
        dev_p = find("dev.csv")
        eval_p = find("eval.csv")
        dev_info_p = find("dev_clips_info_FSD50K.json")
        eval_info_p = find("eval_clips_info_FSD50K.json")
        log(f"vocabulary={vocab_p}")
        log(f"dev={dev_p} eval={eval_p}")
        log(f"dev_info={dev_info_p} eval_info={eval_info_p}")

        # vocabulary.csv: idx,display_name,mid  (no header)
        vocab = []
        with open(vocab_p, encoding="utf-8") as f:
            for row in csv.reader(f):
                if len(row) >= 3:
                    vocab.append((row[1].strip(), row[2].strip()))
        vocab_names = {n for n, _ in vocab}
        log(f"Vocabulary classes: {len(vocab)}")

        present = [c for c in TARGET_CLASSES if c in vocab_names]
        missing = [c for c in TARGET_CLASSES if c not in vocab_names]
        log(f"Target classes present in FSD50K: {present}")
        log(f"Target classes NOT in FSD50K: {missing}")
        # Surface near-misses so nothing relevant is silently skipped
        for m in missing:
            key = m.split("_")[0].lower()
            near = [n for n in sorted(vocab_names) if key in n.lower()]
            if near:
                log(f"  near-miss for {m}: {near}")

        # licenses per clip
        licenses: dict[str, str] = {}
        titles: dict[str, str] = {}
        uploaders: dict[str, str] = {}
        for p in [dev_info_p, eval_info_p]:
            with open(p, encoding="utf-8") as f:
                info = json.load(f)
            for fname, rec in info.items():
                licenses[str(fname)] = normalise_license(rec.get("license", ""))
                titles[str(fname)] = rec.get("title", "")
                uploaders[str(fname)] = rec.get("uploader", "")
        log(f"License records loaded: {len(licenses)}")
        log("Overall license mix: " + json.dumps(dict(Counter(licenses.values()))))

        # ground truth rows
        rows = []
        for p, split_default in [(dev_p, None), (eval_p, "eval")]:
            with open(p, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    labels = [x.strip() for x in (r.get("labels") or "").split(",") if x.strip()]
                    rows.append({
                        "fname": r["fname"].strip(),
                        "labels": labels,
                        "split": r.get("split", split_default) or split_default,
                        "set": "dev" if split_default is None else "eval",
                    })
        log(f"Ground-truth rows: {len(rows)}")

        # count per class x license
        per_class = defaultdict(lambda: Counter())
        candidates = []
        for r in rows:
            hit = [c for c in present if c in r["labels"]]
            if not hit:
                continue
            lic = licenses.get(r["fname"], "UNKNOWN")
            for c in hit:
                per_class[c][lic] += 1
            candidates.append({
                "fname": r["fname"],
                "freesound_url": f"https://freesound.org/s/{r['fname']}/",
                "matched_classes": "|".join(hit),
                "all_labels": "|".join(r["labels"]),
                "set": r["set"],
                "split": r["split"] or "",
                "license": lic,
                "commercial_ok": lic in COMMERCIAL_OK,
                "attribution_required": lic == "CC-BY",
                "title": titles.get(r["fname"], ""),
                "uploader": uploaders.get(r["fname"], ""),
            })

        uniq = {c["fname"]: c for c in candidates}
        ok = [c for c in uniq.values() if c["commercial_ok"]]
        not_ok = [c for c in uniq.values() if not c["commercial_ok"]]

        with open(CANDIDATES_CSV, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(next(iter(uniq.values())).keys()))
            w.writeheader()
            for c in sorted(uniq.values(), key=lambda x: (x["matched_classes"], x["fname"])):
                w.writerow(c)
        log(f"Wrote {CANDIDATES_CSV} ({len(uniq)} unique clips)")

        # tables
        all_lics = sorted({l for cnt in per_class.values() for l in cnt})
        head = "| Class | " + " | ".join(all_lics) + " | Total | Commercial-safe |"
        sep = "|---|" + "---:|" * (len(all_lics) + 2)
        lines = [head, sep]
        for c in present:
            cnt = per_class.get(c, Counter())
            tot = sum(cnt.values())
            safe = sum(v for k, v in cnt.items() if k in COMMERCIAL_OK)
            lines.append("| " + c + " | " + " | ".join(str(cnt.get(l, 0)) for l in all_lics)
                         + f" | {tot} | **{safe}** |")
        class_table = "\n".join(lines)

        log("Per-class counts: " + json.dumps({k: dict(v) for k, v in per_class.items()}))
        log(f"Unique candidate clips: {len(uniq)} | commercial-safe: {len(ok)} | excluded: {len(not_ok)}")

        est_mb = len(ok) * 0.9  # ~7.1s avg @ 44.1k mono 16-bit is ~0.6-1.2 MB
        ended = datetime.now()

        REPORT_MD.write_text(f"""# FSD50K distress probe (metadata only)

Run: {started.isoformat(timespec='seconds')} -> {ended.isoformat(timespec='seconds')}  
Downloaded: `FSD50K.ground_truth.zip` + `FSD50K.metadata.zip` only (~7 MB).  
**No audio downloaded. Nothing trained. No existing SafeHer data touched.**

Assumption: SafeHer may be **commercial**, so only **CC0** and **CC-BY** clips count as
usable. CC-BY-NC is excluded. CC Sampling+ is a retired/ambiguous license and is also
treated as not usable.

## Target classes

Present in the FSD50K 200-class vocabulary: {', '.join(present) if present else 'none'}  
Not in FSD50K: {', '.join(missing) if missing else 'none'}

## Clips per class by license

{class_table}

Counts are per class, so a clip labelled both `Screaming` and `Shout` is counted in both
rows. Unique clips are reported below.

## Bottom line

- Unique candidate clips (any license): **{len(uniq)}**
- **Commercial-safe (CC0 / CC-BY): {len(ok)}**
- Excluded (NC / Sampling+ / unknown): {len(not_ok)}
- Of the safe set, **{sum(1 for c in ok if c['attribution_required'])}** are CC-BY and
  require attribution; {sum(1 for c in ok if c['license'] == 'CC0')} are CC0 and do not.
- Rough download size if fetched individually from Freesound: **~{est_mb:.0f} MB**
  (versus ~23 GiB for the full FSD50K bulk zips).

Per-clip detail, including Freesound URLs and uploader names for attribution:
`{CANDIDATES_CSV}`

## Suggested next step

Fetch only the {len(ok)} commercial-safe clips individually via the Freesound API
(needs a free API key) rather than downloading 23 GiB. Then run the same acoustic +
content audit used for the AudioSet Screaming set.

Note: the FSD50K curators ask to be contacted for commercial use of the dataset
(efonseca@google.com, frederic.font@upf.edu). The per-clip CC licenses govern the audio
itself, but that request is on the Zenodo record.
""", encoding="utf-8")

        log(f"Wrote {REPORT_MD}")
        log("STATUS=PROBE_COMPLETE")
        print("===FSD50K_PROBE===")
        print(json.dumps({
            "classes_present": present,
            "classes_missing": missing,
            "unique_candidates": len(uniq),
            "commercial_safe": len(ok),
            "excluded": len(not_ok),
            "per_class": {k: dict(v) for k, v in per_class.items()},
        }, indent=2))
    except Exception:
        import traceback
        log("ERROR")
        log(traceback.format_exc())
        log("STATUS=FAILED")
        raise
    finally:
        fh.close()


if __name__ == "__main__":
    main()
