"""Replay producer: stream a dataset's test set (last 30%) line by line into the Redis stream.

    python -m src.streaming.replay hdfs --rate 500
    python -m src.streaming.replay bgl --rate 2000 --limit 100000
    python -m src.streaming.replay openssh --rate 500      # Loghub OpenSSH, no labels
    python -m src.streaming.replay apache --rate 200       # Loghub Apache error log, no labels

HDFS: lines that mention a test block (blocks are in first-appearance order, so the test blocks are those after
the 70% cut). BGL: every line from the first test window on; the detector numbers its 20-line windows from
that window, so window ids match the offline ones. OpenSSH: every line from the first line of the first test
minute on (1-minute windows). Apache: every line from the first test window on (20-line windows of parsed lines).
For OpenSSH and Apache the reset message also carries the line parser's state (year, last timestamp), so the
detector reads timestamps exactly as time_windows.parse_timed_log did. A "reset" message starts the replay and a "flush" message
ends it: after a complete replay the detector scores the blocks still open; after one cut short by --limit it
drops them, because a block cut off in the middle doesn't look like any training block.
"""

import argparse
import json
import re
import time

import pandas as pd
import redis
from tqdm import tqdm

from src.models.unsupervised import time_split
from src.features.time_windows import LOG_PATHS
from src.streaming.common import REDIS_URL, ROOT, STREAM, STREAM_MAXLEN, TIMED_DATASETS, TimedLogParser

RAW, PROCESSED = ROOT / "data" / "raw", ROOT / "data" / "processed"
BLOCK_RE = re.compile(r"blk_-?\d+")


def hdfs_lines():
    """Test-set HDFS lines, in file order."""
    _, test = time_split(pd.read_parquet(PROCESSED / "hdfs_sequences.parquet", columns=["BlockId", "order"]), 0.7)
    test_blocks = set(test["BlockId"])
    with open(RAW / "HDFS" / "HDFS.log", encoding="utf-8", errors="replace") as f:
        for line in f:
            if "blk_" in line and any(b in test_blocks for b in BLOCK_RE.findall(line)):
                yield line.rstrip("\n")


def bgl_lines(window_size=20):
    """(first test window, generator of BGL lines from that window on)."""
    n_windows = len(pd.read_parquet(PROCESSED / "bgl_sequences.parquet", columns=["window"]))
    first = int(n_windows * 0.7)  # same cut as time_split(train_frac=0.7)

    def lines():
        skip = first * window_size  # non-empty lines before the first test window, as counted in parse_bgl
        with open(RAW / "BGL" / "BGL.log", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                if skip:
                    skip -= 1
                    continue
                yield line.rstrip("\n")

    return first, lines()


def timed_lines(source, window_size=20):
    """OpenSSH / Apache: (first test window, parser state before its first line, generator of lines from there on).

    The parser has to read the skipped lines anyway (OpenSSH year changes, Apache timestamps), so the state is
    only known once the generator reaches the first test line: the dict returned is filled in at that point.
    """
    dataset = TIMED_DATASETS[source]
    windows = pd.read_parquet(PROCESSED / f"{source}_sequences.parquet", columns=["window", "start_time"])
    _, test = time_split(windows, 0.7, "window")
    first, first_start = int(test["window"].iloc[0]), int(test["start_time"].iloc[0])
    state = {}

    def lines():
        parser, kept, started = TimedLogParser(dataset), 0, False
        with open(LOG_PATHS[dataset], encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                if not started:
                    before = parser.state()
                    ts, content, _ = parser(line)
                    if content is None:
                        continue
                    # OpenSSH: first line of the first test minute; Apache: first line after first * 20 parsed lines
                    started = ts // 60 * 60 >= first_start if source == "openssh" else kept >= first * window_size
                    kept += 1
                    if not started:
                        continue
                    state.update(before)
                yield line.rstrip("\n")

    return first, state, lines()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=["hdfs", "bgl", "openssh", "apache"])
    parser.add_argument("--rate", type=float, default=500, help="lines per second")
    parser.add_argument("--limit", type=int, help="stop after this many lines")
    args = parser.parse_args()

    r = redis.Redis.from_url(REDIS_URL)
    state = None
    if args.dataset == "hdfs":
        start, lines = 0, hdfs_lines()
    elif args.dataset == "bgl":
        start, lines = bgl_lines()
    else:
        start, state, lines = timed_lines(args.dataset)
        first_line = next(lines)  # reads up to the first test line, which fills in the parser state
        lines = _chain(first_line, lines)
    reset = {"source": args.dataset, "kind": "reset", "start": start}
    if state is not None:
        reset["state"] = json.dumps(state)
    r.xadd(STREAM, reset, maxlen=STREAM_MAXLEN, approximate=True)

    batch = max(1, int(args.rate / 10))  # send in batches 10 times a second
    sent, began = 0, time.monotonic()
    pipe = r.pipeline(transaction=False)
    with tqdm(total=args.limit, unit=" lines", desc=f"replay {args.dataset}", mininterval=5) as bar:
        for line in lines:
            pipe.xadd(STREAM, {"source": args.dataset, "kind": "line", "line": line}, maxlen=STREAM_MAXLEN, approximate=True)
            sent += 1
            if sent % batch == 0:
                pipe.execute()
                bar.update(batch)
                time.sleep(max(0.0, began + sent / args.rate - time.monotonic()))
            if args.limit and sent >= args.limit:
                break
        pipe.execute()
    # a replay cut short by --limit leaves HDFS blocks unfinished; the detector drops those instead of scoring them
    complete = not (args.limit and sent >= args.limit)
    r.xadd(STREAM, {"source": args.dataset, "kind": "flush", "complete": int(complete)}, maxlen=STREAM_MAXLEN,
           approximate=True)
    print(f"sent {sent:,} lines in {time.monotonic() - began:.0f} s")


def _chain(first, rest):
    yield first
    yield from rest


if __name__ == "__main__":
    main()
