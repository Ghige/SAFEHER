"""Generate SafeHer team handover PDF (no secrets). ASCII-only for Helvetica."""
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "TEAM_HANDOVER.pdf"


class HandoverPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(120, 40, 70)
        self.cell(0, 8, "SafeHer - Team Handover Guide", align="L")
        self.ln(4)
        self.set_draw_color(200, 160, 170)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0,
            10,
            f"Page {self.page_no()}/{{nb}}  |  No credentials in this document",
            align="C",
        )

    def h1(self, text):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(90, 20, 50)
        self.multi_cell(0, 9, text)
        self.ln(2)

    def h2(self, text):
        self.ln(2)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(110, 30, 60)
        self.multi_cell(0, 7, text)
        self.ln(1)

    def body(self, text):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def bullet(self, text):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, f"- {text}")

    def warn(self, text):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(140, 40, 20)
        self.multi_cell(0, 5.5, text)
        self.ln(1)


def build():
    pdf = HandoverPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.h1("SafeHer Team Handover")
    pdf.body(
        "SafeHer is a personal-safety system: Android app + FastAPI backend + "
        "on-device audio AI + WhatsApp/Firebase alerts + live track web page."
    )
    pdf.body("Repo: https://github.com/Ghige/SAFEHER")
    pdf.body(
        "Folders: safeher_android / safeher_backend / safeher_ai / safeher_web. "
        "Large training audio (safeher_ai/data) and secrets are NOT in Git."
    )

    pdf.h2("1. First-time setup (Backend) - start here")
    pdf.bullet("Install Python 3.11 (recommended). Avoid 3.12+ for AI/TensorFlow compatibility.")
    pdf.bullet("Install PostgreSQL and Redis (Redis optional for simple local API tests; required for reliable dead-man switch).")
    pdf.bullet("Clone the repo from GitHub.")
    pdf.bullet("Open a terminal in safeher_backend.")
    pdf.bullet("Create venv:  python -m venv .venv")
    pdf.bullet("Activate (Windows):  .venv\\Scripts\\activate")
    pdf.bullet("Activate (macOS/Linux):  source .venv/bin/activate")
    pdf.bullet("Install deps:  pip install -r requirements.txt")
    pdf.bullet("Copy credentials template:  copy .env.example .env   (then fill real values - never commit .env)")
    pdf.bullet("Place Firebase Admin JSON locally (e.g. firebase-credentials.json). Point FIREBASE_CREDENTIALS_PATH to it.")
    pdf.bullet("Create DB, then:  alembic upgrade head")
    pdf.bullet("Run API:  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    pdf.bullet("Open docs:  http://localhost:8000/docs")

    pdf.h2("2. Put credentials (local only)")
    pdf.body("Ask the lead for private values. Do not put real secrets in Git, chat dumps, or this PDF.")
    pdf.bullet("Backend .env: DATABASE_URL, SECRET_KEY, REDIS_URL, META_* WhatsApp tokens, FIREBASE_*, TRACK_BASE_URL, API_BASE_URL")
    pdf.bullet("Backend Firebase Admin SDK JSON file (service account)")
    pdf.bullet("Android: google-services.json into safeher_android/app/")
    pdf.bullet("Android: local.properties with sdk.dir and MAPS_API_KEY")
    pdf.bullet("Optional release: keystore.properties from keystore.properties.example")

    pdf.h2("3. Android setup (short)")
    pdf.bullet("Install Android Studio + JDK 17.")
    pdf.bullet("Open safeher_android/, add google-services.json + local.properties.")
    pdf.bullet("Sync Gradle, run debug app on device/emulator.")
    pdf.bullet("Point app API base URL to your machine (emulator often 10.0.2.2:8000).")
    pdf.bullet("TFLite model asset yamnet_distress_quant.tflite should already be under app assets.")

    pdf.h2("4. AI training setup (optional / retrain)")
    pdf.bullet("cd safeher_ai && python -m venv .venv && activate && pip install -r requirements_training.txt")
    pdf.bullet("Dataset is NOT in Git. Get safeher_ai/data from shared Drive/OneDrive and place under safeher_ai/data/.")
    pdf.bullet("Pipeline: training/00_convert_audio.py -> 01_prepare_dataset.py -> 02_train_model.py -> 03_evaluate_model.py -> 04_export_tflite.py")
    pdf.bullet("Copy exported TFLite into Android assets before release.")

    pdf.h2("5. Web track page")
    pdf.bullet("safeher_web/track/index.html - contacts open WhatsApp track link with token.")
    pdf.bullet("Locally backend can serve /track/. Production: host on safeher.app with query string preserved.")

    pdf.add_page()
    pdf.h2("6. CRITICAL - Wallet / pocket panic auto-trigger (current behavior)")
    pdf.warn(
        "CURRENT STATUS: If the phone is in a wallet/pocket and the SafeHer app is in the BACKGROUND "
        "(screen off / app not open), AI does NOT keep listening for panic and will NOT auto-trigger SOS."
    )
    pdf.body(
        "Why: AiMonitoringCoordinator only runs the inference loop while the app is in the foreground "
        "(_isAppInForeground). AppForegroundTracker stops the loop on background. Field docs also say "
        "background inference pauses. This is intentional for RC1 (battery/privacy/OS limits), "
        "but it means hands-free wallet detection is NOT done yet."
    )
    pdf.body("What DOES work today (when Monitoring is ON and app is open/foreground):")
    pdf.bullet("On-device TFLite audio scoring about every 3 seconds")
    pdf.bullet("Backend confidence fusion can recommend: ignore / haptic / 30s countdown / immediate SOS")
    pdf.bullet("Manual SOS button + alert flow + WhatsApp track link + location while alert active")
    pdf.bullet("Dead-man escalation if pings stop during an active alert (needs Redis in multi-worker prod)")

    pdf.h2("7. Pending / remaining work (summary for team)")
    pdf.bullet("AI: True always-on / wallet-pocket monitoring with reliable background service + battery policy")
    pdf.bullet("AI: Reduce false positives (street noise, traffic); retune thresholds with real field data")
    pdf.bullet("AI: Movement / fall model still feature-flagged OFF (AiFeatureFlags.MOVEMENT_AI_ENABLED = false)")
    pdf.bullet("AI: Dataset sharing outside Git; improve distress/normal balance; optional noise folder for augmentation")
    pdf.bullet("AI: Cloud dataset upload / Help Improve AI is limited (design: opt-in; not full prod pipeline)")
    pdf.bullet("Messaging: Production Meta WhatsApp approved templates (alert + cancel) wired in .env")
    pdf.bullet("Android: Official google-services.json, Maps key, release signing, battery-optimization UX polish")
    pdf.bullet("Backend: Production Postgres/Redis/hosting, rotate any previously shared service-account keys")
    pdf.bullet("Web: Deploy track page on production domain with CORS + HTTPS")
    pdf.bullet("QA: Full end-to-end on real devices outdoors (see test cases below)")
    pdf.bullet("Docs: Keep README + PRODUCTION_SETUP.md updated as env vars change")

    pdf.h2("8. Test cases checklist")
    pdf.body("Backend")
    pdf.bullet("GET /docs loads; health/auth register+login returns JWT")
    pdf.bullet("pytest in safeher_backend passes")
    pdf.bullet("Create alert -> WhatsApp/Meta path sends (or logs clearly if token missing)")
    pdf.bullet("Track link opens map updates; cancel alert hides location")
    pdf.bullet("Dead-man: stop pings -> escalation after timeout")

    pdf.body("Android - core")
    pdf.bullet("Install, login/register, grant mic + location (+ notifications)")
    pdf.bullet("Manual SOS -> countdown -> active alert -> contacts get track link")
    pdf.bullet("Cancel SOS within window -> cancel message / no false emergency")
    pdf.bullet("Maps show when MAPS_API_KEY set; graceful fallback if missing")
    pdf.bullet("FCM token saved after login (users.fcm_token)")

    pdf.body("Android - AI (foreground)")
    pdf.bullet("AI Status: on-device model Ready")
    pdf.bullet("Monitoring ON: quiet room stays below trigger; no SOS from silence")
    pdf.bullet("Normal talk should not repeatedly hit high distress")
    pdf.bullet("Safe playback of distress sample via speaker raises score (note peak)")
    pdf.bullet("Score tiers: ~60-79 countdown path; ~80+ immediate SOS path (see AiScoreThresholds / field doc)")
    pdf.bullet("Monitoring OFF: mic foreground service stops")

    pdf.body("Android - wallet / background (expected FAIL until pending work ships)")
    pdf.bullet("Enable Monitoring, lock phone / put in pocket/wallet for 2-5 minutes with distress audio nearby")
    pdf.bullet("EXPECTATION TODAY: no auto SOS (inference paused in background) - confirm and log as known gap")
    pdf.bullet("Bring app to foreground again - monitoring/inference should resume")

    pdf.body("Regression / safety")
    pdf.bullet("No secrets committed (.env, adminsdk JSON, google-services.json)")
    pdf.bullet("Release build ProGuard does not break Retrofit/Firebase")
    pdf.bullet("Offline SOS queue behavior (if implemented on device) when network returns")

    pdf.h2("9. Who to ask / where to read")
    pdf.bullet("Root README.md - full setup")
    pdf.bullet("PRODUCTION_SETUP.md - production checklist")
    pdf.bullet("safeher_ai/README.md - training pipeline")
    pdf.bullet("safeher_android/docs/AUDIO_AI_FIELD_TEST.md - AI field tests")
    pdf.bullet("safeher_web/README.md - track page deploy")

    pdf.ln(4)
    pdf.warn("Never commit passwords, API tokens, Firebase private keys, or .env files.")

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
