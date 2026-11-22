"""Processing time of the detection service per step and model, on replayed HDFS / BGL test windows.

Times every step separately, in milliseconds per window:
- Drain parsing (per line, assign_cluster on test lines from the replay producer)
- encoding the window into a count vector
- each model, scoring windows one at a time (batch 1, as for live windows) and in batches of 500
  (as the service does when many windows close at once, e.g. at the end of an HDFS replay)
- the explanation of one alert (SHAP for Random Forest alerts, count deviation for the other models)
"""

import itertools
import time

import numpy as np
import pandas as pd

from src.models.unsupervised import time_split
from src.streaming.common import ROOT, assign_cluster, parse_bgl, parse_hdfs
from src.streaming.packs import Pack
from src.streaming.replay import bgl_lines, hdfs_lines

PROCESSED = ROOT / "data" / "processed"


def test_windows(name, n, seed=42):
    """n test-set event sequences (last 30%), sampled at random."""
    order_col = "order" if name == "hdfs" else "window"
    _, test = time_split(pd.read_parquet(PROCESSED / f"{name}_sequences.parquet"), 0.7, order_col)
    return [list(s) for s in test["EventSequence"].sample(n, random_state=seed)]


def parse_time(pack, name, n_lines=20000):
    """Milliseconds per line for parsing + Drain matching (test lines, in replay order)."""
    if name == "hdfs":
        lines = list(itertools.islice(hdfs_lines(), n_lines))
        parse = lambda line: parse_hdfs(line)[1]
    else:
        lines = list(itertools.islice(bgl_lines()[1], n_lines))
        parse = lambda line: parse_bgl(line)[1]
    start = time.perf_counter()
    for line in lines:
        content = parse(line)
        if content is not None:
            assign_cluster(pack.miner, content)
    return (time.perf_counter() - start) / len(lines) * 1000


def model_times(pack, windows, batch_size):
    """Milliseconds per window for encoding and each model, scoring `windows` in batches of batch_size."""
    timings = {}
    for i in range(0, len(windows), batch_size):
        pack.score_batch(windows[i : i + batch_size], timings=timings)
    return {step: seconds / len(windows) * 1000 for step, seconds in timings.items()}


def explanation_times(pack, windows, per_model=20):
    """Milliseconds per alert for the explanation, grouped by the model the alert names."""
    scored = pack.score_batch(windows)
    by_model = {}
    for i, (verdicts, x, unseen) in enumerate(scored):
        flagged = [m for m in ["Random Forest", "LSTM", "PCA", "Isolation Forest"] if verdicts.get(m, {}).get("flagged")]
        if flagged and len(by_model.setdefault(flagged[0], [])) < per_model:
            by_model[flagged[0]].append((i, verdicts, x, unseen))
    out = {}
    for model, items in by_model.items():
        start = time.perf_counter()
        for i, verdicts, x, unseen in items:
            pack.explain(i, windows[i], verdicts, x, unseen)
        out[model] = (time.perf_counter() - start) / len(items) * 1000, len(items)
    return out


def processing_times(names=("hdfs", "bgl"), n_windows=2000, batch_sizes=(1, 500), n_lines=20000):
    """One row per dataset, step and batch size: ms per window (per line for parsing, per alert for explanations)."""
    rows = []
    for name in names:
        pack = Pack.load(name)
        windows = test_windows(name, n_windows)
        mean_lines = float(np.mean([len(w) for w in windows]))
        rows.append({"dataset": name.upper(), "step": "Drain parsing", "batch_size": None, "unit": "per line",
                     "ms": parse_time(pack, name, n_lines), "n": n_lines})
        for batch_size in batch_sizes:
            for step, ms in model_times(pack, windows, batch_size).items():
                rows.append({"dataset": name.upper(), "step": step, "batch_size": batch_size, "unit": "per window",
                             "ms": ms, "n": len(windows)})
        for model, (ms, n) in explanation_times(pack, windows).items():
            rows.append({"dataset": name.upper(), "step": f"explanation ({model} alert)", "batch_size": 1,
                         "unit": "per alert", "ms": ms, "n": n})
        for row in rows:
            row.setdefault("mean_lines_per_window", round(mean_lines, 1))
    return pd.DataFrame(rows)
