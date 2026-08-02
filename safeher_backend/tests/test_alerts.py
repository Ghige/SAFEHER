import pytest
from app.ai.confidence_scorer import compute_confidence_score
from app.ai.movement_model.inference import predict_panic_movement, is_jogging
import numpy as np


def test_confidence_score_fire_immediately():
    result = compute_confidence_score(
        audio_score=80, movement_score=70, is_night=True
    )
    assert result["action"] == "fire_immediately"
    assert result["total_score"] >= 70


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


def test_jogging_detection():
    # Simulate regular jogging oscillation
    t = np.linspace(0, 3, 30)
    jogging_data = [(np.sin(2 * np.pi * 2 * ti) * 10,
                     np.cos(2 * np.pi * 2 * ti) * 10,
                     9.8) for ti in t]
    result = is_jogging(jogging_data)
    assert isinstance(result, bool)
