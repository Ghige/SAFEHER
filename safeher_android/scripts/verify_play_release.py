#!/usr/bin/env python3
"""Repository-side Play Internal Testing gates. Never trains. Never sends SOS.

Usage:
  python scripts/verify_play_release.py
  python scripts/verify_play_release.py --aab path/to/app-release.aab
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

ANDROID = Path(__file__).resolve().parents[1]
REPO = ANDROID.parent
APP = ANDROID / "app"
GRADLE = APP / "build.gradle.kts"
CONTRACT = APP / "src" / "main" / "assets" / "decision_contract.json"
TFLITE = APP / "src" / "main" / "assets" / "yamnet_distress_quant.tflite"
NSC = APP / "src" / "main" / "res" / "xml" / "network_security_config.xml"
MIN_TFLITE_BYTES = 1_000_000

UNSAFE_AAB_SUFFIXES = (
    ".jks",
    ".keystore",
    ".pem",
    ".p12",
    ".env",
    "keystore.properties",
    ".git/",
)
UNSAFE_AAB_NAME_PARTS = (
    "keystore.properties",
    ".env",
    "id_rsa",
    "google-services.json",
    "firebase-credentials.json",
)


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(2)


def gradle_text() -> str:
    return GRADLE.read_text(encoding="utf-8")


def extract_release_block(text: str) -> str:
    m = re.search(r"release\s*\{(.*?)compileOptions", text, re.S)
    if not m:
        # fallback: from 'release {' until next sibling at same indent of compileOptions
        m = re.search(r"buildTypes\s*\{(.*)\n    \}", text, re.S)
        if not m:
            fail("Could not parse buildTypes from app/build.gradle.kts")
        block = m.group(1)
        rel = re.search(r"\n        release\s*\{(.*)", block, re.S)
        if not rel:
            fail("Could not find release { } in buildTypes")
        return rel.group(1)
    return m.group(1)


def check_gradle() -> None:
    text = gradle_text()
    if 'buildConfigField("boolean", "AI_AUTO_SOS_ENABLED", "false")' not in text:
        fail("AI_AUTO_SOS_ENABLED=false missing from Gradle")
    if re.search(r'buildConfigField\("boolean", "AI_AUTO_SOS_ENABLED", "true"\)', text):
        fail("AI_AUTO_SOS_ENABLED=true is present in Gradle")
    if 'buildConfigField("boolean", "DEMO_MODE", "true")' not in text:
        fail("DEMO_MODE=true missing from Gradle BuildConfig")
    if "https://api.safeher.app/" not in text:
        fail("Release BASE_URL must be https://api.safeher.app/")
    # debug may use emulator HTTP; release block must not mention 10.0.2.2
    # Find release { ... } inside buildTypes more carefully
    release = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if re.match(r"\s+release\s*\{", lines[i]):
            buf = []
            depth = 0
            for j in range(i, len(lines)):
                depth += lines[j].count("{") - lines[j].count("}")
                buf.append(lines[j])
                if j > i and depth <= 0:
                    release = "\n".join(buf)
                    break
            break
        i += 1
    if not release:
        fail("release buildType not found")
    if "10.0.2.2" in release:
        fail("Release buildType still references emulator host 10.0.2.2")
    if 'ENABLE_LOGGING", "true"' in release:
        fail("Release ENABLE_LOGGING must be false")
    if 'AI_AUTO_SOS_ENABLED", "false"' not in release:
        fail("Release AI_AUTO_SOS_ENABLED must be false")
    if 'DEMO_MODE", "true"' not in release:
        fail("Release DEMO_MODE must be true")
    if "https://api.safeher.app/" not in release:
        fail("Release BASE_URL is not https://api.safeher.app/")
    print("PASS: Gradle release BuildConfig gates")


def check_contract() -> None:
    raw = CONTRACT.read_text(encoding="utf-8")
    if '"DEMO_MODE": true' not in raw:
        fail("decision_contract.json DEMO_MODE is not true")
    if '"AI_AUTO_SOS_ENABLED": false' not in raw:
        fail("decision_contract.json AI_AUTO_SOS_ENABLED is not false")
    print("PASS: bundled DecisionContract flags")


def check_tflite() -> None:
    if not TFLITE.is_file():
        fail(f"Missing {TFLITE}")
    size = TFLITE.stat().st_size
    if size < MIN_TFLITE_BYTES:
        fail(f"TFLite too small ({size} bytes)")
    print(f"PASS: TFLite asset present ({size} bytes)")


def check_network() -> None:
    raw = NSC.read_text(encoding="utf-8")
    if 'cleartextTrafficPermitted="false"' not in raw:
        fail("Release network security config must forbid cleartext")
    print("PASS: cleartext disabled in main network_security_config")


def check_android_client_otp() -> None:
    main = APP / "src" / "main"
    hits = []
    for path in main.rglob("*"):
        if path.suffix.lower() not in {".kt", ".xml", ".json"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "OTP_ALLOW_DEV_SHORTCUT" in text or "otp == \"123456\"" in text:
            hits.append(str(path.relative_to(REPO)))
    if hits:
        fail("Android main sources must not embed mock OTP shortcuts: " + ", ".join(hits))
    print("PASS: Android client has no mock OTP shortcut")


def check_aab(path: Path) -> None:
    if not path.is_file():
        fail(f"AAB not found: {path}")
    size = path.stat().st_size
    if size < 1_000_000:
        fail(f"AAB unexpectedly small ({size} bytes)")
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        unsafe = []
        for n in names:
            low = n.lower()
            if any(low.endswith(s) or s in low for s in UNSAFE_AAB_SUFFIXES):
                unsafe.append(n)
            elif any(part in low for part in UNSAFE_AAB_NAME_PARTS):
                unsafe.append(n)
            elif low.endswith((".wav", ".csv")) and "assets" in low:
                unsafe.append(n)
        if unsafe:
            fail("AAB contains unsafe files: " + ", ".join(unsafe[:20]))
        tflite_hits = [n for n in names if n.endswith("yamnet_distress_quant.tflite")]
        if not tflite_hits:
            fail("AAB missing yamnet_distress_quant.tflite")
        info = zf.getinfo(tflite_hits[0])
        if info.file_size < MIN_TFLITE_BYTES:
            fail(f"AAB TFLite too small ({info.file_size} bytes)")
        contract_hits = [n for n in names if n.endswith("decision_contract.json")]
        if not contract_hits:
            fail("AAB missing decision_contract.json")
        contract_raw = zf.read(contract_hits[0]).decode("utf-8")
        if '"AI_AUTO_SOS_ENABLED": false' not in contract_raw:
            fail("AAB decision_contract.json does not keep AI_AUTO_SOS_ENABLED=false")
        if '"DEMO_MODE": true' not in contract_raw:
            fail("AAB decision_contract.json does not keep DEMO_MODE=true")
        assets = sorted(n for n in names if "/assets/" in n.replace("\\", "/"))
        print(f"PASS: AAB {path.name} ({size} bytes)")
        print(f"  tflite entries: {tflite_hits} ({info.file_size} bytes)")
        print(f"  contract entries: {contract_hits}")
        print(f"  asset entries: {assets}")
        print(f"  entries: {len(names)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aab", default="", help="Optional path to app-release.aab")
    args = parser.parse_args()
    check_gradle()
    check_contract()
    check_tflite()
    check_network()
    check_android_client_otp()
    aab = Path(args.aab) if args.aab else APP / "build" / "outputs" / "bundle" / "release" / "app-release.aab"
    if aab.is_file():
        check_aab(aab)
    else:
        print("NOT VERIFIED: AAB not on disk (build :app:bundleRelease)")
    print("Play release source gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
