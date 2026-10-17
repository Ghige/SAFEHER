"""
Local listening/review tool for SafeHer's derived distress datasets.

Serves a single-page app that plays each clip, shows its metadata and the
heuristic guess, and records a human verdict of
DISTRESS / HARD_NEGATIVE / REJECT / AMBIGUOUS.

This is the step the audits could not do: every `preliminary_category` in these
datasets is a metadata guess, and only listening settles it.

Two datasets are wired up:

  fsd50k  843 Freesound clips        -> data/derived/fsd50k_distress/
  berst   4,523 BERSt phone clips    -> data/derived/distress_collection_v2/

Verdicts are written to a SEPARATE file per dataset after every keystroke, so the
audit outputs are never modified: re-run an audit at any time and your verdicts
survive. Closing the browser or the server loses nothing.

Standard library only - no new dependencies.

Run:
  ..\\venv311\\Scripts\\python.exe training\\review_distress_clips.py --dataset berst
  ..\\venv311\\Scripts\\python.exe training\\review_distress_clips.py --dataset berst --all
  ..\\venv311\\Scripts\\python.exe training\\review_distress_clips.py --dataset fsd50k
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
UI_HTML = HERE / "review_ui.html"

VERDICTS = ["DISTRESS", "HARD_NEGATIVE", "REJECT", "AMBIGUOUS"]

_lock = threading.Lock()
_verdicts: dict[str, dict] = {}
_items: list[dict] = []
_ids: set[str] = set()
_cfg: dict = {}


def _num(v, nd):
    try:
        return round(float(v), nd)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Per-dataset adapters. Each build_* turns one CSV row into the generic item
# the UI renders, so the front end never needs to know which corpus it is on.
# ---------------------------------------------------------------------------

def build_fsd50k(r: dict) -> dict:
    return {
        "id": str(r["freesound_id"]),
        "title": r.get("title", ""),
        "subtitle": f"{r.get('license','')} · {r.get('set','')} set",
        "link": {"href": r.get("freesound_url", ""), "text": "Freesound page"},
        "category": r.get("content_category", ""),
        "category_note": f"{r.get('category_confidence','')} confidence · "
                         f"{r.get('predominance','')}",
        "evidence": r.get("category_evidence", ""),
        "predominance": r.get("predominance", ""),
        "duration": _num(r.get("duration"), 2),
        "lufs": _num(r.get("loudness_lufs"), 1),
        "rms_dbfs": _num(r.get("rms_dbfs"), 1),
        "clipping_pct": _num(r.get("clipping_pct"), 2),
        "silence_pct": _num(r.get("silence_pct"), 1),
        "facts": [
            ["FSD50K classes", (r.get("matched_classes") or "").replace("|", ", ")],
            ["All labels", (r.get("all_labels") or "").replace("|", ", ")],
            ["Uploader", r.get("uploader", "")],
        ],
        "chips_label": "Tags",
        "chips": [t for t in (r.get("tags") or "").split("|") if t][:22],
    }


def build_berst(r: dict) -> dict:
    label = r.get("original_label", "")
    affect = label.split(";")[0].split("=", 1)[-1]
    shout = label.split("shout_level=", 1)[-1]
    seq = (r.get("clip_id", "").rsplit("_", 1) + [""])[1].lstrip("0") or "0"
    # "Place phone in a bag ... 15/19" -> keep the wording, drop the index suffix.
    pos = re.sub(r"\s*\d+/19$", "", r.get("phone_position", ""))
    spk = r.get("speaker_id", "").replace("user_", "")[:8]
    return {
        "id": r["clip_id"],
        "title": f"#{seq}  {affect} · {shout}",
        "subtitle": f"speaker {spk} · {r.get('gender','')} · {r.get('age_band','')} · "
                    f"{r.get('split','')} split",
        "link": None,
        "category": r.get("preliminary_category", ""),
        "category_note": "from dataset labels only",
        "evidence": r.get("category_basis", ""),
        "predominance": "",
        "duration": _num(r.get("duration_s"), 2),
        "lufs": None, "rms_dbfs": None, "clipping_pct": None, "silence_pct": None,
        "facts": [
            ["Prompted affect", affect],
            ["Shout level", shout],
            ["Spoken phrase", r.get("script", "")],
            ["Phone position", pos],
            ["Phone model", r.get("phone_model", "")],
            ["Speaker", r.get("speaker_id", "")],
            ["First language", r.get("first_language", "")],
            ["Licence", r.get("license", "")],
        ],
        "chips_label": "",
        "chips": [],
    }


DATASETS = {
    "fsd50k": {
        "name": "FSD50K distress-adjacent",
        "dir": ROOT / "data" / "derived" / "fsd50k_distress",
        "audio": "audio",
        "items_csv": "metadata/quality_audit.csv",
        "queue_csv": "metadata/manual_review_list.csv",
        "queue_id": "freesound_id",
        "verdicts_csv": "metadata/manual_review_verdicts.csv",
        "verdict_id_col": "freesound_id",
        "verdict_extra": ["heuristic_category", "predominance", "title"],
        "build": build_fsd50k,
        "order": ["LIKELY_DISTRESS", "POSSIBLE_DISTRESS", "AMBIGUOUS",
                  "NON_DISTRESS_SCREAM", "MOVIE_OR_MEDIA", "MUSIC_RELATED",
                  "LOW_QUALITY"],
        "default_categories": None,   # queue comes from manual_review_list.csv
    },
    "berst": {
        "name": "BERSt distress candidates",
        "dir": ROOT / "data" / "derived" / "distress_collection_v2",
        "audio": "source_01_berst/audio",
        "items_csv": "metadata/collection_metadata.csv",
        "queue_csv": None,
        "queue_id": None,
        "verdicts_csv": "metadata/manual_review_verdicts.csv",
        "verdict_id_col": "clip_id",
        "verdict_extra": ["heuristic_category", "title"],
        "build": build_berst,
        "order": ["LIKELY_DISTRESS", "POSSIBLE_DISTRESS", "AMBIGUOUS",
                  "HARD_NEGATIVE", "REJECT"],
        # Default queue is the distress-positive candidates, not all 4,523 clips.
        "default_categories": ["LIKELY_DISTRESS", "POSSIBLE_DISTRESS"],
    },
}


def verdict_path() -> Path:
    return _cfg["dir"] / _cfg["verdicts_csv"]


def audio_dir() -> Path:
    return _cfg["dir"] / _cfg["audio"]


def verdict_fields() -> list[str]:
    return ([_cfg["verdict_id_col"], "verdict", "notes", "reviewed_at"]
            + _cfg["verdict_extra"])


def _sort_id(x: str):
    return (0, int(x)) if x.isdigit() else (1, x)


def load_verdicts() -> dict[str, dict]:
    p = verdict_path()
    if not p.exists():
        return {}
    idc = _cfg["verdict_id_col"]
    out = {}
    with open(p, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            # Tolerate a verdicts file written before the id column was renamed.
            key = r.get(idc) or r.get("freesound_id") or r.get("clip_id")
            if key:
                out[str(key)] = r
    return out


def save_verdicts() -> None:
    p = verdict_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".csv.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=verdict_fields(), extrasaction="ignore")
        w.writeheader()
        for k in sorted(_verdicts, key=_sort_id):
            w.writerow(_verdicts[k])
    tmp.replace(p)


def load_items(review_all: bool) -> list[dict]:
    items_csv = _cfg["dir"] / _cfg["items_csv"]
    if not items_csv.exists():
        raise SystemExit(f"No clips found. Expected {items_csv} to exist.")
    rows = list(csv.DictReader(open(items_csv, encoding="utf-8")))

    queued: dict[str, str] = {}
    qcsv = _cfg["queue_csv"] and (_cfg["dir"] / _cfg["queue_csv"])
    if qcsv and qcsv.exists():
        for r in csv.DictReader(open(qcsv, encoding="utf-8")):
            queued[str(r[_cfg["queue_id"]])] = r.get("review_reason", "")

    wanted = None if review_all else _cfg["default_categories"]

    items = []
    for r in rows:
        it = _cfg["build"](r)
        if not review_all:
            if queued and it["id"] not in queued:
                continue
            if wanted and it["category"] not in wanted:
                continue
        it["review_reason"] = queued.get(it["id"], "")
        it["queued"] = it["id"] in queued
        items.append(it)

    order = {c: i for i, c in enumerate(_cfg["order"])}
    items.sort(key=lambda x: (order.get(x["category"], 99),
                              x["predominance"] != "PREDOMINANT",
                              _sort_id(x["id"])))
    return items


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # keep the console readable

    def _send(self, code, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            return self._send(200, UI_HTML.read_bytes(), "text/html; charset=utf-8")

        if path == "/api/items":
            with _lock:
                payload = {"items": _items, "verdicts": _verdicts,
                           "options": VERDICTS, "dataset": _cfg["name"],
                           "categories": _cfg["order"]}
            return self._send(200, json.dumps(payload).encode("utf-8"),
                              "application/json")

        if path.startswith("/audio/") and path.endswith(".wav"):
            cid = path[len("/audio/"):-len(".wav")]
            # Only ids we actually loaded can be served - no path traversal.
            if cid not in _ids:
                return self._send(404, b"not found", "text/plain")
            p = audio_dir() / f"{cid}.wav"
            if not p.exists():
                return self._send(404, b"not found", "text/plain")
            return self._serve_audio(p)

        self._send(404, b"not found", "text/plain")

    def _serve_audio(self, p: Path):
        data = p.read_bytes()
        rng = self.headers.get("Range")
        # Chrome seeks with Range requests; without this, scrubbing misbehaves.
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                start = int(m.group(1) or 0)
                end = int(m.group(2)) if m.group(2) else len(data) - 1
                end = min(end, len(data) - 1)
                chunk = data[start:end + 1]
                self.send_response(206)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(len(chunk)))
                self.end_headers()
                self.wfile.write(chunk)
                return
        self._send(200, data, "audio/wav", {"Accept-Ranges": "bytes"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/verdict":
            return self._send(404, b"not found", "text/plain")

        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, b'{"ok":false}', "application/json")

        cid = str(body.get("clip_id", ""))
        verdict = body.get("verdict", "")
        if verdict and verdict not in VERDICTS:
            return self._send(400, b'{"ok":false}', "application/json")

        with _lock:
            item = next((i for i in _items if i["id"] == cid), None)
            if item is None:
                return self._send(404, b'{"ok":false}', "application/json")
            if not verdict and not (body.get("notes") or "").strip():
                _verdicts.pop(cid, None)
            else:
                rec = {
                    _cfg["verdict_id_col"]: cid,
                    "verdict": verdict,
                    "notes": (body.get("notes") or "").strip(),
                    "reviewed_at": datetime.now().isoformat(timespec="seconds"),
                    "heuristic_category": item["category"],
                    "predominance": item["predominance"],
                    "title": item["title"],
                }
                _verdicts[cid] = rec
            save_verdicts()
            done = len(_verdicts)

        return self._send(200, json.dumps({"ok": True, "done": done}).encode(),
                          "application/json")


class Server(ThreadingHTTPServer):
    # Windows lets SO_REUSEADDR bind a port another process is already listening
    # on: the bind succeeds, but the original owner keeps receiving connections
    # and this server silently serves nobody. Refuse the port instead.
    allow_reuse_address = False
    daemon_threads = True


def port_busy(p: int) -> bool:
    import socket
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", p)) == 0


def serve(port: int) -> tuple[Server, int]:
    for p in range(port, port + 12):
        if port_busy(p):
            continue
        try:
            return Server(("127.0.0.1", p), Handler), p
        except OSError:
            continue
    raise SystemExit(f"No free port in {port}..{port + 11}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=sorted(DATASETS), default="berst")
    ap.add_argument("--all", action="store_true",
                    help="review every clip instead of the distress candidates")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    global _items, _verdicts, _ids, _cfg
    _cfg = DATASETS[args.dataset]
    _items = load_items(review_all=args.all)
    _ids = {i["id"] for i in _items}
    _verdicts = load_verdicts()

    if not _items:
        raise SystemExit("No clips matched the review queue.")

    srv, port = serve(args.port)
    url = f"http://127.0.0.1:{port}"
    judged = sum(1 for v in _verdicts.values() if v.get("verdict"))
    print("=" * 64)
    print(f"SafeHer - {_cfg['name']} review")
    print(f"  clips to review : {len(_items)}"
          f"{'  (all clips)' if args.all else '  (distress candidates)'}")
    print(f"  already judged  : {judged}")
    print(f"  verdicts file   : {verdict_path()}")
    print(f"  open            : {url}")
    print("=" * 64)
    print("This tool never relabels the dataset; it only records your verdicts")
    print("to the file above. Ctrl+C to stop.", flush=True)

    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print(f"\nStopped. {len(_verdicts)} verdicts saved to {verdict_path()}")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
