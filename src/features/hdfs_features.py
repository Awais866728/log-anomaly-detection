"""Block-level event sequences and count vectors for the full HDFS_v1 dataset."""

import re
import time
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from src.parsing.drain_parser import DrainParser, extract_content

ROOT = Path(__file__).resolve().parents[2]
HDFS_DIR = ROOT / "data" / "raw" / "HDFS"
PROCESSED = ROOT / "data" / "processed"

BLOCK_RE = re.compile(r"blk_-?\d+")


def parse_hdfs_blocks(log_path):
    """Parse the log line by line; return {block_id: [cluster ids]} in first-appearance order."""
    parser = DrainParser("HDFS")
    blocks = {}  # dicts keep insertion order, so this is first-appearance order
    n_lines = n_unparsed = 0
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in tqdm(f, desc="Parsing HDFS.log", unit=" lines", mininterval=30):
            n_lines += 1
            content = extract_content(line, "HDFS")
            if content is None:
                n_unparsed += 1
                continue
            cluster_id = parser.parse(content)[0]
            # a line can mention several blocks (e.g. delete requests); the event counts for each
            for block_id in dict.fromkeys(BLOCK_RE.findall(content)):
                blocks.setdefault(block_id, []).append(cluster_id)
    return blocks, parser, n_lines, n_unparsed


def build_hdfs(log_path=HDFS_DIR / "HDFS.log", label_path=HDFS_DIR / "preprocessed" / "anomaly_label.csv"):
    """Build and save hdfs_sequences.parquet and hdfs_counts.parquet; return (sequences, counts, stats)."""
    start = time.perf_counter()
    blocks, parser, n_lines, n_unparsed = parse_hdfs_blocks(log_path)
    parse_seconds = time.perf_counter() - start

    labels = pd.read_csv(label_path).set_index("BlockId")["Label"].map({"Normal": 0, "Anomaly": 1})

    sequences = pd.DataFrame({
        "BlockId": list(blocks),
        "order": range(len(blocks)),
        "EventSequence": [[f"E{cid}" for cid in seq] for seq in blocks.values()],
    })
    sequences["Label"] = sequences["BlockId"].map(labels)

    lengths = sequences["EventSequence"].str.len()
    events = sequences["EventSequence"].explode()
    counts = pd.crosstab(events.index, events).rename_axis(index=None, columns=None)
    event_cols = sorted(counts.columns, key=lambda c: int(c[1:]))
    counts = sequences[["BlockId", "order", "Label"]].join(counts[event_cols])

    templates = pd.DataFrame({
        "EventId": [f"E{c.cluster_id}" for c in parser.miner.drain.clusters],
        "template": [c.get_template() for c in parser.miner.drain.clusters],
    })

    PROCESSED.mkdir(parents=True, exist_ok=True)
    sequences.to_parquet(PROCESSED / "hdfs_sequences.parquet", index=False)
    counts.to_parquet(PROCESSED / "hdfs_counts.parquet", index=False)
    templates.to_csv(PROCESSED / "hdfs_templates.csv", index=False)

    stats = {
        "lines": n_lines,
        "unparsed_lines": n_unparsed,
        "templates": parser.num_templates,
        "blocks": len(sequences),
        "unlabelled_blocks": int(sequences["Label"].isna().sum()),
        "anomalous_blocks": int(sequences["Label"].sum()),
        "mean_sequence_length": float(lengths.mean()),
        "parse_seconds": parse_seconds,
        "total_seconds": time.perf_counter() - start,
    }
    return sequences, counts, stats
