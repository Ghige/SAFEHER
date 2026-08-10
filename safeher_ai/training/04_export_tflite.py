"""
SafeHer — Step 4: Export to TFLite
=====================================

Converts the trained classifier → TFLite for on-device inference.

UPDATED for the embedding-based training pipeline (02_train_model.py):
the saved .keras file is now just the small classifier head (embedding
in, score out). The Android app's inference.py calls the TFLite model
with raw audio in and a score out, so this script rebuilds that full
pipeline as a single graph:

    raw waveform (1, 16000)
        ↓
    YAMNet backbone (frozen)
        ↓
    embeddings, mean-pooled over frames → (1, 1024)
        ↓
    trained classifier head
        ↓
    distress score (1, 1)

That combined graph — not the classifier alone — is what gets converted
to TFLite, using a tf.Module wrapping YAMNet + classifier under a
tf.function with a fixed input signature (batch size 1, matching how
inference.py feeds one chunk at a time).

Outputs:
  models/final/yamnet_distress.tflite        → copy this to app/ai/audio_model/
  models/final/yamnet_distress_quant.tflite  → smaller/faster, best-effort

Run AFTER 02_train_model.py (03_evaluate_model.py is optional first):
    python 04_export_tflite.py --model models/final/safeher_classifier_YYYYMMDD_HHMM.keras
"""

import argparse
import random
import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
from pathlib import Path

SAMPLE_RATE   = 16000
CHUNK_SAMPLES = SAMPLE_RATE
FINAL_DIR     = Path("models/final")

YAMNET_URL = "https://tfhub.dev/google/yamnet/1"


# ── Combined inference module (YAMNet + classifier, one graph) ────────────────

class SafeHerInferenceModel(tf.Module):
    """
    Wraps the frozen YAMNet backbone and the trained classifier head into
    a single callable: raw waveform in, distress score out.

    Fixed batch size of 1 — matches how the Android app feeds one 1-second
    chunk at a time (see inference.py / verify_tflite below).
    """

    def __init__(self, classifier: tf.keras.Model):
        super().__init__()
        self.yamnet = hub.load(YAMNET_URL)
        self.classifier = classifier

    @tf.function(input_signature=[tf.TensorSpec([1, CHUNK_SAMPLES], tf.float32)])
    def __call__(self, waveform):
        # YAMNet expects a single 1-D waveform, not a batch — squeeze the
        # fixed batch-of-1 dimension before calling it.
        wf = tf.reshape(waveform, [CHUNK_SAMPLES])
        _, embeddings, _ = self.yamnet(wf)          # (frames, 1024)
        embedding = tf.reduce_mean(embeddings, axis=0)  # (1024,)
        embedding = tf.expand_dims(embedding, 0)        # (1, 1024)
        score = self.classifier(embedding)              # (1, 1)
        return score


def representative_dataset():
    """
    Feed the quantizer real audio samples so it can calibrate the integer
    quantization accurately.
    Reads from data/processed/distress/ and data/processed/normal/
    """
    all_wavs = (
        list(Path("data/processed/distress").glob("*.wav"))[:50] +
        list(Path("data/processed/normal").glob("*.wav"))[:50]
    )
    random.shuffle(all_wavs)

    for wav_path in all_wavs[:100]:
        try:
            audio = tf.io.read_file(str(wav_path))
            audio, _ = tf.audio.decode_wav(audio, desired_channels=1)
            audio = tf.squeeze(audio, axis=-1)
            audio = tf.cast(audio, tf.float32)
            if audio.shape[0] < CHUNK_SAMPLES:
                audio = tf.pad(audio, [[0, CHUNK_SAMPLES - audio.shape[0]]])
            else:
                audio = audio[:CHUNK_SAMPLES]
            audio = tf.expand_dims(audio, 0)  # (1, 16000)
            yield [audio]
        except Exception:
            continue


def export_float32(inference_model: SafeHerInferenceModel, out_path: Path):
    """Standard TFLite conversion — larger but exact precision."""
    print("  Converting float32 TFLite...")
    concrete_fn = inference_model.__call__.get_concrete_function()
    converter = tf.lite.TFLiteConverter.from_concrete_functions(
        [concrete_fn], inference_model
    )
    tflite_model = converter.convert()
    out_path.write_bytes(tflite_model)
    size_kb = len(tflite_model) / 1024
    print(f"  ✅ Saved: {out_path}  ({size_kb:.0f} KB)")
    return size_kb


