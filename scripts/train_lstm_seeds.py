"""Train the DeepLog LSTM with several random seeds (HDFS and BGL), for notebook 22.

The reported configuration of notebook 16: 20,000 normal sequences of the first 60% (time order), spaced evenly;
same model and training settings. Only the seed changes. Before each run, random, numpy and torch are seeded;
fit_lstm also uses the seed for the 10% early-stopping hold-out, the weight initialisation and the batch shuffling.
Saves models/<prefix>_lstm_seed<seed>.pt with the training history; notebook 22 chooses k and tests.

    python -u scripts/train_lstm_seeds.py > lstm_seeds.log 2>&1      # CPU: about 30 minutes
"""

import argparse
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.lstm import build_vocab, evenly_spaced, fit_lstm, known_events  # noqa: E402
from src.models.unsupervised import time_split_val  # noqa: E402

PROCESSED, MODELS = ROOT / "data" / "processed", ROOT / "models"
H, N_TRAIN = 10, 20_000
MODEL_CONFIG = {"embed_dim": 32, "hidden_size": 64, "num_layers": 2}  # as in notebook 16
LABELLED = {"HDFS": ("hdfs", "order"), "BGL": ("bgl", "window")}
SEEDS = [42, 7, 123]  # as in the Isolation Forest and Random Forest seed studies (notebooks 20, 21)


def model_path(prefix, seed):
    return MODELS / f"{prefix}_lstm_seed{seed}.pt"


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets", nargs="+", default=list(LABELLED), choices=list(LABELLED))
    parser.add_argument("--seeds", nargs="+", type=int, default=SEEDS)
    args = parser.parse_args()
    MODELS.mkdir(exist_ok=True)
    for name in args.datasets:
        prefix, order_col = LABELLED[name]
        sequences = pd.read_parquet(PROCESSED / f"{prefix}_sequences.parquet")
        fit, _, _ = time_split_val(sequences, order_col=order_col)
        train_seqs = evenly_spaced(fit.loc[fit["Label"] == 0, "EventSequence"].tolist(), N_TRAIN)
        vocab = build_vocab(pd.read_csv(PROCESSED / f"{prefix}_templates.csv")["EventId"])
        known = known_events(train_seqs, 1)
        for seed in args.seeds:
            print(f"{time.strftime('%H:%M:%S')} {name} seed {seed}: {len(train_seqs):,} training sequences", flush=True)
            set_seed(seed)
            model, history, seconds = fit_lstm(train_seqs, vocab, H, seed, model_config=MODEL_CONFIG)
            torch.save({"state_dict": model.state_dict(), "vocab": vocab, "train_events": sorted(known),
                        "config": {"h": H, **MODEL_CONFIG}, "seed": seed, "train_sequences": len(train_seqs),
                        "epochs": len(history), "history": history, "train_seconds": seconds}, model_path(prefix, seed))
            print(f"{time.strftime('%H:%M:%S')} {name} seed {seed}: {len(history)} epochs, {seconds:.0f} s; "
                  f"saved {model_path(prefix, seed).relative_to(ROOT)}", flush=True)
    print(f"{time.strftime('%H:%M:%S')} done", flush=True)


if __name__ == "__main__":
    main()
