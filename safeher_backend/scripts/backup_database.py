#!/usr/bin/env python3
"""
SafeHer Stage 9 — database backup helper (logical dump).

Usage (PostgreSQL client required):
  python scripts/backup_database.py
  python scripts/backup_database.py --output-dir D:\\backups\\safeher

Does NOT enable AI SOS. Does NOT modify models/datasets.
Restore is documented in the printed instructions (manual pg_restore/psql).

External verification: restore drill on a staging DB is NOT VERIFIED by this script alone.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def _parse_db_url(url: str) -> dict:
    u = urlparse(url)
    return {
        "host": u.hostname or "localhost",
        "port": str(u.port or 5432),
        "user": u.username or "postgres",
        "password": u.password or "",
        "dbname": (u.path or "/safeher_db").lstrip("/") or "safeher_db",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="SafeHer PostgreSQL backup")
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "data" / "backups"),
        help="Directory for dump files",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="PostgreSQL URL (default: DATABASE_URL env)",
    )
    args = parser.parse_args()

    if not args.database_url:
        # Load from app settings if available
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from app.config import settings

            args.database_url = settings.DATABASE_URL
        except Exception as exc:
            print(f"DATABASE_URL missing and settings load failed: {exc}", file=sys.stderr)
            return 1

    if not shutil.which("pg_dump"):
        print(
            "pg_dump not found on PATH. Install PostgreSQL client tools, then re-run.\n"
            "NOT VERIFIED: backup was not created.",
            file=sys.stderr,
        )
        return 2

    cfg = _parse_db_url(args.database_url)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_file = out_dir / f"safeher_{cfg['dbname']}_{stamp}.dump"

    env = os.environ.copy()
    if cfg["password"]:
        env["PGPASSWORD"] = cfg["password"]

    cmd = [
        "pg_dump",
        "-h",
        cfg["host"],
        "-p",
        cfg["port"],
        "-U",
        cfg["user"],
        "-d",
        cfg["dbname"],
        "-Fc",
        "-f",
        str(out_file),
    ]
    print("Running:", " ".join(cmd[:-2] + ["-f", str(out_file)]))
    try:
        subprocess.run(cmd, check=True, env=env)
    except subprocess.CalledProcessError as exc:
        print(f"pg_dump failed: {exc}", file=sys.stderr)
        return 3

    print(f"Backup OK: {out_file}")
    print(
        "Restore (manual):\n"
        f"  pg_restore -h HOST -U USER -d TARGET --clean --if-exists {out_file}\n"
        "Restore drill on staging: NOT VERIFIED until ops runs it."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
