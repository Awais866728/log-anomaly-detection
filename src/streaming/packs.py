"""Model packs for the detection service: everything needed to score one source's windows.

A pack holds the Drain parser state, the event columns, the fitted detectors with their thresholds, the event
counts of normal training windows, and (replay) the Random Forest used for SHAP explanations.

- Replay packs (HDFS, BGL): built from the offline training data with the validation-chosen settings
  (fit on the first 60%, chosen on the next 10%, as in notebooks 14-16). The Drain state is rebuilt by parsing
  the full log exactly as in training, so template ids match the model columns.
- Unlabelled replay packs (OpenSSH, Apache): no labels, so PCA, Isolation Forest and LSTM fitted on the first 70%
  of windows (all assumed normal, as in notebooks 14 and 16), with the settings chosen on BGL
  (docs/cross_system_results.csv); no Random Forest.
- Live packs (one per Docker service): Drain, PCA, Isolation Forest and LSTM trained on normal logs collected
  with scripts/collect_logs.py, in 1-minute windows. No labels, so no Random Forest; fixed thresholds.

Build:  python -m src.streaming.packs replay        (HDFS and BGL, about 10 minutes)
        python -m src.streaming.packs replay --datasets OpenSSH Apache
        python -m src.streaming.packs live --label normal
"""

import argparse
import time

import joblib
import numpy as np
import pandas as pd
import torch

from src.features.bgl_features import BGL_DIR, parse_bgl
from src.features.hdfs_features import HDFS_DIR, parse_hdfs_blocks
from src.features.time_windows import FILE_PREFIX, LOG_PATHS, WINDOWING, parse_timed_log
from src.models.lstm import DeepLogLSTM, build_vocab, evenly_spaced, fit_lstm, known_events, next_event_ranks, sweep_k
from src.models.supervised import explain_alert, select_rf_method
from src.models.unsupervised import (IForestDetector, PCADetector, pick_best, time_split, time_split_val,
                                     unseen_columns, validated_sweeps)
from src.parsing.drain_parser import DrainParser
from src.streaming.common import LIVE_SERVICES, MODELS, ROOT, parse_live, split_docker_line
from src.streaming.windows import TimeWindows

PROCESSED = ROOT / "data" / "processed"
LIVE_DIR = ROOT / "data" / "raw" / "live"
PERCENTILES = [90, 95, 97.5, 99, 99.5]
KS = [1, 2, 3, 5, 9, 12]
H = 10
LIVE_PERCENTILE, LIVE_K = 99, 9  # no labels on the live services, so fixed settings
MIN_WINDOWS = {"PCA": 5, "Isolation Forest": 5, "LSTM": 10}  # fewer normal windows: model not trained
MODEL_ORDER = ["Random Forest", "LSTM", "PCA", "Isolation Forest"]  # which flagging model an alert names


def pack_path(name):
    return MODELS / f"stream_{name}.joblib"


# ---------------------------------------------------------------- building


def _lstm_train_scores(model, sequences, vocab, known, k):
    """Share of predicted events outside the top k, per training sequence (for the score percentile)."""
    ranks, seq_idx = next_event_ranks(model, sequences, vocab, H)
    return np.sort(_miss_share(sequences, ranks, seq_idx, known, k))


def _miss_share(sequences, ranks, seq_idx, known, k):
    """Per sequence: share of positions 1..n-1 whose (seen) event is outside the top k; unseen targets are skipped."""
    starts = np.searchsorted(seq_idx, np.arange(len(sequences)))
    out = np.zeros(len(sequences))
    for i, seq in enumerate(sequences):
        if len(seq) < 2:
            continue
        r = ranks[starts[i] : starts[i] + len(seq) - 1]
        target_known = np.array([e in known for e in seq[1:]])
        if target_known.any():
            out[i] = (r[target_known] >= k).mean()
    return out


