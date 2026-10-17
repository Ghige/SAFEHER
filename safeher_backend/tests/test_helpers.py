import pytest
from app.services.location_service import haversine_distance
from app.ai.confidence_scorer import compute_confidence_score


def test_haversine_same_point():
    """Distance between same point should be 0."""
    dist = haversine_distance(19.0760, 72.8777, 19.0760, 72.8777)
    assert dist == 0.0


def test_haversine_known_distance():
    """These two Greater Mumbai points are ~16.1 km apart (standard haversine)."""
    dist = haversine_distance(19.0760, 72.8777, 19.1974, 72.9615)
    assert 15000 < dist < 18000


def test_haversine_500m():
    """Two points ~500m apart should return ~500."""
    # Approx 500m north of Mumbai CST
    dist = haversine_distance(18.9398, 72.8355, 18.9443, 72.8355)
    assert 400 < dist < 600


def test_confidence_night_bonus():
    """Night context should increase score vs day (small SDE bonus)."""
    day = compute_confidence_score(audio_score=0, movement_score=0, is_night=False)
    night = compute_confidence_score(audio_score=0, movement_score=0, is_night=True)
    assert night["total_score"] >= day["total_score"]


def test_confidence_isolated_bonus():
    """Isolated location should increase score vs baseline."""
    base = compute_confidence_score(audio_score=0, movement_score=0, is_night=False, is_isolated=False)
    result = compute_confidence_score(
        audio_score=0, movement_score=0,
        is_night=False, is_isolated=True
    )
    assert result["total_score"] >= base["total_score"]


def test_confidence_full_score():
    """Strong multi-signal = fire immediately."""
    result = compute_confidence_score(
        audio_score=80,
        movement_score=80,
        heart_rate_spike=True,
        is_night=True,
        is_isolated=True
    )
    assert result["action"] == "fire_immediately"
    assert result["total_score"] >= 65


def test_confidence_thresholds():
    """Legacy audio floors still map to confirm / fire."""
    assert compute_confidence_score(0, 0, is_night=False)["action"] == "nothing"
    assert compute_confidence_score(60, 0, is_night=False)["action"] == "confirm_30s"
    assert compute_confidence_score(80, 70, is_night=False)["action"] == "fire_immediately"


def test_movement_only_does_not_fire():
    result = compute_confidence_score(audio_score=0, movement_score=95, is_night=False)
    assert result["action"] != "fire_immediately"
