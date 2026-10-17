"""
Human review for real-world AI feedback candidates.

Reuses Stage 6 verdicts (DISTRESS / HARD_NEGATIVE / REJECT / AMBIGUOUS).
Never auto-promotes UNREVIEWED, user-confirmed labels, or AI predictions to gold.

Input: JSONL export from scripts/export_ai_feedback_candidates.py
Output: safeher_ai/data/training_logs/realworld_gold/

Run:
  python training/review_ai_feedback.py --progress-only
  python training/review_ai_feedback.py --import ..\\safeher_backend\\data\\ai_feedback_export.jsonl --reviewer alice
"""

from __future__ import annotations

import argparse
import csv
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from gold_policy import (
    FORBIDDEN_GOLD_LABELS,
    GOLD_VERDICTS,
    LICENSE_OK_REALWORLD,
    REVIEW_VERDICTS,
    TARGET_DISTRESS,
    TARGET_HARD_NEGATIVE,
    assign_split,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
GOLD_DIR = DATA / "training_logs" / "realworld_gold"
REVIEWS_CSV = GOLD_DIR / "reviews.csv"
CONFIRMED_DISTRESS_CSV = GOLD_DIR / "confirmed_distress.csv"
VERIFIED_HN_CSV = GOLD_DIR / "verified_hard_negative.csv"
PROGRESS_JSON = GOLD_DIR / "progress.json"
AUDIT_JSONL = GOLD_DIR / "promotion_audit.jsonl"
QUEUE_JSONL = GOLD_DIR / "candidate_queue.jsonl"
UI_HTML = Path(__file__).resolve().parent / "review_ai_feedback_ui.html"

REVIEW_FIELDS = [
    "event_id",
    "session_id",
    "source_id",
    "manual_verdict",
    "reviewer_id",
    "review_timestamp",
    "license_status",
    "candidate_category",
    "model_version",
    "notes",
]

CONFIRM_FIELDS = [
    "event_id",
    "session_id",
    "source_id",
    "manual_verdict",
    "license_status",
    "reviewer_a",
    "reviewer_b",
    "review_timestamp_a",
    "review_timestamp_b",
    "confirmed_at",
    "split",
]

HN_FIELDS = [
    "event_id",
    "session_id",
    "source_id",
    "manual_verdict",
    "license_status",
    "reviewer_id",
    "review_timestamp",
    "dual_agree",
    "notes",
    "split",
]

_lock = threading.Lock()
_items: list[dict] = []
_reviews: list[dict] = []
_reviewer_default = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    tmp.replace(path)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_reviews() -> list[dict]:
    if not REVIEWS_CSV.exists():
        return []
    with REVIEWS_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def append_audit(event: str, detail: dict) -> None:
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    rec = {"ts": utc_now(), "event": event, **detail}
    with AUDIT_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def recompute_confirmed(reviews: list[dict]) -> tuple[list[dict], list[dict]]:
    by_eid: dict[str, list[dict]] = {}
    for r in reviews:
        if not r.get("manual_verdict"):
            continue
        by_eid.setdefault(r["event_id"], []).append(r)

    confirmed: list[dict] = []
    verified_hn: list[dict] = []

    for eid, rs in by_eid.items():
        latest: dict[str, dict] = {}
        for r in sorted(rs, key=lambda x: x.get("review_timestamp", "")):
            rid = (r.get("reviewer_id") or "").strip()
            if rid:
                latest[rid] = r

        distress = [r for r in latest.values() if r.get("manual_verdict") == "DISTRESS"]
        if len(distress) >= 2:
            a, b = distress[0], distress[1]
            lic = a.get("license_status") or b.get("license_status") or ""
            if lic in LICENSE_OK_REALWORLD and a["reviewer_id"] != b["reviewer_id"]:
                confirmed.append({
                    "event_id": eid,
                    "session_id": a.get("session_id", ""),
                    "source_id": a.get("source_id") or a.get("session_id") or eid,
                    "manual_verdict": "DISTRESS",
                    "license_status": lic,
                    "reviewer_a": a["reviewer_id"],
                    "reviewer_b": b["reviewer_id"],
                    "review_timestamp_a": a.get("review_timestamp", ""),
                    "review_timestamp_b": b.get("review_timestamp", ""),
                    "confirmed_at": utc_now(),
                    "split": assign_split(eid),
                })

        hn = [r for r in latest.values() if r.get("manual_verdict") == "HARD_NEGATIVE"]
        if hn:
            primary = hn[0]
            lic = primary.get("license_status", "")
            if lic in LICENSE_OK_REALWORLD:
                verified_hn.append({
                    "event_id": eid,
                    "session_id": primary.get("session_id", ""),
                    "source_id": primary.get("source_id") or primary.get("session_id") or eid,
                    "manual_verdict": "HARD_NEGATIVE",
                    "license_status": lic,
                    "reviewer_id": primary.get("reviewer_id", ""),
                    "review_timestamp": primary.get("review_timestamp", ""),
                    "dual_agree": "YES" if len(hn) >= 2 else "NO",
                    "notes": primary.get("notes", ""),
                    "split": assign_split(eid),
                })

    confirmed.sort(key=lambda r: r["event_id"])
    verified_hn.sort(key=lambda r: r["event_id"])
    return confirmed, verified_hn


def persist_all(reviews: list[dict]) -> dict:
    confirmed, verified_hn = recompute_confirmed(reviews)
    # Refuse writing forbidden labels into gold CSVs.
    confirmed = [r for r in confirmed if r.get("manual_verdict") in GOLD_VERDICTS]
    verified_hn = [r for r in verified_hn if r.get("manual_verdict") in GOLD_VERDICTS]
    write_csv(REVIEWS_CSV, REVIEW_FIELDS, reviews)
    write_csv(CONFIRMED_DISTRESS_CSV, CONFIRM_FIELDS, confirmed)
    write_csv(VERIFIED_HN_CSV, HN_FIELDS, verified_hn)
    prog = {
        "generated_at": utc_now(),
        "policy": {
            "no_auto_promote": True,
            "no_automatic_retrain": True,
            "confirmed_distress_requires_dual_review": True,
            "license_ok": sorted(LICENSE_OK_REALWORLD),
            "forbidden_in_gold": sorted(FORBIDDEN_GOLD_LABELS),
            "verdicts": list(REVIEW_VERDICTS),
        },
        "counts": {
            "review_rows": len(reviews),
            "confirmed_DISTRESS": len(confirmed),
            "verified_HARD_NEGATIVE": len(verified_hn),
            "remaining_DISTRESS": max(0, TARGET_DISTRESS - len(confirmed)),
            "remaining_HARD_NEGATIVE": max(0, TARGET_HARD_NEGATIVE - len(verified_hn)),
        },
        "production_ready": False,
        "gold_eligible_now": False,
    }
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_JSON.write_text(json.dumps(prog, indent=2), encoding="utf-8")
    append_audit("recompute", {"counts": prog["counts"]})
    return prog


def upsert_review(body: dict) -> dict:
    eid = str(body.get("event_id", "")).strip()
    reviewer = str(body.get("reviewer_id", "")).strip()
    verdict = str(body.get("manual_verdict", "")).strip()
    notes = (body.get("notes") or "").strip()
    known = {i["event_id"] for i in _items}
    if not eid or eid not in known:
        return {"ok": False, "error": "unknown event_id"}
    if not reviewer:
        return {"ok": False, "error": "reviewer_id required"}
    if verdict and verdict not in REVIEW_VERDICTS:
        return {"ok": False, "error": "invalid verdict"}

    item = next(i for i in _items if i["event_id"] == eid)
    if item.get("review_status") == "UNREVIEWED" and not verdict:
        return {"ok": False, "error": "empty verdict"}

    with _lock:
        global _reviews
        _reviews = [
            r for r in _reviews
            if not (r.get("event_id") == eid and r.get("reviewer_id") == reviewer)
        ]
        if verdict:
            _reviews.append({
                "event_id": eid,
                "session_id": item.get("session_id", ""),
                "source_id": item.get("session_id") or eid,
                "manual_verdict": verdict,
                "reviewer_id": reviewer,
                "review_timestamp": utc_now(),
                "license_status": item.get("license_status") or "USER_CONSENT_OPT_IN",
                "candidate_category": item.get("candidate_category", ""),
                "model_version": item.get("model_version", ""),
                "notes": notes,
            })
            append_audit("review", {"event_id": eid, "reviewer_id": reviewer, "verdict": verdict})
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
        if u.path == "/":
            html = UI_HTML.read_bytes() if UI_HTML.exists() else (
                b"<html><body><h1>SafeHer real-world AI review</h1>"
                b"<p>Metadata only. No audio. POST /api/review</p></body></html>"
            )
            return self._send(200, html, "text/html; charset=utf-8")
        if u.path == "/api/items":
            qs = parse_qs(u.query)
            rid = (qs.get("reviewer_id") or [_reviewer_default])[0].strip()
            with _lock:
                mine = {r["event_id"]: r for r in _reviews if r.get("reviewer_id") == rid}
                payload = {
                    "items": _items,
                    "my_verdicts": mine,
                    "options": list(REVIEW_VERDICTS),
                    "reviewer_id": rid,
                    "policy": (
                        "AI predictions are NEVER gold. Dual DISTRESS + USER_CONSENT_OPT_IN "
                        "required. UNREVIEWED/AMBIGUOUS/REJECT never enter gold."
                    ),
                    "progress": persist_all(_reviews)["counts"],
                }
            return self._send(200, json.dumps(payload).encode(), "application/json")
        if u.path == "/api/progress":
            with _lock:
                body = json.dumps(persist_all(_reviews), indent=2).encode()
            return self._send(200, body, "application/json")
        return self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if urlparse(self.path).path != "/api/review":
            return self._send(404, b"not found", "text/plain")
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return self._send(400, b'{"ok":false}', "application/json")
        result = upsert_review(body)
        code = 200 if result.get("ok") else 400
        return self._send(code, json.dumps(result).encode(), "application/json")


def main() -> int:
    global _items, _reviews, _reviewer_default
    parser = argparse.ArgumentParser(description="Review real-world AI feedback (no training)")
    parser.add_argument("--import", dest="import_path", default="", help="JSONL candidate export")
    parser.add_argument("--reviewer", default="")
    parser.add_argument("--progress-only", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(args.import_path) if args.import_path else QUEUE_JSONL
    imported = load_jsonl(src)
    if imported:
        QUEUE_JSONL.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in imported) + "\n",
            encoding="utf-8",
        )
    _items = load_jsonl(QUEUE_JSONL)
    _reviews = load_reviews()
    _reviewer_default = args.reviewer
    prog = persist_all(_reviews)
    print(json.dumps(prog, indent=2))
    if args.progress_only:
        return 0
    if not _items:
        print("No candidates. Export with backend scripts/export_ai_feedback_candidates.py")
        return 0
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Review UI http://{args.host}:{args.port}/  (Ctrl+C to stop). Does NOT train.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