def build_replay_pack(dataset):
    """HDFS or BGL pack with the validation-chosen settings."""
    start = time.perf_counter()
    prefix, order_col = {"HDFS": ("hdfs", "order"), "BGL": ("bgl", "window")}[dataset]
    print(f"{dataset}: rebuilding the Drain state from the full log ...", flush=True)
    if dataset == "HDFS":
        _, parser, _, _ = parse_hdfs_blocks(HDFS_DIR / "HDFS.log")
    else:
        _, _, _, parser, _ = parse_bgl(BGL_DIR / "BGL.log")
    templates = pd.read_csv(PROCESSED / f"{prefix}_templates.csv").set_index("EventId")["template"]
    assert parser.num_templates == len(templates.drop("E0", errors="ignore")), "Drain state differs from training"

    counts = pd.read_parquet(PROCESSED / f"{prefix}_counts.parquet")
    event_cols = list(counts.filter(regex=r"^E\d+$").columns)
    fit, _, _ = time_split_val(counts, order_col=order_col)
    X_normal = fit.loc[fit["Label"] == 0, event_cols].to_numpy()
    unseen = unseen_columns(X_normal)

    print(f"{dataset}: PCA and Isolation Forest, percentile chosen on validation ...", flush=True)
    detectors = {"PCA": PCADetector(variance=0.95), "Isolation Forest": IForestDetector(max_samples=1.0)}
    val_t, test_t = validated_sweeps(counts, detectors, PERCENTILES, order_col)  # fits the detectors in place
    chosen = pick_best(val_t, test_t).set_index("model")
    packed = {}
    for name, det in detectors.items():
        # the stream zeroes never-seen-in-normal events before scoring (they give "New template" warnings);
        # those columns are 0 in every normal training row, so the training scores are unchanged
        scores, p = det.score(X_normal), float(chosen.loc[name, "percentile"])
        packed[name] = {"model": det, "percentile": p, "threshold": float(np.percentile(scores, p)),
                        "train_scores": np.sort(scores), "zero_unseen": True}

    print(f"{dataset}: Random Forest, method chosen on validation ...", flush=True)
    rf = select_rf_method(counts, order_col=order_col)
    packed["Random Forest"] = {"model": rf["model"], "method": rf["method"], "threshold": 0.5, "zero_unseen": False}
    background = fit[event_cols].sample(100, random_state=42) if dataset == "BGL" else None

    print(f"{dataset}: LSTM from models/{prefix}_lstm_fit60.pt, k chosen on validation ...", flush=True)
    saved = torch.load(MODELS / f"{prefix}_lstm_fit60.pt")
    lstm = DeepLogLSTM(num_events=len(saved["vocab"]), **{k: v for k, v in saved["config"].items() if k != "h"})
    lstm.load_state_dict(saved["state_dict"])
    sequences = pd.read_parquet(PROCESSED / f"{prefix}_sequences.parquet")
    s_fit, s_val, _ = time_split_val(sequences, order_col=order_col)
    train_seqs = evenly_spaced(s_fit.loc[s_fit["Label"] == 0, "EventSequence"].tolist(), 20000)
    known = set(saved["train_events"])
    sweep, *_ = sweep_k(lstm, s_val["EventSequence"].tolist(), saved["vocab"], known, KS, s_val["Label"].to_numpy(), H)
    k = int(sweep.loc[sweep["f1"].idxmax(), "k"])
    packed["LSTM"] = {"state_dict": saved["state_dict"], "config": saved["config"], "vocab": saved["vocab"],
                      "known": known, "k": k, "train_scores": _lstm_train_scores(lstm, train_seqs, saved["vocab"], known, k)}

    pack = {"name": prefix, "dataset": dataset, "mode": "replay", "parser": parser.miner, "event_cols": event_cols,
            "templates": templates.to_dict(), "normal_mean": X_normal.mean(axis=0), "unseen": unseen,
            "detectors": packed, "background": background,
            "settings": {name: (f"percentile {d['percentile']:g}" if "percentile" in d else
                                f"k {d['k']}" if "k" in d else f"method {d['method']}") for name, d in packed.items()}}
    joblib.dump(pack, pack_path(prefix))
    print(f"{dataset}: saved {pack_path(prefix).relative_to(ROOT)}  settings {pack['settings']}  "
          f"({time.perf_counter() - start:.0f} s)", flush=True)


UNLABELLED_SETTINGS_FROM = "BGL"  # their percentile / k: the ones chosen on this labelled dataset
SEED = 42


