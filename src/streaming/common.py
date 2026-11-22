"""Shared pieces of the streaming pipeline: Redis settings, line parsing per source, Drain matching."""

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from src.features.bgl_features import EMPTY_MESSAGE
from src.features.time_windows import APACHE_HEADERLESS, Timestamps
from src.parsing.drain_parser import extract_content

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "models"
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
STREAM = os.environ.get("LOG_STREAM", "logs")
STREAM_MAXLEN = 200_000  # Redis keeps about this many entries

REPLAY_SOURCES = ["hdfs", "bgl", "openssh", "apache"]  # openssh / apache: Loghub datasets without labels
TIMED_DATASETS = {"openssh": "OpenSSH", "apache": "Apache"}  # replay source -> dataset name in time_windows
LIVE_SERVICES = ["nginx", "app", "postgres", "ssh"]

HDFS_BLOCK_RE = re.compile(r"blk_-?\d+")
DOCKER_TS_RE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(\.\d+)?Z (.*)$")

# Message part of each service's own line format; lines that match none keep their full text.
LIVE_FORMATS = {
    # 2026-11-12T10:03:01.080Z INFO 172.20.0.1 GET / 200 13ms
    "app": [re.compile(r"^\S+Z (?P<level>INFO|WARN|ERROR) (?P<content>.*)$")],
    "nginx": [
        # 172.20.0.1 - - [12/Nov/2026:10:03:01 +0000] "GET /api/ HTTP/1.1" 200 15 "-" "curl/8.5.0" "-"
        re.compile(r'^\S+ - \S+ \[[^\]]+\] (?P<content>"[^"]*" (?P<status>\d{3}) .*)$'),
        # 2026/11/12 10:02:54 [notice] 1#1: start worker process 26
        re.compile(r"^\d{4}/\d\d/\d\d \d\d:\d\d:\d\d \[(?P<level>\w+)\] \d+#\d+: (?:\*\d+ )?(?P<content>.*)$"),
    ],
    # 2026-11-21 20:14:44.695 UTC [38] LOG:  connection received: host=[local]
    "postgres": [re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+ \w+ \[\d+\] (?P<level>[A-Z]+):\s+(?P<content>.*)$")],
    "ssh": [],  # sshd writes the bare message (OpenSSH format without the syslog header)
}
LEVELS = {"WARNING": "WARN", "WARN": "WARN", "ERROR": "ERROR", "FATAL": "ERROR", "PANIC": "ERROR",
          "error": "ERROR", "crit": "ERROR", "alert": "ERROR", "emerg": "ERROR", "warn": "WARN"}
SSH_WARN_RE = re.compile(r"Failed|Invalid user|invalid user|error|BREAK-IN|Did not receive identification|Bad protocol")


def iso(ts):
    """Unix seconds -> ISO 8601 UTC string with milliseconds."""
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def split_docker_line(raw):
    """'2026-11-21T16:19:04.364771273Z message' -> (unix seconds, message); (None, raw) without a timestamp."""
    match = DOCKER_TS_RE.match(raw)
    if match is None:
        return None, raw
    base, frac, message = match.groups()
    ts = datetime.strptime(base, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    return ts + (float(frac[:7]) if frac else 0.0), message


def parse_live(service, message):
    """Service message -> (content for Drain, level INFO/WARN/ERROR)."""
    for pattern in LIVE_FORMATS[service]:
        match = pattern.match(message)
        if match:
            groups = match.groupdict()
            level = LEVELS.get(groups.get("level") or "", "INFO")
            if groups.get("status"):
                level = "ERROR" if groups["status"][0] == "5" else "WARN" if groups["status"][0] == "4" else "INFO"
            return match.group("content").strip(), level
    level = "WARN" if service == "ssh" and SSH_WARN_RE.search(message) else "INFO"
    return message.strip(), level


def parse_hdfs(line):
    """HDFS line -> (unix seconds, content or None, block ids, level)."""
    fields = line.split(maxsplit=4)
    try:
        ts = datetime.strptime(fields[0] + fields[1], "%y%m%d%H%M%S").replace(tzinfo=timezone.utc).timestamp()
    except (IndexError, ValueError):
        ts = None
    content = extract_content(line, "HDFS")
    level = LEVELS.get(fields[3], "INFO") if len(fields) > 3 else "INFO"
    blocks = list(dict.fromkeys(HDFS_BLOCK_RE.findall(content))) if content else []
    return ts, content, blocks, level


def parse_bgl(line):
    """BGL line -> (unix seconds, content or None, is_alert, level), handled exactly as in bgl_features.parse_bgl."""
    fields = line.split(maxsplit=2)
    ts = float(fields[1]) if len(fields) > 1 and fields[1].isdigit() else None
    content = extract_content(line, "BGL")
    if content is None and len(line.split()) == 9:
        content = EMPTY_MESSAGE
    parts = line.split()
    level = parts[8] if len(parts) > 8 else "INFO"
    level = {"FATAL": "ERROR", "FAILURE": "ERROR", "SEVERE": "ERROR", "ERROR": "ERROR", "WARNING": "WARN"}.get(level, "INFO")
    return ts, content, bool(fields) and fields[0] != "-", level


APACHE_LEVEL_RE = re.compile(r"^\[[^\]]*\]\s+\[(\w+)\]")


class TimedLogParser:
    """OpenSSH / Apache line -> (unix seconds, content or None, level), exactly as time_windows.parse_timed_log.

    Lines without a timestamp or message give content None and are not part of any window. Apache's headerless
    APACHE_HEADERLESS lines get the previous kept line's timestamp. OpenSSH lines have no year: Timestamps adds
    one when the month goes back. state() / restore() carry this across the start of a replay.
    """

    def __init__(self, dataset):
        self.dataset = dataset
        self.to_seconds = Timestamps(dataset)
        self.last_ts = None

    def __call__(self, line):
        content, ts = extract_content(line, self.dataset), self.to_seconds(line)
        if self.dataset == "Apache" and line.strip() == APACHE_HEADERLESS and self.last_ts is not None:
            content, ts = APACHE_HEADERLESS, self.last_ts
        if self.dataset == "Apache":
            match = APACHE_LEVEL_RE.match(line)
            level = LEVELS.get(match.group(1), "INFO") if match else "INFO"
        else:
            level = "WARN" if SSH_WARN_RE.search(line) else "INFO"
        if content is None or ts is None:
            return ts, None, level
        self.last_ts = ts
        return ts, content, level

    def state(self):
        return {"year": self.to_seconds.year, "last_month": self.to_seconds.last_month, "last_ts": self.last_ts}

    def restore(self, state):
        self.to_seconds.year = int(state.get("year", self.to_seconds.year))
        self.to_seconds.last_month = state.get("last_month")
        self.last_ts = state.get("last_ts")


def assign_cluster(miner, content):
    """Cluster id for a message without changing any training template.

    Uses the same tree search (and similarity threshold) as Drain's add_log_message, so a line gets the cluster
    it would have joined during training. A message that matches nothing becomes a new cluster, with an id above
    every training cluster, so the models treat it as an unseen event.
    """
    drain = miner.drain
    tokens = drain.get_content_as_tokens(miner.masker.mask(content))
    cluster = drain.tree_search(drain.root_node, tokens, drain.sim_th, False)
    if cluster is not None:
        return cluster.cluster_id
    return miner.add_log_message(content)["cluster_id"]