def export_quantized(inference_model: SafeHerInferenceModel, out_path: Path):
    """
    INT8-where-possible quantized TFLite — smaller/faster on most Android
    devices. Note: YAMNet's internal ops (STFT/mel-spectrogram) don't all
    have pure INT8 kernels, so this allows falling back to select TF ops
    for those; if that still fails, the float32 model is used instead.
    """
    print("  Converting quantized TFLite (this can take a few minutes)...")
    concrete_fn = inference_model.__call__.get_concrete_function()
    converter = tf.lite.TFLiteConverter.from_concrete_functions(
        [concrete_fn], inference_model
    )
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_dataset
    # Prefer full INT8, but allow falling back to TF ops for anything in
    # YAMNet's spectrogram pipeline that doesn't have an INT8 kernel.
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS_INT8,
        tf.lite.OpsSet.SELECT_TF_OPS,
    ]
    converter.inference_input_type  = tf.float32
    converter.inference_output_type = tf.float32

    try:
        tflite_quant = converter.convert()
        out_path.write_bytes(tflite_quant)
        size_kb = len(tflite_quant) / 1024
        print(f"  ✅ Saved: {out_path}  ({size_kb:.0f} KB)")
        return size_kb
    except Exception as e:
        print(f"  ⚠️  Quantization failed: {e}")
        print("  Using float32 version instead.")
        return None


def verify_tflite(tflite_path: Path):
    """
    Quick sanity check — run 1 second of silence through the TFLite model
    and confirm it outputs a value between 0 and 1.
    """
    print(f"\n  Verifying {tflite_path.name}...")
    interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
    interpreter.allocate_tensors()

    input_details  = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    dummy = np.zeros((1, CHUNK_SAMPLES), dtype=np.float32)
    interpreter.set_tensor(input_details[0]["index"], dummy)
    interpreter.invoke()
    output = interpreter.get_tensor(output_details[0]["index"])
    score  = float(output[0][0]) * 100

    print(f"  Input shape  : {input_details[0]['shape']}")
    print(f"  Output shape : {output_details[0]['shape']}")
    print(f"  Silence score: {score:.1f} (should be close to 0)")

    if score > 30:
        print("  ⚠️  Silence scores high — check model quality")
    else:
        print("  ✅ Model verified — ready for deployment")

    return score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Path to .keras classifier (from 02_train_model.py)")
    args = parser.parse_args()

    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 55)
    print("  SafeHer — TFLite Export")
    print("=" * 55)

    print(f"\n  Loading classifier: {args.model}")
    classifier = tf.keras.models.load_model(args.model)

    print("  Loading YAMNet backbone and building combined graph...")
    inference_model = SafeHerInferenceModel(classifier)

    # Float32 version
    float_path = FINAL_DIR / "yamnet_distress.tflite"
    float_size = export_float32(inference_model, float_path)

    # Quantized version (best-effort)
    quant_path = FINAL_DIR / "yamnet_distress_quant.tflite"
    quant_size = export_quantized(inference_model, quant_path)

    # Verify both
    verify_tflite(float_path)
    if quant_path.exists():
        verify_tflite(quant_path)

    # Instructions
    print("\n" + "=" * 55)
    print("  NEXT STEPS")
    print("=" * 55)
    print()

    if quant_path.exists() and quant_size:
        reduction = (1 - quant_size / float_size) * 100
        print(f"  Quantized model is {reduction:.0f}% smaller than float32.")
        print(f"  Recommended for production if verification above looked good.")
        print()
        print(f"  Copy to your app:")
        print(f"  cp {quant_path} app/ai/audio_model/yamnet_distress.tflite")
    else:
        print(f"  Copy to your app:")
        print(f"  cp {float_path} app/ai/audio_model/yamnet_distress.tflite")

    print()
    print("  In inference.py, the model is already loaded from:")
    print("  MODEL_PATH = os.path.join(os.path.dirname(__file__), 'yamnet_distress.tflite')")
    print()
    print("  No other code changes needed — the pipeline is complete. ✅")
    print("=" * 55)


if __name__ == "__main__":
    main()