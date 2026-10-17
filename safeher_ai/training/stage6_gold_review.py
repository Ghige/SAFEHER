"""
Stage 6 gold-label review — dual independent listeners.

Reads the existing 7,883-row listening queue (P0 first by default).
Writes ONLY to data/training_logs/stage6_gold/ — never touches:
  - existing model weights
  - raw/derived audio
  - legacy manual_review_verdicts.csv
  - heuristic / folder labels

Confirmed DISTRESS requires TWO different reviewer_ids both choosing DISTRESS
AND license_status in {SAFE, ATTRIBUTION_REQUIRED}.

Heuristic labels are never auto-promoted.

Run:
  python training/stage6_gold_review.py
  python training/stage6_gold_review.py --priority P0 --reviewer alice
  python training/stage6_gold_review.py --progress-only
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
QUEUE_CSV = DATA / "training_logs" / "stage6_listening_review_queue.csv"
GOLD_DIR = DATA / "training_logs" / "stage6_gold"
REVIEWS_CSV = GOLD_DIR / "reviews.csv"
CONFIRMED_DISTRESS_CSV = GOLD_DIR / "confirmed_distress.csv"
VERIFIED_HN_CSV = GOLD_DIR / "verified_hard_negative.csv"
PROGRESS_JSON = GOLD_DIR / "progress.json"
UI_HTML = Path(__file__).resolve().parent / "stage6_gold_ui.html"

VERDICTS = ["DISTRESS", "HARD_NEGATIVE", "REJECT", "AMBIGUOUS"]
LICENSE_OK = {"SAFE", "ATTRIBUTION_REQUIRED"}
TARGET_DISTRESS = 500
TARGET_HN_ADDITIONAL = 999  # toward 1000 total; 1 legacy already exists
LEGACY_HN = 1  # berst_train_00772 in stage6_existing_gold_labels.csv

REVIEW_FIELDS = [
    "queue_id",
    "source_id",
    "manual_verdict",
    "reviewer_id",
    "review_timestamp",
    "license_status",
    "rel_path",
    "priority",
    "notes",
]

CONFIRM_FIELDS = [
    "queue_id",
    "source_id",
    "manual_verdict",
    "license_status",
    "reviewer_a",
    "reviewer_b",
    "review_timestamp_a",
    "review_timestamp_b",
    "confirmed_at",
]

HN_FIELDS = [
    "queue_id",
    "source_id",
    "manual_verdict",
    "license_status",
    "reviewer_id",
    "review_timestamp",
    "dual_agree",
    "notes",
]

_lock = threading.Lock()
_items: list[dict] = []
_path_by_qid: dict[str, Path] = {}
_reviews: list[dict] = []  # all review rows
_reviewer_default = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_audio(rel_path: str) -> Path | None:
    """Resolve queue rel_path; tolerate accidental 'data/' prefix."""
    rel = rel_path.replace("\\", "/")
    candidates = [
        DATA / rel,
        DATA / rel.removeprefix("data/"),
        ROOT / rel,
        ROOT / rel.removeprefix("data/"),
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def source_id_for(row: dict) -> str:
    """Stable source id for manifests (not a gold label)."""
    name = Path(row["filename"]).stem
    bucket = row.get("source_bucket", "")
    if "BERSt" in bucket or "berst" in bucket.lower():
        return name  # berst_* clip ids
    if "fsd50k" in bucket:
        return f"fsd_{name}"
    if "emergency_phrases" in bucket:
        return f"em_{name}"
    if "Screaming" in bucket:
        return f"yt_scream_{name}"
    return f"{bucket.replace('/', '_')}_{name}"


def load_queue(priority: str | None) -> list[dict]:
    if not QUEUE_CSV.exists():
        raise SystemExit(f"Missing queue: {QUEUE_CSV}")
    rows = list(csv.DictReader(QUEUE_CSV.open(encoding="utf-8")))
    if priority:
        rows = [r for r in rows if r.get("priority") == priority]
    # P0..P3 order already in file; keep stable
    items = []
    for r in rows:
        audio = resolve_audio(r["rel_path"])
        resolved = ""
        if audio:
            try:
                resolved = str(audio.relative_to(DATA)).replace("\\", "/")
            except ValueError:
                resolved = str(audio)
        items.append({
            "queue_id": r["queue_id"],
            "source_id": source_id_for(r),
            "rel_path": r["rel_path"],
            "resolved_path": resolved,
            "filename": r["filename"],
            "source_bucket": r["source_bucket"],
            "heuristic_label": r["heuristic_label"],
            "label_status": r["label_status"],
            "license_status": r["license_tier_pre"],
            "priority": r["priority"],
            "review_hint": r.get("review_hint", ""),
            "audio_available": bool(audio),
            "do_not_auto_promote": r.get("do_not_auto_promote", "YES"),
        })
        if audio:
            _path_by_qid[r["queue_id"]] = audio
    return items


def load_reviews() -> list[dict]:
    if not REVIEWS_CSV.exists():
        return []
    with REVIEWS_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    tmp.replace(path)


def recompute_confirmed(reviews: list[dict]) -> tuple[list[dict], list[dict]]:
    """Build confirmed DISTRESS (dual agree + license OK) and verified HN lists."""
    by_qid: dict[str, list[dict]] = {}
    for r in reviews:
        if not r.get("manual_verdict"):
            continue
        by_qid.setdefault(r["queue_id"], []).append(r)

    confirmed: list[dict] = []
    verified_hn: list[dict] = []

    for qid, rs in by_qid.items():
        # latest verdict per reviewer
        latest: dict[str, dict] = {}
        for r in sorted(rs, key=lambda x: x.get("review_timestamp", "")):
            rid = (r.get("reviewer_id") or "").strip()
            if rid:
                latest[rid] = r

        distress_reviewers = [
            r for r in latest.values() if r.get("manual_verdict") == "DISTRESS"
        ]
        if len(distress_reviewers) >= 2:
            a, b = distress_reviewers[0], distress_reviewers[1]
            lic = a.get("license_status") or b.get("license_status") or ""
            if lic in LICENSE_OK and a["reviewer_id"] != b["reviewer_id"]:
                confirmed.append({
                    "queue_id": qid,
                    "source_id": a.get("source_id", ""),
                    "manual_verdict": "DISTRESS",
                    "license_status": lic,
                    "reviewer_a": a["reviewer_id"],
                    "reviewer_b": b["reviewer_id"],
                    "review_timestamp_a": a.get("review_timestamp", ""),
                    "review_timestamp_b": b.get("review_timestamp", ""),
                    "confirmed_at": utc_now(),
                })

        hn_reviewers = [
            r for r in latest.values() if r.get("manual_verdict") == "HARD_NEGATIVE"
        ]
        if hn_reviewers:
            # Verified HN = at least one human HARD_NEGATIVE (not heuristic).
            # dual_agree when two independent reviewers agree.
            primary = hn_reviewers[0]
            dual = len(hn_reviewers) >= 2
            verified_hn.append({
                "queue_id": qid,
                "source_id": primary.get("source_id", ""),
                "manual_verdict": "HARD_NEGATIVE",
                "license_status": primary.get("license_status", ""),
                "reviewer_id": primary.get("reviewer_id", ""),
                "review_timestamp": primary.get("review_timestamp", ""),
                "dual_agree": "YES" if dual else "NO",
                "notes": primary.get("notes", ""),
            })

    confirmed.sort(key=lambda r: r["queue_id"])
    verified_hn.sort(key=lambda r: r["queue_id"])
    return confirmed, verified_hn


def progress_payload(reviews: list[dict] | None = None) -> dict:
    reviews = reviews if reviews is not None else load_reviews()
    confirmed, verified_hn = recompute_confirmed(reviews)
    # license-OK HN preferred for prod, but count all human HN toward verified
    hn_license_ok = sum(1 for r in verified_hn if r.get("license_status") in LICENSE_OK)
    distress_n = len(confirmed)
    hn_n = len(verified_hn)
    # additional toward 999 = new verified HN (legacy separate)
    additional_hn = hn_n  # new store; legacy 1 counted separately
    remaining_distress = max(0, TARGET_DISTRESS - distress_n)
    remaining_hn_additional = max(0, TARGET_HN_ADDITIONAL - additional_hn)

    by_verdict: dict[str, int] = {}
    latest_pairs: dict[tuple[str, str], str] = {}
    for r in sorted(reviews, key=lambda x: x.get("review_timestamp", "")):
        key = (r.get("queue_id", ""), r.get("reviewer_id", ""))
        if key[0] and key[1]:
            latest_pairs[key] = r.get("manual_verdict", "")
    for v in latest_pairs.values():
        by_verdict[v] = by_verdict.get(v, 0) + 1

    dual_pending = 0
    by_qid: dict[str, set[str]] = {}
    for (qid, rid), ver in latest_pairs.items():
        if ver == "DISTRESS":
            by_qid.setdefault(qid, set()).add(rid)
    for qid, rids in by_qid.items():
        if len(rids) == 1:
            # check license of that review
            dual_pending += 1

    payload = {
        "generated_at": utc_now(),
        "policy": {
            "no_auto_promote": True,
            "confirmed_distress_requires_dual_review": True,
            "confirmed_distress_requires_license_ok": True,
            "license_ok": sorted(LICENSE_OK),
            "verdicts": VERDICTS,
        },
        "targets": {
            "confirmed_DISTRESS": TARGET_DISTRESS,
            "additional_verified_HARD_NEGATIVE": TARGET_HN_ADDITIONAL,
            "legacy_HARD_NEGATIVE_outside_store": LEGACY_HN,
        },
        "counts": {
            "review_rows": len(reviews),
            "unique_reviewer_clip_pairs": len(latest_pairs),
            "verdicts_by_latest_pair": by_verdict,
            "confirmed_DISTRESS": distress_n,
            "verified_HARD_NEGATIVE_stage6": hn_n,
            "verified_HARD_NEGATIVE_license_ok": hn_license_ok,
            "legacy_HARD_NEGATIVE": LEGACY_HN,
            "total_HARD_NEGATIVE_incl_legacy": hn_n + LEGACY_HN,
            "distress_awaiting_second_reviewer": dual_pending,
            "remaining_confirmed_DISTRESS": remaining_distress,
            "remaining_additional_HARD_NEGATIVE": remaining_hn_additional,
        },
        "production_ready": False,
        "gates": {
            "G_distress": distress_n >= TARGET_DISTRESS,
            "G_hard_negative_additional": additional_hn >= TARGET_HN_ADDITIONAL,
        },
    }
    return payload


def persist_all(reviews: list[dict]) -> dict:
    confirmed, verified_hn = recompute_confirmed(reviews)
    write_csv(REVIEWS_CSV, REVIEW_FIELDS, reviews)
    write_csv(CONFIRMED_DISTRESS_CSV, CONFIRM_FIELDS, confirmed)
    write_csv(VERIFIED_HN_CSV, HN_FIELDS, verified_hn)
    prog = progress_payload(reviews)
    PROGRESS_JSON.write_text(json.dumps(prog, indent=2), encoding="utf-8")
    return prog


def upsert_review(body: dict) -> dict:
    qid = str(body.get("queue_id", "")).strip()
    reviewer = str(body.get("reviewer_id", "")).strip()
    verdict = str(body.get("manual_verdict", "")).strip()
    notes = (body.get("notes") or "").strip()

    if not qid or qid not in {i["queue_id"] for i in _items}:
        return {"ok": False, "error": "unknown queue_id"}
    if not reviewer:
        return {"ok": False, "error": "reviewer_id required"}
    if verdict and verdict not in VERDICTS:
        return {"ok": False, "error": "invalid verdict"}

    item = next(i for i in _items if i["queue_id"] == qid)
    # Reviewer may not change license to invent SAFE; use queue tier.
    license_status = item["license_status"]

    with _lock:
        global _reviews
        # remove prior row for same queue_id+reviewer_id
        _reviews = [
            r for r in _reviews
            if not (r.get("queue_id") == qid and r.get("reviewer_id") == reviewer)
        ]
        if verdict:
            _reviews.append({
                "queue_id": qid,
                "source_id": item["source_id"],
                "manual_verdict": verdict,
                "reviewer_id": reviewer,
                "review_timestamp": utc_now(),
                "license_status": license_status,
                "rel_path": item["resolved_path"] or item["rel_path"],
                "priority": item["priority"],
                "notes": notes,
            })
        prog = persist_all(_reviews)

    return {"ok": True, "progress": prog["counts"]}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path

        if path == "/":
            return self._send(200, UI_HTML.read_bytes(), "text/html; charset=utf-8")

        if path == "/api/items":
            with _lock:
                # Attach this reviewer's existing verdicts for UI
                qs = parse_qs(u.query)
                rid = (qs.get("reviewer_id") or [_reviewer_default])[0].strip()
                mine = {
                    r["queue_id"]: r
                    for r in _reviews
                    if r.get("reviewer_id") == rid
                }
                all_by_qid: dict[str, list[dict]] = {}
                for r in _reviews:
                    all_by_qid.setdefault(r["queue_id"], []).append({
                        "reviewer_id": r["reviewer_id"],
                        "manual_verdict": r["manual_verdict"],
                        "review_timestamp": r["review_timestamp"],
                    })
                payload = {
                    "items": _items,
                    "my_verdicts": mine,
                    "all_reviews_by_qid": all_by_qid,
                    "options": VERDICTS,
                    "reviewer_id": rid,
                    "targets": {
                        "confirmed_DISTRESS": TARGET_DISTRESS,
                        "additional_HARD_NEGATIVE": TARGET_HN_ADDITIONAL,
                    },
                    "progress": progress_payload(_reviews)["counts"],
                    "policy": "Heuristic labels are NEVER auto-promoted. "
                              "Confirmed DISTRESS needs 2 independent reviewers "
                              "+ license SAFE or ATTRIBUTION_REQUIRED.",
                }
            return self._send(
                200, json.dumps(payload).encode("utf-8"), "application/json"
            )

        if path == "/api/progress":
            with _lock:
                body = json.dumps(progress_payload(_reviews), indent=2).encode()
            return self._send(200, body, "application/json")

        if path.startswith("/audio/"):
            qid = path[len("/audio/"):]
            # allow optional extension strip
            if qid.endswith(".wav"):
                qid = qid[:-4]
            p = _path_by_qid.get(qid)
            if not p or not p.exists():
                return self._send(404, b"not found", "text/plain")
            data = p.read_bytes()
            rng = self.headers.get("Range")
            if rng:
                m = re.match(r"bytes=(\d*)-(\d*)", rng)
                if m:
                    start = int(m.group(1) or 0)
                    end = int(m.group(2)) if m.group(2) else len(data) - 1
                    end = min(end, len(data) - 1)
                    chunk = data[start:end + 1]
                    self.send_response(206)
                    self.send_header("Content-Type", "audio/wav")
                    self.send_header(
                        "Content-Range", f"bytes {start}-{end}/{len(data)}"
                    )
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Length", str(len(chunk)))
                    self.end_headers()
                    self.wfile.write(chunk)
                    return
            return self._send(200, data, "audio/wav")

        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if urlparse(self.path).path != "/api/verdict":
            return self._send(404, b"not found", "text/plain")
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, b'{"ok":false}', "application/json")
        result = upsert_review(body)
        code = 200 if result.get("ok") else 400
        return self._send(code, json.dumps(result).encode(), "application/json")


class Server(ThreadingHTTPServer):
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


def export_p0_queue() -> Path:
    """Write P0 worklist with resolved paths (new file; does not alter master queue)."""
    out = GOLD_DIR / "p0_worklist.csv"
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    fields = [
        "queue_id", "source_id", "priority", "license_status", "label_status",
        "heuristic_label", "source_bucket", "rel_path", "resolved_path",
        "audio_available", "manual_verdict", "reviewer_id", "review_timestamp",
        "do_not_auto_promote",
    ]
    rows = []
    for it in _items:
        rows.append({
            **{k: it.get(k, "") for k in fields if k in it},
            "manual_verdict": "",
            "reviewer_id": "",
            "review_timestamp": "",
            "do_not_auto_promote": "YES",
        })
    write_csv(out, fields, rows)
    return out


def main():
    global _items, _reviews, _reviewer_default

    ap = argparse.ArgumentParser(description="Stage 6 dual-review gold labeling")
    ap.add_argument("--priority", default="P0",
                    help="Queue priority filter (default P0). Use ALL for full 7883.")
    ap.add_argument("--reviewer", default="", help="Default reviewer_id in UI")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--progress-only", action="store_true",
                    help="Recompute progress JSON/CSV and exit")
    ap.add_argument("--init-only", action="store_true",
                    help="Create gold store + P0 worklist and exit")
    args = ap.parse_args()

    pri = None if args.priority.upper() == "ALL" else args.priority
    _reviewer_default = args.reviewer.strip()
    _items = load_queue(pri)
    _reviews = load_reviews()
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    # Ensure store files exist
    if not REVIEWS_CSV.exists():
        write_csv(REVIEWS_CSV, REVIEW_FIELDS, [])
    prog = persist_all(_reviews)
    p0_path = export_p0_queue() if (pri == "P0" or args.init_only) else None
    if pri is None:
        # still export P0 slice for convenience
        only_p0 = [i for i in _items if i["priority"] == "P0"]
        # temporary swap for export
        pass

    if args.progress_only or args.init_only:
        if pri == "P0" or args.init_only:
            export_p0_queue()
        print(json.dumps(prog, indent=2))
        print(f"\nGold store: {GOLD_DIR}")
        if p0_path or args.init_only:
            print(f"P0 worklist: {GOLD_DIR / 'p0_worklist.csv'}")
        return

    if not UI_HTML.exists():
        raise SystemExit(f"Missing UI: {UI_HTML}")

    avail = sum(1 for i in _items if i["audio_available"])
    srv, port = serve(args.port)
    url = f"http://127.0.0.1:{port}"
    print("=" * 64)
    print("SafeHer Stage 6 — GOLD label review (dual DISTRESS)")
    print(f"  queue            : {QUEUE_CSV.name} ({'ALL' if pri is None else pri})")
    print(f"  clips loaded    : {len(_items)}  (audio ok: {avail})")
    print(f"  review rows     : {len(_reviews)}")
    print(f"  confirmed DISTRESS : {prog['counts']['confirmed_DISTRESS']} / {TARGET_DISTRESS}")
    print(f"  verified HN (new)  : {prog['counts']['verified_HARD_NEGATIVE_stage6']} "
          f"(need +{TARGET_HN_ADDITIONAL}; legacy HN={LEGACY_HN})")
    print(f"  gold store      : {GOLD_DIR}")
    print(f"  open            : {url}")
    print("=" * 64)
    print("No training. No heuristic auto-promote. Ctrl+C to stop.", flush=True)

    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print(f"\nStopped. Progress → {PROGRESS_JSON}")
    finally:
        srv.server_close()
        persist_all(_reviews)


if __name__ == "__main__":
    main()
