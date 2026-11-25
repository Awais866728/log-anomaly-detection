#!/usr/bin/env bash
# Long normal log run for the live models: normal traffic only (no faults), logs collected with timestamps.
#
# Same load as the earlier normal run: Locust with 20 users (ramp 2/s) and successful SSH logins at the same
# rate (60 per 90 minutes). Logs go to data/raw/live_long/ (not data/raw/live, so the earlier run is kept):
#   <service>_normal.log   collected live during the run, then replaced by a final snapshot at the end
#   run.log                progress: start, line counts every 5 minutes, end
#   start_time.txt / end_time.txt, locust.log, ssh_activity.log, run.pid
#
# Start (from the project root; keeps the laptop awake and survives closing the terminal):
#   setsid nohup systemd-inhibit --what=sleep:idle:handle-lid-switch --who=log-anomaly \
#       --why="3-hour normal log run" scripts/long_normal_run.sh > data/raw/live_long/nohup.out 2>&1 &
# Stop early:  kill -TERM "$(cat data/raw/live_long/run.pid)"     (stops the traffic, takes the final snapshot)

set -u
cd "$(dirname "$0")/.."
MINUTES=${MINUTES:-180}
OUT=$(realpath -m "${OUT:-data/raw/live_long}")
LOGINS=$(( MINUTES * 60 / 90 ))  # same login rate as the 90-minute run
mkdir -p "$OUT"
echo $$ > "$OUT/run.pid"

log() { echo "$(date -u +%FT%TZ)  $*" >> "$OUT/run.log"; }
counts() { for s in nginx app postgres ssh; do printf "%s %s  " "$s" "$(wc -l < "$OUT/${s}_normal.log" 2>/dev/null || echo 0)"; done; }

START=$(date -u +%FT%TZ)
echo "$START" > "$OUT/start_time.txt"
log "start: $MINUTES min, Locust 20 users, $LOGINS SSH logins, no faults"

docker compose -f docker/docker-compose.yml up -d --wait >> "$OUT/run.log" 2>&1
venv/bin/python scripts/collect_logs.py --follow --since "$START" --out-dir "$OUT" >> "$OUT/run.log" 2>&1 &
COLLECTOR=$!
(cd docker && exec ../venv/bin/locust -f locust/locustfile.py --headless -u 20 -r 2 -t "${MINUTES}m" \
    --host http://localhost:8080 >> "$OUT/locust.log" 2>&1) &
LOCUST=$!
SSH_USER=testuser venv/bin/python scripts/ssh_normal_activity.py --minutes "$MINUTES" --logins "$LOGINS" \
    >> "$OUT/ssh_activity.log" 2>&1 &
SSHGEN=$!
log "running: collector pid $COLLECTOR, locust pid $LOCUST, ssh activity pid $SSHGEN"

finish() {
    kill "$LOCUST" "$SSHGEN" 2>/dev/null
    wait "$LOCUST" "$SSHGEN" 2>/dev/null
    sleep 30  # let the last lines reach Docker's logs
    kill -TERM "$COLLECTOR" 2>/dev/null
    wait "$COLLECTOR" 2>/dev/null
    venv/bin/python scripts/collect_logs.py --since "$START" --out-dir "$OUT" >> "$OUT/run.log" 2>&1  # final snapshot
    date -u +%FT%TZ > "$OUT/end_time.txt"
    log "done: $(counts)"
    rm -f "$OUT/run.pid"
    exit 0
}
trap 'log "stop requested"; finish' TERM INT

while kill -0 "$LOCUST" 2>/dev/null || kill -0 "$SSHGEN" 2>/dev/null; do
    for _ in $(seq 300); do  # 5 minutes, in 1-second steps so a stop request is handled quickly
        kill -0 "$LOCUST" 2>/dev/null || kill -0 "$SSHGEN" 2>/dev/null || break
        sleep 1
    done
    log "progress: $(counts)"
done
log "traffic finished after $MINUTES min"
finish
