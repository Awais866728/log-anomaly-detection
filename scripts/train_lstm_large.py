"""Train the DeepLog LSTM on a larger training sample (HDFS and BGL), for notebook 19.

Same protocol as notebook 16; only the number of training sequences changes (default 100,000 instead of 20,000):
normal sequences of the first 60% (time order), spaced evenly; same model, training settings and seed.
Saves models/<prefix>_lstm_large<N/1000>k.pt with the training history; notebook 19 chooses k and tests.

    python -u scripts/train_lstm_large.py > lstm_large.log 2>&1      # CPU: takes about an hour
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.lstm import build_vocab, evenly_spaced, fit_lstm, known_events  # noqa: E402
from src.models.unsupervised import time_split_val  # noqa: E402

PROCESSED, MODELS = ROOT / "data" / "processed", ROOT / "models"
H, SEED = 10, 42
MODEL_CONFIG = {"embed_dim": 32, "hidden_size": 64, "num_layers": 2}  # as in notebook 16
LABELLED = {"HDFS": ("hdfs", "order"), "BGL": ("bgl", "window")}


def model_path(prefix, n_train):
    return MODELS / f"{prefix}_lstm_large{n_train // 1000}k.pt"


def train(name, n_train):
    prefix, order_col = LABELLED[name]
    sequences = pd.read_parquet(PROCESSED / f"{prefix}_sequences.parquet")
    fit, _, _ = time_split_val(sequences, order_col=order_col)
    normal = fit.loc[fit["Label"] == 0, "EventSequence"].tolist()
    train_seqs = evenly_spaced(normal, n_train)
    templates = pd.read_csv(PROCESSED / f"{prefix}_templates.csv")["EventId"]
    vocab = build_vocab(templates)
    print(f"{time.strftime('%H:%M:%S')} {name}: {len(train_seqs):,} of {len(normal):,} normal fit sequences", flush=True)

    model, history, seconds = fit_lstm(train_seqs, vocab, H, SEED, model_config=MODEL_CONFIG)
    known = known_events(train_seqs, 1)
    MODELS.mkdir(exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "vocab": vocab, "train_events": sorted(known),
                "config": {"h": H, **MODEL_CONFIG}, "train_sequences": len(train_seqs), "epochs": len(history),
                "history": history, "train_seconds": seconds}, model_path(prefix, n_train))
    print(f"{time.strftime('%H:%M:%S')} {name}: {len(history)} epochs, {seconds:.0f} s, "
          f"{len(known)} of {len(vocab)} event types seen; saved {model_path(prefix, n_train).relative_to(ROOT)}",
          flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets", nargs="+", default=list(LABELLED), choices=list(LABELLED))
    parser.add_argument("--n-train", type=int, default=100_000)
    args = parser.parse_args()
    for name in args.datasets:
        train(name, args.n_train)
    print(f"{time.strftime('%H:%M:%S')} done", flush=True)


if __name__ == "__main__":
    main()
