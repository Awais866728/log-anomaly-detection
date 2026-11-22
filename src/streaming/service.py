"""Detection service: reads the Redis log stream, builds windows as in training, scores and explains them.

    uvicorn src.streaming.service:app --port 8000

Replay sources (hdfs, bgl, and the unlabelled openssh, apache) use the packs built from the offline training data; live sources (the Docker services)
use the packs trained on collected normal logs (python -m src.streaming.packs replay / live). A source without a
pack is still shown on the live log page but not scored.

Endpoints: GET /api/logs, /api/alerts, /api/stats, /api/models, /api/packs, /api/system, /health and GET /api/events
(server-sent events: "logs", "alert" and "stats"). /api/system has the container state from `docker compose ps`, log
lines per minute per service and the pipeline status. /api/logs keeps the last lines per source, so a fast
replay doesn't push the live services out. Set ALERT_LOG=<path> to also keep every alert in a JSON-lines file.
"""

import asyncio
import json
import os
import subprocess
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

from src.streaming.common import (LIVE_SERVICES, REDIS_URL, REPLAY_SOURCES, ROOT, STREAM, TIMED_DATASETS, TimedLogParser,
                                  assign_cluster, iso, parse_bgl, parse_hdfs, parse_live, split_docker_line)
from src.streaming.packs import Pack, pack_path
from src.streaming.windows import BlockWindows, LineWindows, TimeWindows

MAX_LOGS, MAX_ALERTS = 500, 500  # log lines and alerts kept per source (a BGL replay alone makes ~18 alerts/s)
START_ID = os.environ.get("STREAM_START", "$")  # "$" = only new entries, "0" = everything in the stream
HDFS_IDLE = float(os.environ.get("HDFS_IDLE_SECONDS", 4 * 3600))
DEDUPE_NEW_TEMPLATES = os.environ.get("DEDUPE_NEW_TEMPLATES", "1") == "1"
ALERT_LOG = os.environ.get("ALERT_LOG")  # if set: append every alert to this file as one JSON line
# SHAP and predict_proba get numpy rows; the models were fitted on DataFrames
warnings.filterwarnings("ignore", message="X does not have valid feature names")
SOURCE_LABEL = {s: f"{s} (replay)" for s in REPLAY_SOURCES}
COMPOSE_PS = ["docker", "compose", "-f", str(ROOT / "docker" / "docker-compose.yml"), "ps", "--all", "--format", "json"]
VOLUME_MINUTES = 30  # per-minute line counts kept per source
COLLECTOR_STALE = 120  # seconds without a live line before the collector is shown as a warning
QUEUE_WARN = 1000  # stream entries waiting to be read before the queue is shown as a warning


