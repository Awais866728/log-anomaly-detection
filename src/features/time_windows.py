"""Window event sequences and count vectors for the full OpenSSH (1-minute windows) and Apache (20-line windows) datasets."""

import re
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from src.features.bgl_features import make_windows
from src.parsing.drain_parser import DrainParser, extract_content

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

LOG_PATHS = {"OpenSSH": RAW / "OpenSSH" / "SSH.log", "Apache": RAW / "Apache" / "Apache.log"}
FILE_PREFIX = {"OpenSSH": "openssh", "Apache": "apache"}
# ("time", seconds) = fixed time windows; ("lines", n) = fixed windows of n lines in file order, as for BGL
WINDOWING = {"OpenSSH": ("time", 60), "Apache": ("lines", 20)}

# Apache.log has lines with only this text (no timestamp or level); they get the previous line's timestamp.
APACHE_HEADERLESS = "script not found or unable to stat"

# OpenSSH lines have no year. Placeholder start year: only the time between lines matters for windowing.
OPENSSH_START_YEAR = 2000

TIMESTAMP_RE = {
    # Dec 10 06:55:46 LabSZ sshd[24200]: ...
    "OpenSSH": re.compile(r"^(\w{3})\s+(\d{1,2}) (\d{2}):(\d{2}):(\d{2})\s"),
    # [Sun Dec 04 04:47:44 2005] [notice] ...
    "Apache": re.compile(r"^\[\w{3} (\w{3}) (\d{2}) (\d{2}):(\d{2}):(\d{2}) (\d{4})\]"),
}
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


class Timestamps:
    """Parse line timestamps to Unix seconds (UTC); for OpenSSH, add a year when the month goes back (Dec -> Jan)."""

    def __init__(self, dataset):
        self.dataset = dataset
        self.year, self.last_month = OPENSSH_START_YEAR, None

    def __call__(self, line):
        match = TIMESTAMP_RE[self.dataset].match(line)
        if match is None:
            return None
        if self.dataset == "Apache":
            month, day, hh, mm, ss, year = match.groups()
        else:
            month, day, hh, mm, ss = match.groups()
            if self.last_month is not None and MONTHS[month] < self.last_month:
                self.year += 1
            self.last_month, year = MONTHS[month], self.year
        dt = datetime(int(year), MONTHS[month], int(day), int(hh), int(mm), int(ss), tzinfo=timezone.utc)
        return int(dt.timestamp())


def parse_timed_log(log_path, dataset):
    """Parse the log line by line; return per-line cluster ids and timestamps, the parser and the unparsed count.

    Apache's headerless APACHE_HEADERLESS lines are kept with the previous line's timestamp;
    any other line without a timestamp or message is skipped.
    """
    parser = DrainParser(dataset)
    to_seconds = Timestamps(dataset)
    cluster_ids, timestamps = [], []
    n_lines = n_unparsed = n_headerless = 0
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in tqdm(f, desc=f"Parsing {Path(log_path).name}", unit=" lines", mininterval=30):
            if not line.strip():
                continue
            n_lines += 1
            content, ts = extract_content(line, dataset), to_seconds(line)
            if dataset == "Apache" and line.strip() == APACHE_HEADERLESS and timestamps:
                content, ts = APACHE_HEADERLESS, timestamps[-1]
                n_headerless += 1
            if content is None or ts is None:
                n_unparsed += 1
                continue
            cluster_ids.append(parser.parse(content)[0])
            timestamps.append(ts)
    return cluster_ids, timestamps, parser, n_lines, n_unparsed, n_headerless


def make_time_windows(cluster_ids, timestamps, num_events, window_seconds=60):
    """Group lines into fixed, non-overlapping time windows; empty windows are dropped.

    Windows are in time order; lines keep their file order inside a window.
    """
    ids, ts = np.asarray(cluster_ids), np.asarray(timestamps)
    starts = ts // window_seconds * window_seconds
    order = np.argsort(starts, kind="stable")
    ids, starts = ids[order], starts[order]
    window_starts, window_idx = np.unique(starts, return_inverse=True)

    names = np.array([f"E{i}" for i in range(num_events + 1)])
    splits = np.flatnonzero(np.diff(window_idx)) + 1
    sequences = pd.DataFrame({
        "window": np.arange(len(window_starts)),
        "start_time": window_starts,
        "EventSequence": [names[part].tolist() for part in np.split(ids, splits)],
    })

    counts = np.zeros((len(window_starts), num_events + 1), dtype=np.uint32)
    np.add.at(counts, (window_idx, ids), 1)
    counts = pd.concat([sequences[["window", "start_time"]],
                        pd.DataFrame(counts[:, 1:], columns=names[1:])], axis=1)  # cluster ids start at 1
    return sequences, counts


def make_line_windows(cluster_ids, timestamps, num_events, window_size=20):
    """BGL-style windows of window_size lines in file order; the last partial window is dropped. No labels."""
    sequences, counts = make_windows(cluster_ids, [False] * len(cluster_ids), timestamps, num_events, window_size)
    return sequences.drop(columns="Label"), counts.drop(columns="Label")


def build_windows(dataset, log_path=None, save=True):
    """Build (and save) <prefix>_sequences.parquet, <prefix>_counts.parquet and <prefix>_templates.csv.

    The window type and size come from WINDOWING.
    """
    start = time.perf_counter()
    cluster_ids, timestamps, parser, n_lines, n_unparsed, n_headerless = parse_timed_log(
        log_path or LOG_PATHS[dataset], dataset)
    parse_seconds = time.perf_counter() - start

    kind, size = WINDOWING[dataset]
    if kind == "time":
        sequences, counts = make_time_windows(cluster_ids, timestamps, parser.num_templates, size)
    else:
        sequences, counts = make_line_windows(cluster_ids, timestamps, parser.num_templates, size)

    clusters = parser.miner.drain.clusters
    templates = pd.DataFrame({"EventId": [f"E{c.cluster_id}" for c in clusters],
                              "template": [c.get_template() for c in clusters]})

    if save:
        prefix = FILE_PREFIX[dataset]
        PROCESSED.mkdir(parents=True, exist_ok=True)
        sequences.to_parquet(PROCESSED / f"{prefix}_sequences.parquet", index=False)
        counts.to_parquet(PROCESSED / f"{prefix}_counts.parquet", index=False)
        templates.to_csv(PROCESSED / f"{prefix}_templates.csv", index=False)

    ts = np.asarray(timestamps)
    lengths = sequences["EventSequence"].str.len()
    stats = {
        "window": f"{size} s" if kind == "time" else f"{size} lines",
        "lines": n_lines,
        "unparsed_lines": n_unparsed,
        "headerless_lines_kept": n_headerless,
        "templates": parser.num_templates,
        "windows": len(sequences),
        # time windows: minutes with no lines; line windows: lines in the dropped partial window
        "dropped": int((ts.max() // size - ts.min() // size) + 1 - len(sequences)) if kind == "time"
                   else len(cluster_ids) - len(sequences) * size,
        "mean_lines_per_window": float(lengths.mean()),
        "median_lines_per_window": float(lengths.median()),
        "max_lines_per_window": int(lengths.max()),
        "out_of_order_lines": int((ts[1:] < np.maximum.accumulate(ts)[:-1]).sum()),
        "first_time": datetime.fromtimestamp(ts.min(), timezone.utc),
        "last_time": datetime.fromtimestamp(ts.max(), timezone.utc),
        "parse_seconds": parse_seconds,
        "total_seconds": time.perf_counter() - start,
    }
    return sequences, counts, templates, stats
