"""
SafeHer — Audio Background Monitor
Captures 1-second mic snippets, scores each one locally via TFLite,
and discards the buffer immediately if no distress is detected.
Nothing is saved or sent off-device unless distress is confirmed.

Usage:
    monitor = AudioMonitor(on_sos_trigger=your_callback)
    monitor.start()
    ...
    monitor.stop()

Flow:
    mic → 1-sec RAM buffer → TFLite score → low?  wipe buffer, sleep
                                           → high? confirmation window → SOS
"""

import threading
import time
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Callable, List, Optional
from inference import predict_distress, DISTRESS_THRESHOLD

logger = logging.getLogger(__name__)

# ── Tuning constants ──────────────────────────────────────────────────────────

SAMPLE_RATE   = 16000
CHUNK_SECONDS = 1
CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_SECONDS

# DISTRESS_THRESHOLD lives in inference.py — imported above, not redefined
# here. One source of truth: retrain, update the threshold in one place,
# and every caller picks it up automatically.

# CONFIRM_HITS_NEEDED: how many hits within CONFIRM_WINDOW_SEC trigger SOS.
# !! DO NOT TUNE BY INTUITION — A/B test with real users. !!
# Current hypothesis: 2 is safer for Indian environments (noisy, brief cries).
# 3 reduces false positives but risks missing "Help! ... (silence) ... Help!"
# Test both and measure: false positive rate vs missed distress rate.
CONFIRM_HITS_NEEDED = 2        # changed from 3 — test 2 vs 3 before shipping

CONFIRM_WINDOW_SEC  = 5

# SLEEP_BETWEEN_SEC: gap between captures when score is low.
# Lower = more responsive, more battery drain.
# !! BENCHMARK ON TARGET DEVICES before setting this. !!
# Suggested test: measure battery % drop over 1 hour at 0.1 / 0.2 / 0.5
# on a Rs.6,000 Android (Redmi, Realme) — not a flagship.
# Current: 0.1 (responsive). May need to raise to 0.2-0.5 on low-end devices.
SLEEP_BETWEEN_SEC   = 0.1


# ── ConfirmationWindow ────────────────────────────────────────────────────────

@dataclass
class ConfirmationWindow:
    """
    Tracks hit history within the confirmation window.

    Stores individual scores so we can compute:
      - hit count           (how many chunks triggered)
      - average confidence  (51,52,53 vs 95,97,99 — treated differently)
      - peak confidence     (worst-case moment in the window)

    51+52+53 avg=52  →  possible noise bleed, lower urgency
    95+97+99 avg=97  →  very high confidence, maximum urgency
    """
    hits:         List[float] = field(default_factory=list)
    window_start: Optional[float] = None

    def add(self, score: float, now: float):
        if self.window_start is None:
            self.window_start = now
        self.hits.append(score)

    def reset(self):
        self.hits         = []
        self.window_start = None

    def is_expired(self, now: float) -> bool:
        return (
            self.window_start is not None
            and (now - self.window_start) > CONFIRM_WINDOW_SEC
        )

    @property
    def hit_count(self) -> int:
        return len(self.hits)

    @property
    def average_confidence(self) -> float:
        return float(np.mean(self.hits)) if self.hits else 0.0

    @property
    def peak_confidence(self) -> float:
        return float(np.max(self.hits)) if self.hits else 0.0

    def summary(self) -> dict:
        return {
            "hit_count":          self.hit_count,
            "average_confidence": round(self.average_confidence, 1),
            "peak_confidence":    round(self.peak_confidence, 1),
            "scores":             [round(s, 1) for s in self.hits],
        }


# ── SOSEvent ──────────────────────────────────────────────────────────────────

@dataclass
class SOSEvent:
    """
    Passed to the on_sos_trigger callback.
    Contains the full confidence history so the caller can decide urgency.

    Example:
        event.hit_count          -> 2
        event.average_confidence -> 96.5   (high urgency)
        event.peak_confidence    -> 98.0
        event.scores             -> [95.0, 98.0]

    The caller (alert system, sensor fusion layer) uses this to:
      - Set alert urgency level
      - Cross-check with movement / location context
      - Decide whether to page emergency services immediately
    """
    hit_count:          int
    average_confidence: float
    peak_confidence:    float
    scores:             List[float]
    timestamp:          float = field(default_factory=time.time)

    @property
    def urgency(self) -> str:
        """
        Simple urgency tier based on average confidence.
        Used by the context override layer (sensor fusion).

        LOW:    avg < 65   -- alert trusted contacts only
        MEDIUM: avg 65-85  -- alert contacts + request location check-in
        HIGH:   avg > 85   -- full SOS, alert contacts + 112
        """
        if self.average_confidence >= 85:
            return "HIGH"
        elif self.average_confidence >= 65:
            return "MEDIUM"
        else:
            return "LOW"


# ── AudioMonitor ──────────────────────────────────────────────────────────────