class Detector:
    """Consumes the stream in a background thread; keeps recent logs, alerts and counters for the API."""

    def __init__(self):
        self.started = time.time()
        self.packs = {s: Pack.load(s) for s in REPLAY_SOURCES + LIVE_SERVICES if pack_path(s).exists()}
        self.windows = {s: self._new_windows(s) for s in self.packs}
        self.logs = {}  # source label -> its last MAX_LOGS lines
        self.alerts = {}  # source label -> its last MAX_ALERTS alerts, newest first
        self.timed = {s: TimedLogParser(d) for s, d in TIMED_DATASETS.items()}  # OpenSSH / Apache line parsers
        self.lock = threading.Lock()
        self.subscribers = set()  # (loop, asyncio.Queue) per open /api/events connection
        self.counts = Counter()  # lines, windows, alerts per kind
        self.received = deque(maxlen=20000)  # receive times of recent lines (lines per minute)
        self.per_second = {}  # source -> Counter(second -> lines), by receive time, last 60 s
        self.per_minute = {}  # source -> Counter(minute start -> lines), last VOLUME_MINUTES minutes
        self.last_received = {}  # source -> receive time of its last line
        self.last_id = None  # last stream entry read
        self.warned = {s: set() for s in self.packs}  # new templates already reported per source
        self.line_id = 0
        self.hdfs_labels = None
        self.stop = threading.Event()

    def _new_windows(self, source, start=0):
        if source == "hdfs":
            return BlockWindows(source, idle=HDFS_IDLE)
        if source in ("bgl", "apache"):
            return LineWindows(source, size=20, start_index=start)
        if source == "openssh":
            return TimeWindows(source, wall_clock=False)  # old log times: windows close on later lines, not the clock
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
                    last_id = self.last_id = entry_id
                    lines, windows = self.handle(entry_id, fields)
                    new_logs += lines
                    closed += windows
            self.score_windows(closed)
            if new_logs:
                per_source = {}
                for line in new_logs:
                    per_source.setdefault(line["service"], []).append(line)
                with self.lock:
                    for label, lines in per_source.items():
                        self.logs.setdefault(label, deque(maxlen=MAX_LOGS)).extend(lines)
                # at most 100 new lines per source per message, so a fast replay can't crowd out the others
                self.broadcast("logs", sorted((l for lines in per_source.values() for l in lines[-100:]), key=lambda l: l["id"]))
            if time.time() - last_tick >= 1:  # close finished 1-minute windows, push stats
                last_tick = time.time()
                self.score_windows([w for windows in self.windows.values() for w in windows.tick(last_tick)])
                self._prune(last_tick)
                self.broadcast("stats", self.stats())

    def handle(self, entry_id, fields):
        source, kind = fields.get("source"), fields.get("kind", "line")
        received = int(entry_id.split("-")[0]) / 1000
        if kind == "reset" and source in self.timed:  # the replay's parser state at its first line
            self.timed[source] = TimedLogParser(TIMED_DATASETS[source])
            if fields.get("state"):
                self.timed[source].restore(json.loads(fields["state"]))
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
        with self.lock:
            self.per_second.setdefault(source, Counter())[int(received)] += 1
            self.per_minute.setdefault(source, Counter())[int(received // 60) * 60] += 1
            self.last_received[source] = received
        pack = self.packs.get(source)
        label, blocks = None, None
        if source == "hdfs":
            log_time, content, blocks, level = parse_hdfs(raw)
            message = raw
        elif source == "bgl":
            log_time, content, label, level = parse_bgl(raw)
            message = raw
        elif source in self.timed:
            log_time, content, level = self.timed[source](raw)  # content None: not part of any window
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
            self.alerts.setdefault(alert["source"], deque(maxlen=MAX_ALERTS)).appendleft(alert)
        self.broadcast("alert", alert)

    def _describe(self, window):
        if window.source == "hdfs":
            return f"block {window.window_id}"
        if window.source == "bgl":
            first = window.window_id * 20
            return f"window {window.window_id} (test lines {first:,}-{first + 19:,})"
        if window.source == "apache":
            return f"window {window.window_id} (20 parsed lines)"
        if window.source == "openssh":
            return f"{iso(window.window_id)[:16].replace('T', ' ')} (log time, 1 minute)"
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
            alerts = self.all_alerts()
            latencies = [a["latency_ms"] for a in alerts[:100]]
            open_alerts = Counter(a["level"] for a in alerts)
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

    def all_alerts(self, limit=MAX_ALERTS):
        """The last `limit` alerts of every source, newest first (call with self.lock held)."""
        return sorted((a for q in self.alerts.values() for a in list(q)[:limit]), key=lambda a: a["alert_time"], reverse=True)

    def _prune(self, now):
        with self.lock:
            for counter, keep in [(c, now - 60) for c in self.per_second.values()] + \
                                 [(c, now - (VOLUME_MINUTES + 1) * 60) for c in self.per_minute.values()]:
                for key in [k for k in counter if k < keep]:
                    del counter[key]

    def lines_last_minute(self, source, now):
        with self.lock:
            counter = self.per_second.get(source, Counter())
            return sum(n for sec, n in counter.items() if sec > now - 60)

    def complete_minutes(self, now, minutes=VOLUME_MINUTES):
        """Start times of the last `minutes` full minutes since the service started (the first minute is partial)."""
        first = int(self.started // 60) * 60 + 60
        last = int(now // 60) * 60 - 60  # the current minute is still being collected
        return list(range(max(first, last - (minutes - 1) * 60), last + 1, 60))

    def volume(self, now):
        """Live log lines per service and full minute, by receive time."""
        with self.lock:
            counts = {s: dict(self.per_minute.get(s, {})) for s in LIVE_SERVICES}
        return [{"minute": m, **{s: counts[s].get(m, 0) for s in LIVE_SERVICES}} for m in self.complete_minutes(now)]

    def packs_info(self):
        window = {"hdfs": "per block", "bgl": "20 lines", "apache": "20 lines"}
        return [{"source": s, "label": SOURCE_LABEL.get(s, s), "mode": p.mode, "dataset": p.dataset,
                 "models": list(p.detectors), "settings": p.settings, "templates": len(p.event_cols),
                 "train_windows": getattr(p, "train_windows", None), "window": window.get(s, "1 minute"),
                 "labelled": getattr(p, "labelled", p.mode == "replay"), "settings_from": getattr(p, "settings_from", None)}
                for s, p in self.packs.items()]

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
                    # no labels: only the share of windows flagged, with the settings chosen on HDFS and on BGL
                    "unlabelled": {d: [{"chosen_on": r.chosen_on, "setting": r.setting, "flag_rate": float(r.flag_rate)}
                                       for r in table[(table["model"] == name) & (table["dataset"] == d)].itertuples()]
                                   for d in ["OpenSSH", "Apache"]}})
    return out


_docker_cache = {"time": 0.0, "value": None}
_docker_lock = threading.Lock()


def docker_containers(max_age=5):
    """Compose service -> container info from `docker compose ps` (cached for max_age s); None if docker fails."""
    with _docker_lock:
        if time.time() - _docker_cache["time"] < max_age:
            return _docker_cache["value"]
        try:
            out = subprocess.run(COMPOSE_PS, capture_output=True, text=True, timeout=10, check=True).stdout.strip()
            rows = json.loads(out) if out.startswith("[") else [json.loads(line) for line in out.splitlines() if line.strip()]
            value = {r["Service"]: r for r in rows}
        except (OSError, subprocess.SubprocessError, ValueError):
            value = None
        _docker_cache.update(time=time.time(), value=value)
        return value


def container_health(c):
    """healthy / warning / down from the container state and its health check (if it has one)."""
    if c is None:
        return "down"  # docker works, but the service has no container
    if c.get("State") == "running":
        return "healthy" if c.get("Health") in ("", None, "healthy") else "warning"  # starting / unhealthy
    return "warning" if c.get("State") in ("restarting", "paused") else "down"


def uptime(c):
    """'4 hours' from the status 'Up 4 hours (healthy)'; None when the container isn't running."""
    status = (c or {}).get("Status", "")
    return status[3:].split(" (")[0] if status.startswith("Up ") else None


def queue_status(d):
    """Redis stream length and the number of entries the detector hasn't read yet."""
    try:
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=2)
        length = r.xlen(STREAM)
        waiting = len(r.xrange(STREAM, f"({d.last_id}", "+", count=QUEUE_WARN * 10)) if d.last_id else 0
        return {"length": length, "waiting": waiting, "capped": waiting >= QUEUE_WARN * 10}
    except redis.RedisError:
        return None


def system_status(d):
    """Services (docker state + log counts), pipeline steps and per-minute log volume for the dashboard."""
    now = time.time()
    containers = docker_containers()
    minutes = d.complete_minutes(now)[-12:]
    with d.lock:
        alerts = Counter((a["source"], a["level"]) for a in d.all_alerts())
        per_minute = {s: dict(d.per_minute.get(s, {})) for s in LIVE_SERVICES}
        last_received = dict(d.last_received)
    services = []
    for s in LIVE_SERVICES:
        c = containers.get(s) if containers is not None else None
        seen = s in last_received
        pack = d.packs.get(s)
        services.append({
            "name": s, "container": c.get("Name") if c else None, "state": c.get("State") if c else None,
            "status": c.get("Status") if c else None,
            "health": container_health(c) if containers is not None else None, "uptime": uptime(c),
            "logs_per_minute": d.lines_last_minute(s, now) if seen else None,
            "last_line_received": iso(last_received[s]) if seen else None,
            "sparkline": [per_minute[s].get(m, 0) for m in minutes] if seen else [],
            "alerts": alerts[(s, "Alert")], "new_templates": alerts[(s, "New template")],
            "models": list(pack.detectors) if pack else [],
        })

    steps = []
    if containers is None:
        steps.append({"name": "Servers", "detail": "docker compose ps failed", "health": None})
    else:
        running = sum(s["state"] == "running" for s in services)
        steps.append({"name": "Servers", "detail": f"{running}/{len(services)} containers running",
                      "health": "healthy" if running == len(services) else "warning" if running else "down"})
    live_seen = [last_received[s] for s in LIVE_SERVICES if s in last_received]
    if live_seen:
        age = now - max(live_seen)
        steps.append({"name": "Log collector", "detail": f"last live line {age:.0f} s ago",
                      "health": "healthy" if age < COLLECTOR_STALE else "warning"})
    else:
        steps.append({"name": "Log collector", "detail": "no data yet", "health": None})
    queue = queue_status(d)
    if queue is None:
        steps.append({"name": "Queue", "detail": "Redis not reachable", "health": "down"})
    else:
        waiting = f"{queue['waiting']:,}{'+' if queue['capped'] else ''}"
        steps.append({"name": "Queue", "detail": f"Redis stream: {waiting} waiting, {queue['length']:,} kept",
                      "health": "healthy" if queue["waiting"] < QUEUE_WARN else "warning"})
    templates = sum(len(p.event_cols) for p in d.packs.values())
    new = sum(len(w) for w in d.warned.values())
    steps.append({"name": "Parser", "detail": f"Drain3: {templates:,} templates in {len(d.packs)} packs, {new:,} new seen"
                  if d.counts["lines"] else "no data yet", "health": "healthy" if d.counts["lines"] else None})
    n_models = sum(len(p.detectors) for p in d.packs.values())
    steps.append({"name": "Models", "detail": f"{n_models} detectors in {len(d.packs)} packs, {d.counts['windows']:,} windows scored"
                  if d.packs else "no packs loaded", "health": "healthy" if d.packs else "down"})
    explained = d.counts["Alert"] + d.counts["New template"]
    steps.append({"name": "Explanation", "detail": f"{explained:,} alerts explained (SHAP for Random Forest, top events otherwise)",
                  "health": "healthy" if d.packs else None})
    return {"services": services, "pipeline": steps, "volume": d.volume(now), "docker_available": containers is not None}


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
def logs(limit: int = 200, service: str | None = None):
    """The last `limit` lines of each source (or of one source label, e.g. "nginx", "hdfs (replay)"), newest first."""
    with detector.lock:
        sources = [service] if service else list(detector.logs)
        lines = [line for s in sources for line in list(detector.logs.get(s, ()))[-limit:]]
    return sorted(lines, key=lambda line: line["id"], reverse=True)


@app.get("/api/alerts")
def alerts(limit: int = 200):
    with detector.lock:
        return detector.all_alerts(limit)  # the last `limit` of each source


@app.get("/api/stats")
def stats():
    return detector.stats()


@app.get("/api/models")
def models():
    return model_results()


@app.get("/api/packs")
def packs():
    return detector.packs_info()


@app.get("/api/system")
def system():
    return system_status(detector)


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
