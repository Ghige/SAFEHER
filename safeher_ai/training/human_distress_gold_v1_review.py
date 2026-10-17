"""
Review UI for Human Distress Gold Set v1.

Verdicts: DISTRESS / NORMAL / UNCERTAIN
Folder labels are never treated as verified.

Usage (from safeher_ai/):
    python training/human_distress_gold_v1_review.py
"""

from __future__ import annotations

import argparse
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

from evaluate_human_distress_gold_v1 import evaluate, latest_reviews
from human_distress_gold_v1 import OUT, PHRASE_CATEGORIES, REVIEW_VERDICTS, utc_now

UI_HTML = Path(__file__).resolve().parent / "human_distress_gold_v1_ui.html"
REVIEWS = OUT / "reviews.csv"
_lock = threading.Lock()
_items: list[dict] = []
_path_by_id: dict[str, Path] = {}


def load_items() -> list[dict]:
    path = OUT / "review_queue.csv"
    if not path.is_file():
        return []
    return pd.read_csv(path).to_dict("records")


def progress() -> dict:
    reviews = latest_reviews(REVIEWS)
    by_id = {}
    if not reviews.empty:
        by_id = {str(r.sample_id): str(r.manual_verdict) for r in reviews.itertuples(index=False)}
    counts = {"DISTRESS": 0, "NORMAL": 0, "UNCERTAIN": 0, "UNREVIEWED": 0}
    for item in _items:
        v = by_id.get(str(item["sample_id"]), "UNREVIEWED")
        counts[v] = counts.get(v, 0) + 1
    return {
        "candidates": len(_items),
        "counts": counts,
        "human_verified": counts["DISTRESS"] + counts["NORMAL"],
        "official_eval_ready": (counts["DISTRESS"] + counts["NORMAL"]) > 0,
    }


def upsert(body: dict) -> dict:
    sid = str(body.get("sample_id", "")).strip()
    reviewer = str(body.get("reviewer_id", "")).strip() or "reviewer"
    verdict = str(body.get("manual_verdict", "")).strip()
    notes = str(body.get("notes") or "").strip()
    confirmed = str(body.get("confirmed_category") or "").strip()
    if sid not in {str(i["sample_id"]) for i in _items}:
        return {"ok": False, "error": "unknown sample_id"}
    if verdict not in REVIEW_VERDICTS:
        return {"ok": False, "error": "verdict must be DISTRESS, NORMAL, or UNCERTAIN"}
    if verdict == "DISTRESS" and confirmed not in PHRASE_CATEGORIES and confirmed != "conversational_normal":
        return {"ok": False, "error": "DISTRESS requires a confirmed_category"}
    with _lock:
        if REVIEWS.is_file():
            df = pd.read_csv(REVIEWS)
        else:
            df = pd.DataFrame(columns=["sample_id", "reviewer_id", "manual_verdict", "confirmed_category", "review_timestamp", "notes"])
        df = df[~((df["sample_id"].astype(str) == sid) & (df["reviewer_id"].astype(str) == reviewer))]
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    [
                        {
                            "sample_id": sid,
                            "reviewer_id": reviewer,
                            "manual_verdict": verdict,
                            "confirmed_category": confirmed,
                            "review_timestamp": utc_now(),
                            "notes": notes,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        df.to_csv(REVIEWS, index=False)
        cand = pd.read_csv(OUT / "candidates.csv")
        latest = df.sort_values("review_timestamp").groupby("sample_id", as_index=False).tail(1)
        latest_map = {str(r.sample_id): r for r in latest.itertuples(index=False)}
        labels, verified, reviewers, status = [], [], [], []
        for sid_row in cand["sample_id"].astype(str):
            rec = latest_map.get(sid_row)
            if rec is None:
                labels.append("")
                verified.append(False)
                reviewers.append("")
                status.append("UNREVIEWED")
            else:
                labels.append(str(rec.manual_verdict))
                verified.append(str(rec.manual_verdict) in {"DISTRESS", "NORMAL"})
                reviewers.append(str(rec.reviewer_id))
                status.append(str(rec.manual_verdict))
        cand["HUMAN_LABEL"] = labels
        cand["HUMAN_VERIFIED"] = verified
        cand["reviewer"] = reviewers
        cand["human_verification_status"] = status
        cand.to_csv(OUT / "candidates.csv", index=False)
        cand.to_csv(OUT / "review_queue.csv", index=False)
    return {"ok": True, "progress": progress()}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        u = urlparse(self.path)
        if u.path == "/":
            return self._send(200, UI_HTML.read_bytes(), "text/html; charset=utf-8")
        if u.path == "/api/items":
            qs = parse_qs(u.query)
            rid = (qs.get("reviewer_id") or ["reviewer"])[0]
            reviews = latest_reviews(REVIEWS)
            mine = {}
            if not reviews.empty:
                for r in reviews.itertuples(index=False):
                    mine[str(r.sample_id)] = {
                        "manual_verdict": r.manual_verdict,
                        "confirmed_category": getattr(r, "confirmed_category", ""),
                        "notes": getattr(r, "notes", ""),
                        "reviewer_id": getattr(r, "reviewer_id", rid),
                    }
            payload = {
                "items": _items,
                "my_verdicts": mine,
                "options": list(REVIEW_VERDICTS),
                "categories": list(PHRASE_CATEGORIES),
                "progress": progress(),
            }
            return self._send(200, json.dumps(payload, default=str).encode(), "application/json")
        if u.path.startswith("/audio/"):
            sid = u.path[len("/audio/") :]
            p = _path_by_id.get(sid)
            if not p or not p.exists():
                return self._send(404, b"not found", "text/plain")
            data = p.read_bytes()
            rng = self.headers.get("Range")
            if rng:
                m = re.match(r"bytes=(\d*)-(\d*)", rng)
                if m:
                    start = int(m.group(1) or 0)
                    end = int(m.group(2)) if m.group(2) else len(data) - 1
                    chunk = data[start : end + 1]
                    self.send_response(206)
                    self.send_header("Content-Type", "audio/wav")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Length", str(len(chunk)))
                    self.end_headers()
                    self.wfile.write(chunk)
                    return
            return self._send(200, data, "audio/wav")
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/evaluate":
            return self._send(200, json.dumps(evaluate()).encode(), "application/json")
        if path != "/api/verdict":
            return self._send(404, b"not found", "text/plain")
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, b'{"ok":false}', "application/json")
        result = upsert(body)
        code = 200 if result.get("ok") else 400
        return self._send(code, json.dumps(result).encode(), "application/json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    global _items, _path_by_id
    _items = load_items()
    _path_by_id = {str(i["sample_id"]): Path(str(i["file_path"])) for i in _items}
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(url)
    print("Verdicts: DISTRESS / NORMAL / UNCERTAIN")
    print("Drop new recordings in data/incoming/human_distress_gold_v1/ then re-run prepare.")
    if not args.no_browser:
        import webbrowser

        webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
