"""
SafeHer — Confidence Scorer V2

Formula:
    confidence = (0.5 × audio) + (0.3 × movement) + (0.1 × night) + (0.1 × isolated)

Escalation stages:
    0–39   → nothing
    40–59  → silent vibration (low suspicion)
    60–79  → 30s confirmation window
    80–100 → immediate SOS + GPS stream

Confidence decay:
    Call tick_decay() every few seconds when no new signals arrive.
    Prevents a stale audio spike from keeping the score elevated.

V3 (post-data):
    Replace rule engine with a trained classifier once you have
    500+ panic and 500+ normal labelled samples.
    Inputs: audio_score, movement_score, is_night, is_isolated
    Outputs: safe / suspicious / emergency
"""

import time
from datetime import datetime


# ── Tier boundaries ───────────────────────────────────────────────────────────

TIER_SILENT_VIBRATION = 40    # low suspicion  — gentle haptic, no UI
TIER_CONFIRM_30S      = 60    # suspicious     — vibrate, 30 s cancel window
TIER_IMMEDIATE_SOS    = 80    # emergency      — fire immediately + GPS stream


# ── Audio tier weights ────────────────────────────────────────────────────────
# A 61% audio score and a 99% audio score are NOT the same threat.
# Tiers prevent low-confidence audio from inflating the final score.
#
# !! TUNE TIER BOUNDARIES once you have labelled audio data !!
# Current hypothesis based on YAMNet distress outputs in noisy Indian environments.

def _audio_contribution(audio_score: float) -> float:
    """
    Tiered audio contribution (0–50 pts).

    ≥ 90  → 50 pts  (very high confidence — screaming, unmistakable)
    ≥ 75  → 40 pts  (high confidence)
    ≥ 60  → 25 pts  (moderate — possible false positive in crowded areas)
    < 60  → 0 pts   (below noise floor — ignore)
    """
    if audio_score >= 90:
        return 50.0
    elif audio_score >= 75:
        return 40.0
    elif audio_score >= 60:
        return 25.0
    return 0.0


# ── Movement tier weights ─────────────────────────────────────────────────────
# Same logic — a 61% movement score (mild erratic motion) ≠ 99% (full panic).

def _movement_contribution(movement_score: float) -> float:
    """
    Tiered movement contribution (0–40 pts).

    ≥ 90  → 40 pts  (very high — intense struggle or panic run)
    ≥ 75  → 30 pts  (high — clear erratic movement)
    ≥ 60  → 20 pts  (moderate — could be vehicle vibration, dancing, etc.)
    < 60  → 0 pts   (below noise floor — ignore)

    Note: inference.py already suppresses jogging to 15, so it never
    reaches the 60 threshold here. Vehicle/bus vibration testing needed
    before V2 — see FUTURE WORK below.
    """
    if movement_score >= 90:
        return 40.0
    elif movement_score >= 75:
        return 30.0
    elif movement_score >= 60:
        return 20.0
    return 0.0


# ── Main scorer ───────────────────────────────────────────────────────────────

def compute_confidence_score(
    audio_score: float = 0.0,
    movement_score: float = 0.0,
    heart_rate_spike: bool = False,
    is_night: bool = None,
    is_isolated: bool = False,
) -> dict:
    """
    Compute SafeHer confidence score from sensor signals.

    Formula (weighted sum, max 100):
        audio        → up to 50 pts  (tiered, 0.5 weight)
        movement     → up to 40 pts  (tiered, 0.3 weight + fall bonus)
        heart rate   → 30 pts fixed  (binary wearable signal, V3)
        night        → 10 pts        (context amplifier)
        isolated     → 10 pts        (context amplifier)

    Returns dict with total_score, action, activate_gps_stream, and
    all input signals for logging / sensor fusion.
    """

    score = 0.0

    # Primary signals
    score += _audio_contribution(audio_score)
    score += _movement_contribution(movement_score)

    if heart_rate_spike:
        score += 30.0    # Strong physiological signal (V3 wearable)

    # Context amplifiers
    if is_night is None:
        hour = datetime.now().hour
        is_night = (hour >= 22 or hour <= 5)

    if is_night:
        score += 10.0
    if is_isolated:
        score += 10.0

    score = min(score, 100.0)

    # Escalation decision
    if score >= TIER_IMMEDIATE_SOS:
        action             = "fire_immediately"
        activate_gps_stream = True
    elif score >= TIER_CONFIRM_30S:
        action             = "confirm_30s"
        activate_gps_stream = False
    elif score >= TIER_SILENT_VIBRATION:
        action             = "silent_vibration"
        activate_gps_stream = False
    else:
        action             = "nothing"
        activate_gps_stream = False

    return {
        "total_score":         round(score, 1),
        "action":              action,
        "activate_gps_stream": activate_gps_stream,
        "audio_score":         audio_score,
        "movement_score":      movement_score,
        "heart_rate_spike":    heart_rate_spike,
        "is_night":            is_night,
        "is_isolated":         is_isolated,
    }


# ── Confidence decay ──────────────────────────────────────────────────────────
#
# Problem: an audio spike at T=0 that doesn't repeat should not keep the
# score elevated at T=30s. Decay prevents a stale event from looking current.
#
# Usage (call from your sensor fusion loop every few seconds):
#
#     state = {"score": 0.0, "last_update": time.time()}
#
#     # When new sensor data arrives:
#     result = compute_confidence_score(audio_score=..., movement_score=...)
#     state["score"] = result["total_score"]
#     state["last_update"] = time.time()
#
#     # Every 3 seconds with no new data:
#     state["score"] = tick_decay(state["score"])
#
# !! TUNE decay_rate per environment !!
# 0.9 = 10% drop per tick. At 3s ticks: score halves in ~20 seconds.
# May need to lower to 0.85 in noisy environments (quicker reset).

DECAY_RATE    = 0.9       # multiplier applied each tick
DECAY_FLOOR   = 0.0       # score never goes below this from decay alone
DECAY_MIN_GAP = 3.0       # seconds between decay ticks (caller enforces this)


def tick_decay(current_score: float, decay_rate: float = DECAY_RATE) -> float:
    """
    Apply one decay tick to current_score.
    Call this every DECAY_MIN_GAP seconds when no new sensor signal has arrived.

    Returns new (lower) score, floored at DECAY_FLOOR.
    """
    decayed = current_score * decay_rate
    return max(round(decayed, 1), DECAY_FLOOR)


# ── FUTURE WORK ───────────────────────────────────────────────────────────────
#
# Movement model gaps (address before V2 launch):
#   1. Fall detection — many emergencies start with a sudden fall.
#      Add a fall_detected: bool input; give it 25 pts (between movement tiers).
#
#   2. Vehicle detection — bus/auto/train vibration looks like moderate movement.
#      Record vehicle profiles (bus, auto-rickshaw, train) and subtract baseline.
#      Until then, movement_score from a vehicle may contribute false 20 pts.
#
#   3. Phone position — front pocket, handbag, hand-held all shift accelerometer
#      axes. Collect position labels in the data collection app.
#
# ML replacement (after 500+ labelled samples):
#   inputs  = [audio_score, movement_score, is_night, is_isolated]
#   outputs = [safe, suspicious, emergency]
#   Replace compute_confidence_score() body; keep the same return dict shape
#   so callers need no changes.
#
# Priority order (per product spec):
#   1. Data collection app + movement dataset
#   2. Confidence scorer V2 (this file) ← you are here
#   3. Fall detection
#   4. Vehicle detection
#   5. ML replacement scorer