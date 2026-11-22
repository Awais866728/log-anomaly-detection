"""Detection service: reads the Redis log stream, builds windows as in training, scores and explains them.

    uvicorn src.streaming.service:app --port 8000

Replay sources (hdfs, bgl) use the packs built from the offline training data; live sources (the Docker services)
use the packs trained on collected normal logs (python -m src.streaming.packs replay / live). A source without a
pack is still shown on the live log page but not scored.

Endpoints: GET /api/logs, /api/alerts, /api/stats, /api/models, /health and GET /api/events (server-sent events:
"logs", "alert" and "stats"). Set ALERT_LOG=<path> to also keep every alert in a JSON-lines file.
"""

import asyncio
import json
import os
import threading
import time
import warnings
from collections import Counter, deque
from contextlib import asynccontextmanager

import pandas as pd
import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from src.streaming.common import (LIVE_SERVICES, REDIS_URL, REPLAY_SOURCES, ROOT, STREAM, assign_cluster, iso, parse_bgl,
                                  parse_hdfs, parse_live, split_docker_line)
from src.streaming.packs import Pack, pack_path
from src.streaming.windows import BlockWindows, LineWindows, TimeWindows

MAX_LOGS, MAX_ALERTS = 500, 500
START_ID = os.environ.get("STREAM_START", "$")  # "$" = only new entries, "0" = everything in the stream
HDFS_IDLE = float(os.environ.get("HDFS_IDLE_SECONDS", 4 * 3600))
DEDUPE_NEW_TEMPLATES = os.environ.get("DEDUPE_NEW_TEMPLATES", "1") == "1"
ALERT_LOG = os.environ.get("ALERT_LOG")  # if set: append every alert to this file as one JSON line
# SHAP and predict_proba get numpy rows; the models were fitted on DataFrames
warnings.filterwarnings("ignore", message="X does not have valid feature names")
SOURCE_LABEL = {"hdfs": "hdfs (replay)", "bgl": "bgl (replay)"}


