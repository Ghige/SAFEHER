#!/usr/bin/env python3
"""Fail if Android release (or any buildType) enables AI_AUTO_SOS without policy."""

from __future__ import annotations

import re
import sys
from pathlib import Path

GRADLE = (
    Path(__file__).resolve().parents[2]
    / "safeher_android"
    / "app"
    / "build.gradle.kts"
)

FIELD_RE = re.compile(
    r'buildConfigField\(\s*"boolean"\s*,\s*"AI_AUTO_SOS_ENABLED"\s*,\s*"(true|false)"\s*\)'
)


def main() -> int:
    text = GRADLE.read_text(encoding="utf-8")
    matches = FIELD_RE.findall(text)
    if not matches:
        print("FAIL: no AI_AUTO_SOS_ENABLED buildConfigField found")
        return 1
    if any(v == "true" for v in matches):
        print(f"FAIL: AI_AUTO_SOS_ENABLED=true found in {GRADLE}")
        return 1
    # Ensure release block contains an explicit false assignment
    release_idx = text.find("release {")
    if release_idx < 0:
        print("FAIL: release buildType missing")
        return 1
    release_slice = text[release_idx : release_idx + 1200]
    if 'buildConfigField("boolean", "AI_AUTO_SOS_ENABLED", "false")' not in release_slice:
        print("FAIL: release block missing hard-coded AI_AUTO_SOS_ENABLED=false")
        return 1
    print(f"OK: {len(matches)} AI_AUTO_SOS_ENABLED field(s) all false; release hard-coded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
