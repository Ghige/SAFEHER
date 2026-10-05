import numpy as np
import pandas as pd
import tensorflow as tf
import tensorflow_hub as hub
from pathlib import Path
from tqdm import tqdm
import soundfile as sf

SAMPLE_RATE = 16000
EMBED_DIM = 1024

SPLITS_ROOT = Path("safeher_ai/data/splits_v2")
OUTPUT_ROOT = Path("safeher_ai/data/embeddings_v2")

YAMNET_URL = "https://tfhub.dev/google/yamnet/1"


def load_wav(path):
    audio, sr = sf.read(path, dtype="float32")

    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    if sr != SAMPLE_RATE:
        raise ValueError(
            f"Unexpected sample rate {sr} in {path}. Expected {SAMPLE_RATE}."
        )

    if len(audio) != SAMPLE_RATE:
        raise ValueError(
            f"Unexpected length {len(audio)} in {path}. Expected {SAMPLE_RATE}."
        )

    return audio.astype(np.float32)


def create_embeddings(split_name, yamnet):
    csv_path = SPLITS_ROOT / f"{split_name}.csv"
    out_path = OUTPUT_ROOT / f"{split_name}.npz"

    df = pd.read_csv(csv_path)

    print("\n" + "=" * 60)
    print(f"Creating embeddings: {split_name}")
    print("=" * 60)
    print("Samples:", len(df))

    X = np.zeros((len(df), EMBED_DIM), dtype=np.float32)
    y = df["label"].to_numpy(dtype=np.int32)

    for i, row in enumerate(tqdm(df.itertuples(index=False), total=len(df))):
        wav_path = Path(row.filepath)

        # YAMNet returns embeddings for multiple ~0.96s frames.
        waveform = load_wav(wav_path)

        _, embeddings, _ = yamnet(waveform)

        # Mean-pool the frame embeddings into one 1024-D vector.
        embedding = tf.reduce_mean(embeddings, axis=0).numpy()

        if embedding.shape != (EMBED_DIM,):
            raise ValueError(
                f"Unexpected embedding shape {embedding.shape} for {wav_path}"
            )

        X[i] = embedding

    np.savez_compressed(out_path, X=X, y=y)

    print(f"Saved: {out_path}")
    print("X shape:", X.shape)
    print("y shape:", y.shape)
    print("Distress:", int((y == 1).sum()))
    print("Normal:", int((y == 0).sum()))


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("SafeHer — V2 YAMNet Embedding Generation")
    print("=" * 60)
    print("Loading YAMNet...")

    yamnet = hub.load(YAMNET_URL)

    print("✅ YAMNet loaded successfully")

    for split in ["train", "val", "test"]:
        create_embeddings(split, yamnet)

    print("\n" + "=" * 60)
    print("✅ ALL V2 EMBEDDINGS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
