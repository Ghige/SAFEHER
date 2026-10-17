"""
Download the FSD50K audio archives (dev + eval) from Zenodo.

~23 GiB across 8 split-zip parts. Every part is size- and MD5-verified against the
Zenodo manifest, and interrupted transfers resume via HTTP Range (Zenodo truncates
often, so this matters).

Downloads archives ONLY. Extraction/conversion is a separate script.
Touches no existing SafeHer data. Trains nothing.

Run:
  ..\\venv311\\Scripts\\python.exe training\\download_fsd50k_audio.py
"""

from __future__ import annotations

import hashlib
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "derived" / "fsd50k_distress_probe"
ARCHIVES = OUT / "archives"
LOG = ROOT / "data" / "training_logs" / "fsd50k_audio_download.log"

ZENODO = "https://zenodo.org/api/records/4060432/files/{}/content"

# name -> (size_bytes, md5) straight from the Zenodo record manifest
PARTS: dict[str, tuple[int, str]] = {
    "FSD50K.eval_audio.z01": (3221225472, "3090670eaeecc013ca1ff84fe4442aeb"),
    "FSD50K.eval_audio.zip": (3037675767, "6fa47636c3a3ad5c7dfeba99f2637982"),
    "FSD50K.dev_audio.z01": (3221225472, "faa7cf4cc076fc34a44a479a5ed862a3"),
    "FSD50K.dev_audio.z02": (3221225472, "8f9b66153e68571164fb1315d00bc7bc"),
    "FSD50K.dev_audio.z03": (3221225472, "1196ef47d267a993d30fa98af54b7159"),
    "FSD50K.dev_audio.z04": (3221225472, "d088ac4e11ba53daf9f7574c11cccac9"),
    "FSD50K.dev_audio.z05": (3221225472, "81356521aa159accd3c35de22da28c7f"),
    "FSD50K.dev_audio.zip": (2306663327, "c480d119b8f7a7e32fdb58f3ea4d6c5a"),
}

MAX_ATTEMPTS = 8
CHUNK = 1 << 20


def log_line(fh, msg: str):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"), flush=True)
    fh.write(line + "\n")
    fh.flush()


def md5_of(path: Path, log=None) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK * 8), b""):
            h.update(block)
    return h.hexdigest()


def human(n: float) -> str:
    return f"{n / (1 << 30):.2f} GiB"


def download_part(name: str, size: int, md5: str, log) -> bool:
    dest = ARCHIVES / name
    url = ZENODO.format(name)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        have = dest.stat().st_size if dest.exists() else 0

        if have == size:
            log(f"{name}: size ok, verifying md5...")
            if md5_of(dest) == md5:
                log(f"{name}: VERIFIED ({human(size)})")
                return True
            log(f"{name}: md5 mismatch, restarting from scratch")
            dest.unlink()
            have = 0
        elif have > size:
            log(f"{name}: local file larger than expected, restarting")
            dest.unlink()
            have = 0

        headers = {"User-Agent": "safeher-fsd50k/1.0"}
        mode = "wb"
        if have > 0:
            headers["Range"] = f"bytes={have}-"
            mode = "ab"
            log(f"{name}: resuming at {human(have)} / {human(size)} (attempt {attempt})")
        else:
            log(f"{name}: starting download {human(size)} (attempt {attempt})")

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=180) as resp:
                # If the server ignored Range, start over rather than corrupt the file
                if have > 0 and resp.status != 206:
                    log(f"{name}: server ignored Range (status {resp.status}); restarting")
                    dest.unlink(missing_ok=True)
                    continue
                last_report = time.time()
                written = have
                with open(dest, mode) as out:
                    while True:
                        chunk = resp.read(CHUNK)
                        if not chunk:
                            break
                        out.write(chunk)
                        written += len(chunk)
                        if time.time() - last_report > 30:
                            pct = 100.0 * written / size
                            log(f"  {name}: {human(written)} / {human(size)} ({pct:.1f}%)")
                            last_report = time.time()
        except Exception as e:
            log(f"{name}: transfer error: {str(e)[:200]}")
            time.sleep(min(60, 5 * attempt))
            continue

        got = dest.stat().st_size if dest.exists() else 0
        if got != size:
            log(f"{name}: incomplete ({human(got)} of {human(size)}), will resume")
            time.sleep(min(60, 5 * attempt))
            continue

        log(f"{name}: download complete, verifying md5...")
        if md5_of(dest) == md5:
            log(f"{name}: VERIFIED ({human(size)})")
            return True
        log(f"{name}: md5 mismatch after full download; deleting and retrying")
        dest.unlink(missing_ok=True)
        time.sleep(min(60, 5 * attempt))

    return False


def main():
    ARCHIVES.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOG, "a", encoding="utf-8")
    log = lambda m: log_line(fh, m)

    total = sum(s for s, _ in PARTS.values())
    log("=" * 70)
    log("FSD50K audio archive download (dev + eval)")
    log(f"Start: {datetime.now().isoformat()}")
    log(f"Destination: {ARCHIVES}")
    log(f"Total to fetch: {human(total)} across {len(PARTS)} parts")

    ok, failed = [], []
    for name, (size, md5) in PARTS.items():
        if download_part(name, size, md5, log):
            ok.append(name)
        else:
            failed.append(name)
            log(f"GIVING UP on {name} after {MAX_ATTEMPTS} attempts")

    log(f"Verified parts: {len(ok)}/{len(PARTS)}")
    if failed:
        log(f"FAILED: {failed}")
        log("STATUS=DOWNLOAD_INCOMPLETE")
        fh.close()
        sys.exit(1)

    log("All parts verified.")
    log("STATUS=DOWNLOAD_COMPLETE")
    fh.close()


if __name__ == "__main__":
    main()