class AudioMonitor:
    """
    Background audio monitor.

    Captures 1-second mic snippets in a loop. Each snippet is:
      1. Fed into the local TFLite model (no network call, no disk write).
      2. If score < DISTRESS_THRESHOLD -> buffer zeroed, sleep, continue.
      3. If score >= DISTRESS_THRESHOLD -> enter confirmation window.
         If CONFIRM_HITS_NEEDED hits occur within CONFIRM_WINDOW_SEC -> SOS.

    The SOS callback receives a SOSEvent with full confidence history,
    so the alert system can apply sensor fusion (movement, location, time)
    before deciding final response.
    """

    def __init__(
        self,
        on_sos_trigger: Optional[Callable[[SOSEvent], None]] = None,
        context_override: Optional[Callable[[SOSEvent], bool]] = None,
    ):
        """
        Args:
            on_sos_trigger:   called when distress is confirmed.
                              Receives a SOSEvent. Runs on the monitor thread.

            context_override: optional sensor fusion hook.
                              Called before firing SOS with the SOSEvent.
                              Return False to suppress the alert.

                              Example - suppress if location is a cinema:
                                def my_override(event):
                                    if is_known_safe_venue(current_location()):
                                        if event.average_confidence < 90:
                                            return False
                                    return True
        """
        self._on_sos_trigger   = on_sos_trigger  or self._default_sos_handler
        self._context_override = context_override
        self._running          = False
        self._thread           = None
        self._window           = ConfirmationWindow()

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            logger.warning("AudioMonitor already running")
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("AudioMonitor started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("AudioMonitor stopped")

    # ── Internal loop ─────────────────────────────────────────────────────────

    def _loop(self):
        while self._running:
            audio_buffer = np.zeros(CHUNK_SAMPLES, dtype=np.float32)

            try:
                self._capture_mic(audio_buffer)
            except Exception as e:
                logger.error(f"Mic capture failed: {e}")
                audio_buffer[:] = 0
                time.sleep(1)
                continue

            # Score -- buffer zeroed inside predict_distress() after scoring
            score = predict_distress(audio_buffer, sample_rate=SAMPLE_RATE)
            logger.debug(f"Distress score: {score:.1f}")

            now = time.time()

            # Expire stale confirmation window
            if self._window.is_expired(now):
                logger.info("Confirmation window expired -- resetting")
                self._window.reset()

            if score >= DISTRESS_THRESHOLD:
                self._handle_hit(score, now)
            else:
                if self._window.hit_count == 0:
                    # No active window -- sleep to save battery
                    time.sleep(SLEEP_BETWEEN_SEC)
                # If window is active, keep listening without sleep

    # ── Mic capture ───────────────────────────────────────────────────────────

    def _capture_mic(self, buffer: np.ndarray):
        """
        Fill buffer with one second of 16kHz mono mic audio (in-place).

        Platform bridge -- replace this body for mobile:
          Android:      JNI -> AudioRecord (16kHz, CHANNEL_IN_MONO, PCM_FLOAT)
          iOS/Flutter:  MethodChannel -> AVAudioEngine (16kHz mono)
          Desktop/test: sounddevice (pip install sounddevice)
        """
        try:
            import sounddevice as sd
            recording = sd.rec(
                CHUNK_SAMPLES,
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocking=True,
            )
            buffer[:] = recording[:, 0]
        except ImportError:
            logger.debug("sounddevice not available -- injecting silence")
            buffer[:] = 0.0

    # ── Confirmation window ───────────────────────────────────────────────────

    def _handle_hit(self, score: float, now: float):
        self._window.add(score, now)
        logger.info(
            f"Hit {self._window.hit_count}/{CONFIRM_HITS_NEEDED} -- "
            f"score {score:.1f} | "
            f"avg {self._window.average_confidence:.1f} | "
            f"peak {self._window.peak_confidence:.1f}"
        )
        if self._window.hit_count >= CONFIRM_HITS_NEEDED:
            self._fire_sos()

    def _fire_sos(self):
        event = SOSEvent(
            hit_count          = self._window.hit_count,
            average_confidence = self._window.average_confidence,
            peak_confidence    = self._window.peak_confidence,
            scores             = list(self._window.hits),
        )
        self._window.reset()

        # Context override -- sensor fusion hook
        if self._context_override is not None:
            allow = self._context_override(event)
            if not allow:
                logger.info(
                    f"SOS suppressed by context_override "
                    f"(avg={event.average_confidence:.1f}, urgency={event.urgency})"
                )
                return

        logger.warning(
            f"DISTRESS CONFIRMED -- urgency={event.urgency} | "
            f"avg={event.average_confidence:.1f} | "
            f"peak={event.peak_confidence:.1f} | "
            f"scores={event.scores}"
        )
        self._on_sos_trigger(event)

    # ── Default SOS handler ───────────────────────────────────────────────────

    @staticmethod
    def _default_sos_handler(event: SOSEvent):
        """
        Fallback -- logs the SOS event.
        Replace with real alert logic:
          - Send GPS + alert to trusted contacts
          - Upload audio evidence to cloud
          - Call 112 if urgency == HIGH
        """
        logger.critical(
            f"[SOS] urgency={event.urgency} | "
            f"hits={event.hit_count} | "
            f"avg={event.average_confidence:.1f} | "
            f"peak={event.peak_confidence:.1f} | "
            f"scores={event.scores}"
        )


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    def my_sos(event: SOSEvent):
        print(f"\n SOS TRIGGERED")
        print(f"   Urgency  : {event.urgency}")
        print(f"   Hits     : {event.hit_count}")
        print(f"   Avg score: {event.average_confidence:.1f}")
        print(f"   Peak     : {event.peak_confidence:.1f}")
        print(f"   Scores   : {event.scores}\n")

    def cinema_override(event: SOSEvent) -> bool:
        """Example: suppress LOW/MEDIUM alerts in known safe venues."""
        is_cinema = False  # replace with real location check
        if is_cinema and event.urgency != "HIGH":
            print("   [override] Suppressed -- cinema venue detected")
            return False
        return True

    monitor = AudioMonitor(on_sos_trigger=my_sos, context_override=cinema_override)
    monitor.start()

    print("Monitoring for 30 seconds -- Press Ctrl+C to stop.")
    try:
        time.sleep(30)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop()