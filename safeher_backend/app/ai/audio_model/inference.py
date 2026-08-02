import logging
import os
import numpy as np

logger = logging.getLogger(__name__)

# Load TFLite model once at startup
_interpreter = None
MODEL_PATH = os.path.join(os.path.dirname(__file__), "yamnet_distress_quant.tflite")

# Score threshold for "this is distress" — single source of truth.
# Evaluation (03_evaluate_model.py) recommended 60 over the old default of 50.
# Import this constant from callers (e.g. audio_moniter.py) instead of
# hardcoding the number again, so it can't drift out of sync.
DISTRESS_THRESHOLD = 60.0

EXPECTED_SAMPLES = 16000   # 1 second @ 16kHz — must match training pipeline

# Below this mean absolute amplitude, treat the chunk as silence and skip
# inference entirely. Same floor used in 01_prepare_dataset.py's
# SILENCE_THRESHOLD, kept in sync here for consistency.
SILENCE_THRESHOLD = 0.005


def _load_model():
    global _interpreter

    if _interpreter is not None:
        return _interpreter

    try:
        try:
            import tflite_runtime.interpreter as tflite
            logger.info("Using tflite_runtime")
        except ImportError:
            import tensorflow.lite as tflite
            logger.info("Using TensorFlow Lite")

        _interpreter = tflite.Interpreter(model_path=MODEL_PATH)
        _interpreter.allocate_tensors()

    except Exception as e:
        logger.error(f"Failed to load TFLite model: {e}")
        _interpreter = "mock"

    return _interpreter


def predict_distress(audio_chunk: np.ndarray, sample_rate: int = 16000) -> float:
    """
    Run distress detection on a 1-second audio chunk.

    The audio buffer is explicitly zeroed after scoring so that if the
    score is below the threshold the caller can discard it immediately —
    nothing persists in RAM beyond this function call.

    Args:
        audio_chunk: numpy array of audio samples (mono, 16kHz, 16000 samples)
        sample_rate: audio sample rate (default 16000)

    Returns:
        confidence score 0.0 to 100.0
        (compare against DISTRESS_THRESHOLD, currently 60.0)
    """
    if len(audio_chunk) != EXPECTED_SAMPLES:
        logger.error(f"Invalid audio length: {len(audio_chunk)} (expected {EXPECTED_SAMPLES})")
        audio_chunk[:] = 0
        return 0.0

    # Skip inference on near-silent chunks — saves CPU/battery, and the
    # model has nothing meaningful to score anyway.
    if np.mean(np.abs(audio_chunk)) < SILENCE_THRESHOLD:
        audio_chunk[:] = 0
        return 0.0

    interpreter = _load_model()

    if interpreter == "mock":
        # Mock for development — returns 0 (no distress)
        audio_chunk[:] = 0
        return 0.0

    try:
        input_details  = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        # Normalize to [-1.0, 1.0] float32.
        # np.max(np.abs(...)) instead of plain .max() — catches waveforms
        # that are entirely negative, which .max() alone would miss.
        audio_norm = audio_chunk.astype(np.float32)
        if np.max(np.abs(audio_norm)) > 1.0:
            audio_norm = audio_norm / 32768.0

        interpreter.set_tensor(input_details[0]["index"], audio_norm.reshape(1, -1))
        interpreter.invoke()

        output = interpreter.get_tensor(output_details[0]["index"])
        print("=" * 50)
        print("Output Shape:", output.shape)
        print("Raw Output:", output)

        # IMPORTANT: the exported model (04_export_tflite.py) combines YAMNet
        # with a single-sigmoid classifier head, not a 2-class softmax.
        # Output shape is (1, 1) — one distress probability, not
        # [normal_prob, distress_prob]. There is no class index to select.
        # (If you're still using an older 2-class softmax .tflite, this
        # line needs to go back to output[0][1] * 100 instead.)
        distress_score = float(output[0][0]) * 100.0

        logger.debug(f"Distress score: {distress_score:.1f} (threshold: {DISTRESS_THRESHOLD})")
        return min(distress_score, 100.0)

    except Exception as e:
        logger.error(f"Audio inference error: {e}")
        return 0.0

    finally:
        # Always zero the raw buffer after scoring.
        # If score is low, caller discards the chunk; nothing is retained in RAM.
        audio_chunk[:] = 0