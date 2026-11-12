"""DeepLog-style LSTM (Du et al., 2017): predict the next event from the previous h events."""

import copy
import time

import numpy as np
import pandas as pd
import torch
from torch import nn

PAD = 0


def build_vocab(event_ids):
    """Map event IDs ('E1', 'E2', ...) to integers 1..n; 0 is the padding index."""
    return {e: i for i, e in enumerate(sorted(event_ids, key=lambda e: int(e[1:])), start=1)}


def make_windows(sequences, vocab, h=10):
    """Sliding windows over each sequence: the previous h events (left-padded) predict the next one.

    Returns X (n, h), y (n,) and the index of the sequence each window came from.
    """
    X, y, seq_idx = [], [], []
    for i, seq in enumerate(sequences):
        ids = np.array([vocab[e] for e in seq], dtype=np.int64)
        if len(ids) < 2:
            continue
        padded = np.concatenate([np.full(h, PAD, dtype=np.int64), ids])
        X.append(np.lib.stride_tricks.sliding_window_view(padded, h)[1 : len(ids)])
        y.append(ids[1:])
        seq_idx.append(np.full(len(ids) - 1, i))
    return torch.from_numpy(np.concatenate(X)), torch.from_numpy(np.concatenate(y)), np.concatenate(seq_idx)


class DeepLogLSTM(nn.Module):
    def __init__(self, num_events, embed_dim=32, hidden_size=64, num_layers=2):
        super().__init__()
        self.embed = nn.Embedding(num_events + 1, embed_dim, padding_idx=PAD)
        self.lstm = nn.LSTM(embed_dim, hidden_size, num_layers, batch_first=True)
        self.out = nn.Linear(hidden_size, num_events + 1)

    def forward(self, x):
        output, _ = self.lstm(self.embed(x))
        return self.out(output[:, -1])


def _mean_loss(model, X, y, loss_fn, batch_size):
    model.eval()
    with torch.no_grad():
        total = sum(loss_fn(model(X[i : i + batch_size]), y[i : i + batch_size]).item() * len(y[i : i + batch_size])
                    for i in range(0, len(y), batch_size))
    return total / len(y)


def train(model, X_train, y_train, X_val, y_val, epochs=30, patience=3, batch_size=512, lr=1e-3, seed=42):
    """Adam + cross-entropy with early stopping on validation loss; restores the best weights.

    Returns (history DataFrame, training seconds).
    """
    torch.manual_seed(seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss()
    history, best_loss, best_state, bad_epochs = [], float("inf"), None, 0

    start = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        for batch in torch.randperm(len(y_train)).split(batch_size):
            optimizer.zero_grad()
            loss_fn(model(X_train[batch]), y_train[batch]).backward()
            optimizer.step()

        train_loss = _mean_loss(model, X_train, y_train, loss_fn, 4096)
        val_loss = _mean_loss(model, X_val, y_val, loss_fn, 4096)
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})
        print(f"epoch {epoch:2d}  train loss {train_loss:.4f}  val loss {val_loss:.4f}")

        if val_loss < best_loss:
            best_loss, best_state, bad_epochs = val_loss, copy.deepcopy(model.state_dict()), 0
        else:
            bad_epochs += 1
            if bad_epochs >= patience:
                print(f"early stopping after epoch {epoch}")
                break

    model.load_state_dict(best_state)
    return pd.DataFrame(history), time.perf_counter() - start


def next_event_ranks(model, sequences, vocab, h=10, batch_size=4096):
    """Rank of each true next event among the model's predictions (0 = top-1), plus the sequence it belongs to."""
    X, y, seq_idx = make_windows(sequences, vocab, h)
    model.eval()
    ranks = []
    with torch.no_grad():
        for i in range(0, len(y), batch_size):
            logits = model(X[i : i + batch_size])
            target = logits.gather(1, y[i : i + batch_size, None])
            ranks.append((logits > target).sum(dim=1).numpy())  # events scored above the true one
    return np.concatenate(ranks), seq_idx


def flag(sequences, ranks, seq_idx, known_events, k):
    """Anomalous if any event is outside the top-k predictions or not in known_events."""
    pred = np.array([any(e not in known_events for e in seq) for seq in sequences])
    pred[seq_idx[ranks >= k]] = True
    return pred.astype(int)


def detect(model, sequences, vocab, train_events, k, h=10, batch_size=4096):
    """Flag a sequence if any event is outside the model's top-k predictions or was never seen in training."""
    ranks, seq_idx = next_event_ranks(model, sequences, vocab, h, batch_size)
    return flag(sequences, ranks, seq_idx, train_events, k)