def build_unlabelled_pack(dataset):
    """OpenSSH or Apache pack: no labels, models fitted on the first 70% of windows (as in notebooks 14 and 16)."""
    start = time.perf_counter()
    prefix = FILE_PREFIX[dataset]
    print(f"{dataset}: rebuilding the Drain state from the full log ...", flush=True)
    _, _, parser, *_ = parse_timed_log(LOG_PATHS[dataset], dataset)
    templates = pd.read_csv(PROCESSED / f"{prefix}_templates.csv").set_index("EventId")["template"]
    assert parser.num_templates == len(templates), "Drain state differs from training"

    counts = pd.read_parquet(PROCESSED / f"{prefix}_counts.parquet")
    event_cols = list(counts.filter(regex=r"^E\d+$").columns)
    train, _ = time_split(counts, 0.7, "window")
    X_train = train[event_cols].to_numpy()
    unseen = unseen_columns(X_train)
    cross = pd.read_csv(ROOT / "docs" / "cross_system_results.csv")
    setting = cross[(cross["dataset"] == dataset) & (cross["chosen on"] == UNLABELLED_SETTINGS_FROM)].set_index("model")["setting"]

    packed = {}
    for name, det in {"PCA": PCADetector(variance=0.95), "Isolation Forest": IForestDetector(max_samples=1.0)}.items():
        det.fit(X_train)
        scores, p = det.score(X_train), float(setting[name].split()[-1])
        packed[name] = {"model": det, "percentile": p, "threshold": float(np.percentile(scores, p)),
                        "train_scores": np.sort(scores), "zero_unseen": True}

    print(f"{dataset}: LSTM on the first 70% of windows ...", flush=True)
    sequences = pd.read_parquet(PROCESSED / f"{prefix}_sequences.parquet")
    s_train, _ = time_split(sequences, 0.7, "window")
    train_seqs = [list(s) for s in s_train["EventSequence"]]
    vocab = build_vocab(templates.index)
    config = {"embed_dim": 32, "hidden_size": 64, "num_layers": 2}
    model, _, _ = fit_lstm(train_seqs, vocab, H, SEED, model_config=config)
    known, k = known_events(train_seqs, 1), int(setting["LSTM"].split()[-1])
    packed["LSTM"] = {"state_dict": model.state_dict(), "config": {"h": H, **config}, "vocab": vocab, "known": known,
                      "k": k, "train_scores": _lstm_train_scores(model, evenly_spaced(train_seqs, 20000), vocab, known, k)}

    kind, size = WINDOWING[dataset]
    pack = {"name": prefix, "dataset": dataset, "mode": "replay", "parser": parser.miner, "event_cols": event_cols,
            "templates": templates.to_dict(), "normal_mean": X_train.mean(axis=0), "unseen": unseen,
            "detectors": packed, "background": None, "labelled": False, "settings_from": UNLABELLED_SETTINGS_FROM,
            "train_windows": len(train), "window": f"{size} s" if kind == "time" else f"{size} lines",
            "settings": {name: (f"percentile {d['percentile']:g}" if "percentile" in d else f"k {d['k']}")
                         for name, d in packed.items()}}
    joblib.dump(pack, pack_path(prefix))
    print(f"{dataset}: saved {pack_path(prefix).relative_to(ROOT)}  settings {pack['settings']} (chosen on "
          f"{UNLABELLED_SETTINGS_FROM})  ({time.perf_counter() - start:.0f} s)", flush=True)


def live_windows(service, path):
    """Parse a collected service log (lines with Docker timestamps) into 1-minute windows; returns (parser, windows)."""
    parser = DrainParser("OpenSSH" if service == "ssh" else service)  # nginx/app: HTTP status masks, sim 0.7
    windower, windows = TimeWindows(service), []
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, raw in enumerate(f):
            ts, message = split_docker_line(raw.rstrip("\n"))
            if ts is None or not message.strip():
                continue
            content, _ = parse_live(service, message)
            cid = parser.parse(content)[0]
            windows += windower.add(f"E{cid}", str(i), message, ts, ts)
    return parser, windows + windower.flush()


def build_live_pack(service, label="normal"):
    path = LIVE_DIR / f"{service}_{label}.log"
    parser, windows = live_windows(service, path)
    event_cols = [f"E{c.cluster_id}" for c in parser.miner.drain.clusters]
    index = {e: i for i, e in enumerate(event_cols)}
    X = np.zeros((len(windows), len(event_cols)))
    for row, w in enumerate(windows):
        for e in w.events:
            X[row, index[e]] += 1
    sequences = [w.events for w in windows]

    packed = {}
    if len(windows) >= MIN_WINDOWS["PCA"]:
        for name, det in {"PCA": PCADetector(variance=0.95), "Isolation Forest": IForestDetector(max_samples=1.0)}.items():
            det.fit(X)
            scores = det.score(X)
            packed[name] = {"model": det, "percentile": LIVE_PERCENTILE, "threshold": float(np.percentile(scores, LIVE_PERCENTILE)),
                            "train_scores": np.sort(scores), "zero_unseen": True}
    if len(windows) >= MIN_WINDOWS["LSTM"]:
        vocab = build_vocab(event_cols)
        config = {"embed_dim": 32, "hidden_size": 64, "num_layers": 2}
        model, history, _ = fit_lstm(sequences, vocab, H, 42, model_config=config)
        known = known_events(sequences, 1)
        packed["LSTM"] = {"state_dict": model.state_dict(), "config": {"h": H, **config}, "vocab": vocab, "known": known,
                          "k": LIVE_K, "train_scores": _lstm_train_scores(model, sequences, vocab, known, LIVE_K)}
    pack = {"name": service, "dataset": service, "mode": "live", "parser": parser.miner, "event_cols": event_cols,
            "templates": {f"E{c.cluster_id}": c.get_template() for c in parser.miner.drain.clusters},
            "normal_mean": X.mean(axis=0) if len(windows) else np.zeros(len(event_cols)),
            "unseen": np.zeros(len(event_cols), dtype=bool), "detectors": packed, "background": None,
            "settings": {name: (f"percentile {d['percentile']:g}" if "percentile" in d else f"k {d['k']}") for name, d in packed.items()},
            "train_windows": len(windows)}
    joblib.dump(pack, pack_path(service))
    lines = sum(w.n_lines for w in windows)
    print(f"{service:9s} {lines:6,} lines, {len(windows):3d} windows, {len(event_cols):3d} templates, "
          f"models: {', '.join(packed) or 'none (too few windows, new-template warnings only)'}")


