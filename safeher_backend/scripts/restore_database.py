#!/usr/bin/env python3
"""
SafeHer P0-5 — restore a logical dump created by backup_database.py.

Usage:
  python scripts/restore_database.py --dump PATH --database-url postgresql://...
  python scripts/restore_database.py --dump PATH --database-url ... --yes

SAFETY:
  - Refuses to restore unless --yes is passed.
  - Prefer a disposable / staging database — never assume production.
  - Does NOT enable AI SOS. Does NOT send WhatsApp.

External restore drill remains NOT VERIFIED until ops runs this successfully
against a real disposable DB and records RPO/RTO.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
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
    parser = argparse.ArgumentParser(description="SafeHer PostgreSQL restore")
    parser.add_argument("--dump", required=True, help="Path to pg_dump -Fc file")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Target PostgreSQL URL (prefer disposable DB)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required confirmation — restore mutates the target database",
    )
    args = parser.parse_args()

    dump = Path(args.dump)
    if not dump.is_file():
        print(f"Dump not found: {dump}", file=sys.stderr)
        return 1

    if not args.database_url:
        print("DATABASE_URL / --database-url required", file=sys.stderr)
        return 1

    if not args.yes:
        print(
            "Refusing restore without --yes. "
            "Use a disposable staging database, then re-run with --yes.",
            file=sys.stderr,
        )
        return 4

    if not shutil.which("pg_restore"):
        print(
            "pg_restore not found on PATH. Install PostgreSQL client tools.\n"
            "NOT VERIFIED: restore was not executed.",
            file=sys.stderr,
        )
        return 2

    cfg = _parse_db_url(args.database_url)
    env = os.environ.copy()
    if cfg["password"]:
        env["PGPASSWORD"] = cfg["password"]

    cmd = [
        "pg_restore",
        "-h",
        cfg["host"],
        "-p",
        cfg["port"],
        "-U",
        cfg["user"],
        "-d",
        cfg["dbname"],
        "--clean",
        "--if-exists",
        "--no-owner",
        str(dump),
    ]
    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, env=env)
    except subprocess.CalledProcessError as exc:
        print(f"pg_restore failed: {exc}", file=sys.stderr)
        return 3

    print(f"Restore OK into db={cfg['dbname']} host={cfg['host']}")
    print("Record RPO/RTO in ops notes. AI_AUTO_SOS remains false.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
