"""Live collector: push new log lines from the Docker services into the Redis stream.

    python -m src.streaming.collector

Follows `docker compose logs --follow --timestamps` for each service (one thread each) and sends every line
with Docker's receive time in front, e.g. "2026-11-21T16:19:04.364771273Z Accepted password for ...".
If a container restarts, the follow command ends and is started again from the time of the last line.
"""

import argparse
import subprocess
import threading
import time
from datetime import datetime, timezone

import redis

from src.streaming.common import LIVE_SERVICES, REDIS_URL, ROOT, STREAM, STREAM_MAXLEN

COMPOSE_FILE = ROOT / "docker" / "docker-compose.yml"


def follow(service, r, since, stop):
    last = ""  # timestamp of the last line sent; RFC 3339 with 9-digit nanoseconds sorts as text
    while not stop.is_set():
        command = ["docker", "compose", "-f", str(COMPOSE_FILE), "logs", "--follow", "--timestamps", "--no-color",
                   "--no-log-prefix", "--since", since, service]
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1) as proc:
            for line in proc.stdout:
                line = line.rstrip("\n")
                ts = line.split(" ", 1)[0]
                if not line or ts <= last:  # --since includes the last line again after a restart
                    continue
                r.xadd(STREAM, {"source": service, "kind": "line", "line": line}, maxlen=STREAM_MAXLEN, approximate=True)
                since = last = ts  # restart from the last line's time
                if stop.is_set():
                    proc.terminate()
                    break
        if not stop.is_set():
            print(f"{service}: log follow ended, restarting in 2 s", flush=True)
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--services", nargs="+", default=LIVE_SERVICES, choices=LIVE_SERVICES)
    args = parser.parse_args()

    r = redis.Redis.from_url(REDIS_URL)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # only new lines
    stop = threading.Event()
    threads = [threading.Thread(target=follow, args=(s, r, now, stop), daemon=True) for s in args.services]
    for t in threads:
        t.start()
    print(f"collecting {', '.join(args.services)} -> redis stream '{STREAM}' (Ctrl+C to stop)", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
