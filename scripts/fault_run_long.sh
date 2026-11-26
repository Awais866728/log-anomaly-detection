#!/usr/bin/env bash
# Fault-injection experiment with the live packs trained on the long normal run (models/stream_<service>_long.joblib).
#
# Same protocol as notebook 17: the detection service (every alert written to an alert log, a New-template warning
# on every window) and the live collector run the whole time; scripts/inject_faults.py starts normal traffic
# (Locust 20 users, occasional SSH logins) and injects the database failure, traffic overload and password
# guessing scenarios 5 times each, in rotation, with 7 minutes between the end of one fault and the next.
#
# Start (from the project root; keeps the laptop awake and survives closing the terminal):
#   setsid nohup systemd-inhibit --what=sleep:idle:handle-lid-switch --who=log-anomaly \
#       --why="fault injection, long packs" scripts/fault_run_long.sh > data/raw/live_long/fault_nohup.out 2>&1 &
# Progress: data/raw/live_long/fault_run.log     Stop early: kill -TERM "$(cat data/raw/live_long/fault_run.pid)"

set -u
cd "$(dirname "$0")/.."
LOGDIR=data/raw/live_long
RUNS=docs/fault_runs_long.csv
ALERTS=data/processed/fault_alerts_long.jsonl
LOG=$LOGDIR/fault_run.log
mkdir -p "$LOGDIR"
echo $$ > "$LOGDIR/fault_run.pid"
log() { echo "$(date -u +%FT%TZ)  $*" >> "$LOG"; }

for f in "$RUNS" "$ALERTS"; do
    if [ -e "$f" ]; then log "refusing to start: $f exists (it would be appended to)"; exit 1; fi
done

docker compose -f docker/docker-compose.yml up -d --wait >> "$LOG" 2>&1
LIVE_PACK_SUFFIX=_long ALERT_LOG="$ALERTS" DEDUPE_NEW_TEMPLATES=0 \
    venv/bin/uvicorn src.streaming.service:app --port 8000 >> "$LOGDIR/fault_service.log" 2>&1 &
SERVICE=$!
for _ in $(seq 120); do curl -sf localhost:8000/health > /dev/null && break; sleep 1; done
log "detection service pid $SERVICE: $(curl -s localhost:8000/health)"
venv/bin/python -m src.streaming.collector >> "$LOGDIR/fault_collector.log" 2>&1 &
COLLECTOR=$!
log "collector pid $COLLECTOR"
sleep 5

venv/bin/python -u scripts/inject_faults.py --runs 5 --out "$RUNS" >> "$LOG" 2>&1 &
FAULTS=$!

finish() {
    kill "$FAULTS" 2>/dev/null
    wait "$FAULTS" 2>/dev/null
    pkill -P "$FAULTS" 2>/dev/null  # its Locust / SSH traffic, if it was stopped early
    sleep 70  # let the last 1-minute window close and be scored
    kill "$COLLECTOR" "$SERVICE" 2>/dev/null
    wait "$COLLECTOR" "$SERVICE" 2>/dev/null
    log "done: $(wc -l < "$ALERTS" 2>/dev/null || echo 0) alerts in $ALERTS, runs in $RUNS"
    rm -f "$LOGDIR/fault_run.pid"
    exit 0
}
trap 'log "stop requested"; finish' TERM INT

while kill -0 "$FAULTS" 2>/dev/null; do sleep 1; done
log "fault injection finished"
finish
