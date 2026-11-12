"""Fixed-window event sequences and count vectors for the full BGL dataset."""

import time
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from src.parsing.drain_parser import DrainParser, extract_content

ROOT = Path(__file__).resolve().parents[2]
BGL_DIR = ROOT / "data" / "raw" / "BGL"
PROCESSED = ROOT / "data" / "processed"

EMPTY_MESSAGE = "EMPTY_MESSAGE"  # event text for lines with only the 9 header fields


def parse_bgl(log_path, use_dataset_masks=True):
    """Parse the log line by line; return per-line cluster ids, alert flags, timestamps, the parser and line counts."""
    parser = DrainParser("BGL", use_dataset_masks=use_dataset_masks)
    cluster_ids, alerts, timestamps = [], [], []
    line_counts = {"unparsed": 0, "empty_message": 0, "empty_message_alerts": 0}
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in tqdm(f, desc="Parsing BGL.log", unit=" lines", mininterval=30):
            if not line.strip():
                continue
            fields = line.split(maxsplit=2)
            is_alert = fields[0] != "-"
            content = extract_content(line, "BGL")
            if content is None and len(line.split()) == 9:
                content = EMPTY_MESSAGE  # header only: parsed as its own event
                line_counts["empty_message"] += 1
                line_counts["empty_message_alerts"] += is_alert
            if content is None:
                line_counts["unparsed"] += 1
                cluster_ids.append(0)  # E0 = line that doesn't fit the BGL format
            else:
                cluster_ids.append(parser.parse(content)[0])
            alerts.append(is_alert)
            timestamps.append(int(fields[1]) if len(fields) > 1 and fields[1].isdigit() else -1)
    return cluster_ids, alerts, timestamps, parser, line_counts


def make_windows(cluster_ids, alerts, timestamps, num_events, window_size=20):
    """Cut the lines in order into windows of window_size; a final partial window is dropped."""
    n = len(cluster_ids) // window_size * window_size
    ids = np.asarray(cluster_ids[:n]).reshape(-1, window_size)
    labels = np.asarray(alerts[:n]).reshape(-1, window_size).any(axis=1).astype(int)
    windows = np.arange(len(ids))

    names = np.array([f"E{i}" for i in range(num_events + 1)])
    sequences = pd.DataFrame({
        "window": windows,
        "start_time": np.asarray(timestamps[:n]).reshape(-1, window_size)[:, 0],
        "EventSequence": names[ids].tolist(),
        "Label": labels,
    })

    counts = np.zeros((len(ids), num_events + 1), dtype=np.uint8)  # at most 20 per window
    np.add.at(counts, (np.repeat(windows, window_size), ids.ravel()), 1)
    keep = [0] * bool(counts[:, 0].any()) + list(range(1, num_events + 1))  # E0 only if unparsed lines exist
    counts = pd.concat([sequences[["window", "start_time", "Label"]],
                        pd.DataFrame(counts[:, keep], columns=names[keep])], axis=1)
    return sequences, counts


def build_bgl(log_path=BGL_DIR / "BGL.log", window_size=20, use_dataset_masks=True, save=True):
    """Build (and save) the window tables; use_dataset_masks=False uses the shared masks only (the old setup)."""
    start = time.perf_counter()
    cluster_ids, alerts, timestamps, parser, line_counts = parse_bgl(log_path, use_dataset_masks)
    parse_seconds = time.perf_counter() - start

    sequences, counts = make_windows(cluster_ids, alerts, timestamps, parser.num_templates, window_size)

    clusters = parser.miner.drain.clusters
    templates = pd.DataFrame({"EventId": [f"E{c.cluster_id}" for c in clusters],
                              "template": [c.get_template() for c in clusters]})
    if line_counts["unparsed"]:
        templates = pd.concat([pd.DataFrame({"EventId": ["E0"], "template": ["UNPARSED"]}), templates])

    if save:
        PROCESSED.mkdir(parents=True, exist_ok=True)
        sequences.to_parquet(PROCESSED / "bgl_sequences.parquet", index=False)
        counts.to_parquet(PROCESSED / "bgl_counts.parquet", index=False)
        templates.to_csv(PROCESSED / "bgl_templates.csv", index=False)

    ts = np.asarray(timestamps)
    stats = {
        "lines": len(cluster_ids),
        "unparsed_lines": line_counts["unparsed"],
        "empty_message_lines": line_counts["empty_message"],
        "empty_message_alerts": line_counts["empty_message_alerts"],
        "alert_lines": int(sum(alerts)),
        "templates": parser.num_templates,
        "windows": len(sequences),
        "anomalous_windows": int(sequences["Label"].sum()),
        "dropped_tail_lines": len(cluster_ids) - len(sequences) * window_size,
        "out_of_order_lines": int((ts[1:] < np.maximum.accumulate(ts)[:-1]).sum()),
        "parse_seconds": parse_seconds,
        "total_seconds": time.perf_counter() - start,
    }
    return sequences, counts, stats
