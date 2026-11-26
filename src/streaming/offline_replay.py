"""Run collected live logs (lines with Docker timestamps) through the detection service's code, without Redis.

Used to count false alerts on held-out normal traffic: the lines of all services are merged in time order and
passed to the service's Detector (same parsing, 1-minute windows, scoring and alert rules). The only difference
from the running service: windows close on the log's own clock (a line from a later minute, or the end of the
logs), because the lines are not arriving now.
"""

import pandas as pd

from src.streaming import service
from src.streaming.common import LIVE_SERVICES
from src.streaming.windows import TimeWindows


def replay_live_logs(log_dir, pack_suffix="", label="normal", dedupe_new_templates=False):
    """Alerts for <log_dir>/<service>_<label>.log with the live packs models/stream_<service><pack_suffix>.joblib.

    Returns (alerts DataFrame, windows scored per service). dedupe_new_templates=False gives a New-template
    warning on every window with an unseen event, as in the fault-injection runs (DEDUPE_NEW_TEMPLATES=0).
    """
    service.LIVE_PACK_SUFFIX, service.DEDUPE_NEW_TEMPLATES, service.ALERT_LOG = pack_suffix, dedupe_new_templates, None
    detector = service.Detector()
    for s in LIVE_SERVICES:
        detector.windows[s] = TimeWindows(s, wall_clock=False)  # no "started" cut: every window is complete

    lines = []
    for s in LIVE_SERVICES:
        with open(f"{log_dir}/{s}_{label}.log", encoding="utf-8", errors="replace") as f:
            lines += [(line.split(" ", 1)[0], s, line.rstrip("\n")) for line in f if line.strip()]
    lines.sort(key=lambda t: t[0])  # Docker's RFC 3339 timestamps sort as text

    windows = {s: 0 for s in LIVE_SERVICES}
    for ts, s, raw in lines:
        received_ms = int(pd.Timestamp(ts).timestamp() * 1000)
        _, closed = detector.handle(f"{received_ms}-0", {"source": s, "kind": "line", "line": raw})
        detector.score_windows(closed)
        for w in closed:
            windows[w.source] += 1
    for s in LIVE_SERVICES:
        closed = detector.windows[s].flush()
        detector.score_windows(closed)
        windows[s] += len(closed)

    with detector.lock:
        alerts = pd.DataFrame(detector.all_alerts(limit=10 ** 6))
    if len(alerts):
        alerts["window_start"] = pd.to_datetime(alerts["window_id"].astype(float), unit="s", utc=True)
    return alerts, windows
