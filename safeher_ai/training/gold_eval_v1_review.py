"""
Human review UI for Gold Eval v1.

Verdicts: DISTRESS / NORMAL / UNCERTAIN
Folder labels are never treated as verified.

HUMAN_VERIFIED becomes true only after DISTRESS or NORMAL is saved.

Usage (from safeher_ai/):
    python training/gold_eval_v1_review.py
"""

from __future__ import annotations

import argparse
import json
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

from prepare_gold_eval_v1 import OUT
from evaluate_gold_thresholds_v1 import evaluate, latest_reviews

UI_HTML = Path(__file__).resolve().parent / "gold_eval_v1_ui.html"
REVIEWS = OUT / "gold_reviews.csv"
VERDICTS = ("DISTRESS", "NORMAL", "UNCERTAIN")
_lock = threading.Lock()
_items: list[dict] = []
_path_by_id: dict[str, Path] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_items() -> list[dict]:
    df = pd.read_csv(OUT / "gold_review_queue.csv")
    return df.to_dict("records")


def progress() -> dict:
    items = _items
    reviews = latest_reviews(REVIEWS)
    by_id = {}
    if not reviews.empty:
        by_id = {str(r.gold_id): str(r.manual_verdict) for r in reviews.itertuples(index=False)}
    counts = {"DISTRESS": 0, "NORMAL": 0, "UNCERTAIN": 0, "UNREVIEWED": 0}
    for item in items:
        v = by_id.get(str(item["gold_id"]), "UNREVIEWED")
        counts[v] = counts.get(v, 0) + 1
    verified = counts["DISTRESS"] + counts["NORMAL"]
    return {
        "targets": {"distress": 500, "hard_negative": 1000},
        "candidates": len(items),
        "counts": counts,
        "human_verified": verified,
        "HUMAN_VERIFIED_rule": "true only when latest verdict is DISTRESS or NORMAL",
        "official_eval_ready": verified > 0,
    }


def upsert(body: dict) -> dict:
    gold_id = str(body.get("gold_id", "")).strip()
    reviewer = str(body.get("reviewer_id", "")).strip() or "reviewer"
    verdict = str(body.get("manual_verdict", "")).strip()
    notes = str(body.get("notes") or "").strip()
    if gold_id not in {str(i["gold_id"]) for i in _items}:
        return {"ok": False, "error": "unknown gold_id"}
    if verdict not in VERDICTS:
        return {"ok": False, "error": "verdict must be DISTRESS, NORMAL, or UNCERTAIN"}
    with _lock:
        if REVIEWS.is_file():
            df = pd.read_csv(REVIEWS)
        else:
            df = pd.DataFrame(columns=["gold_id", "reviewer_id", "manual_verdict", "review_timestamp", "notes"])
        df = df[~((df["gold_id"].astype(str) == gold_id) & (df["reviewer_id"].astype(str) == reviewer))]
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    [
                        {
                            "gold_id": gold_id,
                            "reviewer_id": reviewer,
                            "manual_verdict": verdict,
                            "review_timestamp": utc_now(),
                            "notes": notes,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        df.to_csv(REVIEWS, index=False)
        # Refresh candidate HUMAN_VERIFIED flags from latest reviews.
        cand = pd.read_csv(OUT / "gold_candidates.csv")
        latest = df.sort_values("review_timestamp").groupby("gold_id", as_index=False).tail(1)
        latest_map = {str(r.gold_id): str(r.manual_verdict) for r in latest.itertuples(index=False)}
        cand["human_verification_status"] = cand["gold_id"].map(lambda g: latest_map.get(str(g), "UNREVIEWED"))
        cand["HUMAN_VERIFIED"] = cand["human_verification_status"].isin(["DISTRESS", "NORMAL"])
        cand.to_csv(OUT / "gold_candidates.csv", index=False)
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
                mine = {
                    str(r.gold_id): {
                        "manual_verdict": r.manual_verdict,
                        "notes": getattr(r, "notes", ""),
                    }
                    for r in reviews.itertuples(index=False)
                    if str(getattr(r, "reviewer_id", "")) == rid or True
                }
            payload = {
                "items": _items,
                "my_verdicts": mine,
                "options": list(VERDICTS),
                "progress": progress(),
                "policy": (
                    "Folder names are NOT gold. Mark DISTRESS, NORMAL, or UNCERTAIN. "
                    "Official Balanced-v1 scoring runs only on DISTRESS/NORMAL."
                ),
            }
            return self._send(200, json.dumps(payload, default=str).encode(), "application/json")
        if u.path == "/api/progress":
            return self._send(200, json.dumps(progress()).encode(), "application/json")
        if u.path.startswith("/audio/"):
            gid = u.path[len("/audio/") :]
            p = _path_by_id.get(gid)
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
        if urlparse(self.path).path == "/api/evaluate":
            result = evaluate()
            return self._send(200, json.dumps(result).encode(), "application/json")
        if urlparse(self.path).path != "/api/verdict":
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
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    global _items, _path_by_id
    _items = load_items()
    _path_by_id = {str(i["gold_id"]): Path(str(i["file_path"])) for i in _items}
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(url)
    print("Verdicts: DISTRESS / NORMAL / UNCERTAIN")
    print("Official threshold eval runs only after verified labels exist.")
    if not args.no_browser:
        import webbrowser

        webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