class Detector:
    """Consumes the stream in a background thread; keeps recent logs, alerts and counters for the API."""

    def __init__(self):
        self.started = time.time()
        self.packs = {s: Pack.load(s) for s in REPLAY_SOURCES + LIVE_SERVICES if pack_path(s).exists()}
        self.windows = {s: self._new_windows(s) for s in self.packs}
        self.logs, self.alerts = deque(maxlen=MAX_LOGS), deque(maxlen=MAX_ALERTS)
        self.lock = threading.Lock()
        self.subscribers = set()  # (loop, asyncio.Queue) per open /api/events connection
        self.counts = Counter()  # lines, windows, alerts per kind
        self.received = deque(maxlen=20000)  # receive times of recent lines (lines per minute)
        self.warned = {s: set() for s in self.packs}  # new templates already reported per source
        self.line_id = 0
        self.hdfs_labels = None
        self.stop = threading.Event()

    def _new_windows(self, source, start=0):
        if source == "hdfs":
            return BlockWindows(source, idle=HDFS_IDLE)
        if source == "bgl":
            return LineWindows(source, size=20, start_index=start)
        return TimeWindows(source, started=self.started)  # the minute the service started is only partly collected

    # ------------------------------------------------------------ stream loop

    def run(self):
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        last_id, last_tick = START_ID, 0.0
        while not self.stop.is_set():
            try:
                batch = r.xread({STREAM: last_id}, count=1000, block=1000) or []
            except redis.ConnectionError:
                time.sleep(2)
                continue
            new_logs, closed = [], []
            for _, entries in batch:
                for entry_id, fields in entries:
                    last_id = entry_id
                    lines, windows = self.handle(entry_id, fields)
                    new_logs += lines
                    closed += windows
            self.score_windows(closed)
            if new_logs:
                with self.lock:
                    self.logs.extend(new_logs)
                self.broadcast("logs", new_logs[-100:])
            if time.time() - last_tick >= 1:  # close finished 1-minute windows, push stats
                last_tick = time.time()
                self.score_windows([w for windows in self.windows.values() for w in windows.tick(last_tick)])
                self.broadcast("stats", self.stats())

    def handle(self, entry_id, fields):
        source, kind = fields.get("source"), fields.get("kind", "line")
        received = int(entry_id.split("-")[0]) / 1000
        if kind == "reset" and source in self.packs:
            closed = self.windows[source].flush()
            self.windows[source] = self._new_windows(source, int(fields.get("start", 0)))
            self.warned[source] = set()
            return [], closed
        if kind == "flush" and source in self.packs:
            closed = self.windows[source].flush()
            if fields.get("complete", "1") == "0":  # replay cut short: unfinished blocks would look anomalous
                self.counts["unfinished_windows_dropped"] += len(closed)
                return [], []
            return [], closed
        if kind != "line":
            return [], []

        raw = fields.get("line", "")
        self.line_id += 1
        self.counts["lines"] += 1
        self.received.append(received)
        pack = self.packs.get(source)
        label, blocks = None, None
        if source == "hdfs":
            log_time, content, blocks, level = parse_hdfs(raw)
            message = raw
        elif source == "bgl":
            log_time, content, label, level = parse_bgl(raw)
            message = raw
        else:
            log_time, message = split_docker_line(raw)
            log_time = log_time or received
            content, level = parse_live(source, message) if source in LIVE_SERVICES else (message, "INFO")
        log_line = {"id": self.line_id, "time": iso(log_time) if log_time else iso(received),
                    "received": iso(received), "service": SOURCE_LABEL.get(source, source), "level": level, "message": message}

        closed = []
        if pack is not None and (content is not None or source == "bgl"):
            event = f"E{assign_cluster(pack.miner, content)}" if content is not None else "E0"
            windows = self.windows[source]
            if source == "hdfs":
                closed = windows.add_multi(event, blocks, self.line_id, message, log_time, received)
            else:
                closed = windows.add(event, self.line_id, message, log_time, received, label)
        return [log_line], closed

    # ------------------------------------------------------------ scoring

    def score_windows(self, windows, batch_size=500):
        """Score closed windows, batched per source (one model call per detector and batch)."""
        by_source = {}
        for w in windows:
            by_source.setdefault(w.source, []).append(w)
        for source, items in by_source.items():
            for start in range(0, len(items), batch_size):
                chunk = items[start : start + batch_size]
                for w, scored in zip(chunk, self.packs[source].score_batch([w.events for w in chunk])):
                    self.alert(w, *scored)

    def alert(self, window, verdicts, x, unseen):
        pack = self.packs[window.source]
        self.counts["windows"] += 1
        alert = pack.explain(window.window_id, window.events, verdicts, x, unseen)
        if alert is None:
            return
        if alert["level"] == "New template" and DEDUPE_NEW_TEMPLATES:
            fresh = [e for e in unseen if e not in self.warned[window.source]]
            if not fresh:
                self.counts["new_template_repeats"] += 1
                return
        self.warned[window.source].update(unseen)

        now = time.time()
        self.counts[alert["level"]] += 1
        alert.update({
            "id": f"{window.source}-{self.counts['Alert'] + self.counts['New template']}",
            "source": SOURCE_LABEL.get(window.source, window.source),
            "window": self._describe(window),
            "n_lines": window.n_lines,
            "last_line_time": iso(window.last_time) if window.last_time else None,
            "last_line_received": iso(window.last_received),
            "alert_time": iso(now),
            "latency_ms": round((now - window.last_received) * 1000),
            "log_lines": [raw for _, raw in window.lines],
            "line_ids": [i for i, _ in window.lines],
            "true_label": self._true_label(window),
            "status": "open",
        })
        line = json.dumps(alert, default=_jsonable)
        alert = json.loads(line)
        if ALERT_LOG:
            with open(ALERT_LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        with self.lock:
            self.alerts.appendleft(alert)
        self.broadcast("alert", alert)

    def _describe(self, window):
        if window.source == "hdfs":
            return f"block {window.window_id}"
        if window.source == "bgl":
            first = window.window_id * 20
            return f"window {window.window_id} (test lines {first:,}-{first + 19:,})"
        start = iso(window.window_id)
        return f"{start[11:16]}-{iso(window.window_id + 60)[11:16]} UTC"

    def _true_label(self, window):
        if window.source == "bgl":
            return int(any(window.labels))
        if window.source == "hdfs":
            if self.hdfs_labels is None:
                seqs = pd.read_parquet(ROOT / "data" / "processed" / "hdfs_sequences.parquet", columns=["BlockId", "Label"])
                self.hdfs_labels = dict(zip(seqs["BlockId"], seqs["Label"]))
            return int(self.hdfs_labels.get(window.window_id, 0))
        return None

    # ------------------------------------------------------------ API helpers

    def stats(self):
        now = time.time()
        with self.lock:
            latencies = [a["latency_ms"] for a in list(self.alerts)[:100]]
            open_alerts = Counter(a["level"] for a in self.alerts)
        return {
            "lines": self.counts["lines"], "windows": self.counts["windows"],
            "logs_per_minute": sum(1 for t in self.received if t > now - 60),
            "alerts": open_alerts.get("Alert", 0), "new_templates": open_alerts.get("New template", 0),
            "new_template_repeats": self.counts["new_template_repeats"],
            "avg_detection_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
            "late_hdfs_lines": getattr(self.windows.get("hdfs"), "late_lines", 0),
            "unfinished_windows_dropped": self.counts["unfinished_windows_dropped"],
            "packs": {s: {"mode": p.mode, "models": list(p.detectors), "settings": p.settings} for s, p in self.packs.items()},
        }

    def broadcast(self, event, data):
        message = f"event: {event}\ndata: {json.dumps(data, default=_jsonable)}\n\n"
        for loop, queue in list(self.subscribers):
            loop.call_soon_threadsafe(_put, queue, message)


def _put(queue, message):
    if not queue.full():  # a slow browser loses messages instead of slowing the detector
        queue.put_nowait(message)


def _jsonable(value):
    if hasattr(value, "item"):
        return value.item()
    return str(value)


MODEL_INFO = {
    "PCA": ("Statistical", "Flags windows whose event counts can't be rebuilt from normal patterns."),
    "Isolation Forest": ("Unsupervised ML", "Isolates unusual windows with random splits, trained on normal data only."),
    "Random Forest": ("Supervised ML", "Learns from labelled normal and anomalous windows (replay only)."),
    "LSTM": ("Deep learning", "Predicts the next event from the previous 10 (DeepLog) and flags surprises."),
}


def model_results():
    """docs/cross_system_results.csv (validation-chosen settings, test set) in the dashboard's format."""
    table = pd.read_csv(ROOT / "docs" / "cross_system_results.csv").rename(columns={"chosen on": "chosen_on"})
    out = []
    for name, (kind, description) in MODEL_INFO.items():
        rows = table[(table["model"] == name) & table["dataset"].isin(["HDFS", "BGL"])].set_index("dataset")
        out.append({"name": name, "kind": kind, "description": description,
                    "settings": {d: rows.loc[d, "setting"] for d in rows.index},
                    "scores": {d: {m: float(rows.loc[d, m]) for m in ["precision", "recall", "f1", "false_alarm_rate"]}
                               for d in rows.index},
                    "flag_rates": {f"{r.dataset} ({r.chosen_on} setting)": {"setting": r.setting, "flag_rate": float(r.flag_rate)}
                                   for r in table[(table["model"] == name) & ~table["dataset"].isin(["HDFS", "BGL"])].itertuples()}})
    return out


detector = None


@asynccontextmanager
async def lifespan(app):
    global detector
    detector = Detector()
    thread = threading.Thread(target=detector.run, daemon=True)
    thread.start()
    yield
    detector.stop.set()


app = FastAPI(title="Log anomaly detection service", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
                   allow_methods=["GET"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok", "packs": list(detector.packs)}


@app.get("/api/logs")
def logs(limit: int = 200):
    with detector.lock:
        return list(detector.logs)[-limit:][::-1]  # newest first


@app.get("/api/alerts")
def alerts(limit: int = 200):
    with detector.lock:
        return list(detector.alerts)[:limit]


@app.get("/api/stats")
def stats():
    return detector.stats()


@app.get("/api/models")
def models():
    return model_results()


@app.get("/api/events")
async def events():
    loop, queue = asyncio.get_running_loop(), asyncio.Queue(maxsize=200)
    subscriber = (loop, queue)
    detector.subscribers.add(subscriber)

    async def stream():
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            detector.subscribers.discard(subscriber)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
