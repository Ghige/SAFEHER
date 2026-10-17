#!/usr/bin/env python3
"""
Write full-key HI/MR string resources (324 keys).

- Curated translations for SOS/auth/errors/contacts/preflight (quality).
- Remaining keys copied from EN so locale folders are complete (no missing resources).
Reports curated vs english_fallback counts honestly.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EN = ROOT / "safeher_android" / "app" / "src" / "main" / "res" / "values" / "strings.xml"
OUT = {
    "hi": ROOT / "safeher_android" / "app" / "src" / "main" / "res" / "values-hi" / "strings.xml",
    "mr": ROOT / "safeher_android" / "app" / "src" / "main" / "res" / "values-mr" / "strings.xml",
}

STRING_RE = re.compile(r'<string\s+name="([^"]+)"[^>]*>(.*?)</string>', re.DOTALL)

# Load curated maps from previous stage-2 generator (critical UX).
from generate_stage2_full_locales import OVERRIDES  # type: ignore


def parse_strings(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    out = []
    for m in STRING_RE.finditer(text):
        raw = (
            m.group(2)
            .replace("\\'", "'")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("\\n", "\n")
        )
        out.append((m.group(1), raw))
    return out


def escape_android(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("'", "\\'")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "\\n")
    )


def write_locale(lang: str, pairs: list[tuple[str, str]]) -> tuple[int, int]:
    overrides = OVERRIDES.get(lang, {})
    curated = 0
    fallback = 0
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<resources>",
        f"    <!-- Stage 2 full key coverage ({lang}): curated + EN fallback -->",
    ]
    for name, original in pairs:
        if name in overrides:
            value = overrides[name]
            curated += 1
        else:
            value = original
            fallback += 1
        lines.append(f'    <string name="{name}">{escape_android(value)}</string>')
    lines.append("</resources>")
    path = OUT[lang]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{lang}: {len(pairs)} keys curated={curated} en_fallback={fallback} -> {path}")
    return curated, fallback


def main() -> int:
    pairs = parse_strings(EN)
    print(f"EN strings: {len(pairs)}")
    write_locale("hi", pairs)
    write_locale("mr", pairs)
    return 0


if __name__ == "__main__":
    # Allow importing sibling script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