# ---------------------------------------------------------------- scoring


class Pack:
    """A loaded pack: encodes, scores and explains closed windows."""

    def __init__(self, data):
        self.__dict__.update(data)
        self.miner = data["parser"]
        self.col_index = {e: i for i, e in enumerate(self.event_cols)}
        # events seen in normal training windows; live columns are all from normal logs
        self.normal_seen = {e for e, u in zip(self.event_cols, self.unseen) if not u}
        self.zero_mask = np.asarray(self.unseen, dtype=bool)
        for d in self.detectors.values():  # one window at a time: a thread pool per call only adds overhead
            model = getattr(d.get("model"), "model", d.get("model"))
            if hasattr(model, "n_jobs"):
                model.n_jobs = 1
        self.lstm = None
        if "LSTM" in self.detectors:
            d = self.detectors["LSTM"]
            self.lstm = DeepLogLSTM(num_events=len(d["vocab"]), **{k: v for k, v in d["config"].items() if k != "h"})
            self.lstm.load_state_dict(d["state_dict"])
            self.lstm.eval()

    @classmethod
    def load(cls, name):
        return cls(joblib.load(pack_path(name)))

    def template(self, event):
        if event in self.templates:
            return self.templates[event]
        if event == "E0":
            return "UNPARSED"
        cluster = self.miner.drain.id_to_cluster.get(int(event[1:]))
        return cluster.get_template() if cluster else event

    def encode(self, events):
        """Count vector over the model columns, and the window's events never seen in normal training (in order)."""
        x = np.zeros(len(self.event_cols))
        for e in events:
            if e in self.col_index:
                x[self.col_index[e]] += 1
        unseen = [e for e in dict.fromkeys(events) if e not in self.normal_seen]
        return x, unseen

    def score(self, events):
        """{model: {"flagged", "score", "probability"}} plus the count vector and unseen events, for one window."""
        return self.score_batch([events])[0]

    def score_batch(self, windows, timings=None):
        """score() for several windows at once: one model call per detector instead of one per window.

        timings: optional dict; the seconds spent per step ("encode" and each model) are added to it.
        """
        clock = time.perf_counter()
        encoded = [self.encode(events) for events in windows]
        X = np.array([x for x, _ in encoded]).reshape(len(windows), len(self.event_cols))
        X_zeroed = np.where(self.zero_mask, 0, X)  # unseen events count only towards "New template"
        verdicts = [{} for _ in windows]
        if timings is not None:
            timings["encode"] = timings.get("encode", 0.0) + time.perf_counter() - clock
        for name, d in self.detectors.items():
            clock = time.perf_counter()
            self._score_model(name, d, windows, X, X_zeroed, verdicts)
            if timings is not None:
                timings[name] = timings.get(name, 0.0) + time.perf_counter() - clock
        return [(v, x, unseen) for v, (x, unseen) in zip(verdicts, encoded)]

    def _score_model(self, name, d, windows, X, X_zeroed, verdicts):
        """One detector's verdicts for a batch, written into verdicts[i][name]."""
        if name == "LSTM":
            for i, events in enumerate(windows):
                seq = [e for e in events if e in d["vocab"]]
                s = 0.0
                if len(seq) >= 2:
                    ranks, seq_idx = next_event_ranks(self.lstm, [seq], d["vocab"], H)
                    s = float(_miss_share([seq], ranks, seq_idx, d["known"], d["k"])[0])
                verdicts[i][name] = {"flagged": s > 0, "score": s, "probability": self._percentile(d, s)}
        elif name == "Random Forest":
            proba = d["model"].predict_proba(pd.DataFrame(X, columns=self.event_cols))[:, 1]
            for i, p in enumerate(proba):
                verdicts[i][name] = {"flagged": bool(p >= 0.5), "score": float(p), "probability": float(p)}
        else:
            scores = d["model"].score(X_zeroed if d["zero_unseen"] else X)
            for i, s in enumerate(scores):
                verdicts[i][name] = {"flagged": bool(s > d["threshold"]), "score": float(s),
                                     "probability": self._percentile(d, float(s))}

    @staticmethod
    def _percentile(d, s):
        """Share of normal training windows scoring below s: the 'anomaly probability' of a detector without one."""
        return float(np.searchsorted(d["train_scores"], s, side="right") / max(len(d["train_scores"]), 1))

    def explain(self, window_id, events, verdicts, x, unseen):
        """explain_alert-style dict for a window, or None if nothing flags it.

        level "Alert": a model flags the window; level "New template": the only reason is an event never seen in
        normal training. Events with count 0 are expected-but-missing events (SHAP or count deviation).
        """
        flagged = [m for m in MODEL_ORDER if verdicts.get(m, {}).get("flagged")]
        if not flagged and not unseen:
            return None
        level = "Alert" if flagged else "New template"
        model = flagged[0] if flagged else None
        rf = self.detectors.get("Random Forest")
        x_df = pd.DataFrame([x], columns=self.event_cols)
        base = None
        if rf is not None and (model == "Random Forest" or not flagged):
            try:  # Taimoor's explain_alert: SHAP for Random Forest flags, unseen templates otherwise
                base = explain_alert(rf["model"], x_df, window_id, self.dataset, self.event_cols, self.templates,
                                     self.unseen, model_name="Random Forest", background=self.background)
            except ValueError:  # the unseen events are brand-new templates, not model columns
                base = None
        if base is None:
            base = {"window_id": window_id, "dataset": self.dataset, "model": model or "unseen-event rule",
                    "anomaly_probability": round(verdicts[model]["probability"], 4) if model else 1.0,
                    "reason": "model" if flagged else "unseen event",
                    "top_events": self._deviation_events(x) if flagged else []}
        if unseen:  # also list every unseen template (brand-new ones included): often the actual cause
            listed = {e["event"] for e in base["top_events"]}
            counts = pd.Series(events).value_counts()
            base["top_events"] += [{"event": e, "template": self.template(e), "count": int(counts[e]), "shap": None,
                                    "unseen": True} for e in unseen if e not in listed]
        if not flagged:
            base["model"] = "unseen-event rule"
        elif model != "Random Forest":
            base["model"], base["anomaly_probability"] = model, round(verdicts[model]["probability"], 4)
        for e in base["top_events"]:
            i = self.col_index.get(e["event"])
            e["normal_count"] = round(float(self.normal_mean[i]), 2) if i is not None else 0.0
            e["missing"] = e["count"] == 0
            e.setdefault("unseen", e["event"] not in self.normal_seen)
        base.update(level=level, flagged_by=flagged, unseen_events=unseen,
                    setting=self.settings.get(model) if model else None,
                    scores={m: {"flagged": bool(v["flagged"]), "score": round(v["score"], 4)} for m, v in verdicts.items()})
        return base

    def _deviation_events(self, x, n=3):
        """Top n events by |count - normal mean|, for models without SHAP; shap is None."""
        diff = np.abs(x - self.normal_mean)
        top = np.argsort(-diff, kind="stable")[:n]
        return [{"event": self.event_cols[i], "template": self.template(self.event_cols[i]), "count": int(x[i]),
                 "shap": None} for i in top if diff[i] > 0]


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    replay = sub.add_parser("replay")
    replay.add_argument("--datasets", nargs="+", default=["HDFS", "BGL"], choices=["HDFS", "BGL", "OpenSSH", "Apache"])
    live = sub.add_parser("live")
    live.add_argument("--label", default="normal")
    args = parser.parse_args()
    MODELS.mkdir(exist_ok=True)
    if args.mode == "replay":
        for dataset in args.datasets:
            if dataset in FILE_PREFIX:
                build_unlabelled_pack(dataset)
            else:
                build_replay_pack(dataset)
    else:
        for service in LIVE_SERVICES:
            build_live_pack(service, args.label)


if __name__ == "__main__":
    main()
