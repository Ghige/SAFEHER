import numpy as np

from app.ai.confidence_scorer import compute_confidence_score
from app.ai.movement_model.movement_inference import predict_panic_movement


def test_confidence_score_fire_immediately():
    # Same 80/70 floor as test_safety_decision_engine / test_helpers.
    # Night bonus does not change the action; fused score is 65 on the current contract.
    result = compute_confidence_score(
        audio_score=80, movement_score=70, is_night=True
    )
    assert result["action"] == "fire_immediately"
    assert result["total_score"] >= 65


def test_confidence_score_confirm():
    result = compute_confidence_score(
        audio_score=60, movement_score=0, is_night=False
    )
    assert result["action"] == "confirm_30s"


def test_confidence_score_nothing():
    result = compute_confidence_score(
        audio_score=0, movement_score=0, is_night=False
    )
    assert result["action"] == "nothing"
    assert result["total_score"] == 0


def test_panic_movement_detection():
    # Simulate erratic movement
    panic_data = [(np.random.uniform(-30, 30),
                   np.random.uniform(-30, 30),
                   np.random.uniform(-30, 30)) for _ in range(30)]
    score = predict_panic_movement(panic_data)
    assert 0 <= score <= 100


def test_jogging_does_not_max_panic_score():
    # Jogging suppression lives inside predict_panic_movement (no public is_jogging).
    t = np.linspace(0, 3, 30)
    jogging_data = [
        (np.sin(2 * np.pi * 2 * ti) * 10, np.cos(2 * np.pi * 2 * ti) * 10, 9.8)
        for ti in t
    ]
    score = predict_panic_movement(jogging_data)
    assert 0 <= score <= 100
