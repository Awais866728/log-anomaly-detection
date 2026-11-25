"""Save each docker compose service's logs to data/raw/live/<service>_<label>.log and print line counts.

Every line starts with Docker's receive time (RFC 3339, UTC), e.g.
"2026-11-21T16:19:04.364771273Z Accepted password for testuser ...", because some services
(the SSH server) write no timestamp of their own.

Run from the project root:
    python scripts/collect_logs.py                                   # snapshot of everything so far
    python scripts/collect_logs.py --since 2026-11-21T15:00:00Z      # snapshot from a start time
    python scripts/collect_logs.py --follow --since <start> --out-dir data/raw/live_long
        # keep writing new lines as they arrive, until stopped (Ctrl+C / SIGTERM); used for long runs
"""

import argparse
import signal
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker" / "docker-compose.yml"
OUT_DIR = ROOT / "data" / "raw" / "live"
SERVICES = ["nginx", "app", "postgres", "ssh"]
LOGS = ["docker", "compose", "-f", str(COMPOSE_FILE), "logs", "--no-color", "--no-log-prefix", "--timestamps"]


def snapshot(out_dir, label, since):
    for service in SERVICES:
        command = LOGS + (["--since", since] if since else [])
        result = subprocess.run(command + [service], capture_output=True, text=True, check=True)
        # docker compose logs merges the container's stdout and stderr into stdout
        path = out_dir / f"{service}_{label}.log"
        path.write_text(result.stdout)
        print(f"{service:10s} {len(result.stdout.splitlines()):6d} lines -> {_relative(path)}")


def follow(out_dir, label, since):
    """One `docker compose logs --follow` per service, appended to its file. If it ends (e.g. the container was
    restarted), it is started again from the last timestamp written, skipping lines already written."""
    stop, procs = threading.Event(), {}

    def run(service):
        path, last = out_dir / f"{service}_{label}.log", None
        with open(path, "a", encoding="utf-8") as f:
            while not stop.is_set():
                command = LOGS + ["--follow"] + (["--since", last or since] if (last or since) else []) + [service]
                procs[service] = proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                                         text=True, errors="replace")
                for line in proc.stdout:
                    ts = line.split(" ", 1)[0]
                    if last is not None and ts <= last:  # already written before a restart
                        continue
                    f.write(line)
                    f.flush()
                    last = ts
                proc.wait()
                if not stop.is_set():
                    time.sleep(2)

    def shutdown(*_):
        stop.set()
        for proc in list(procs.values()):
            proc.terminate()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    threads = [threading.Thread(target=run, args=(s,), daemon=True) for s in SERVICES]
    for t in threads:
        t.start()
    print(f"following {', '.join(SERVICES)} -> {_relative(out_dir)}/<service>_{label}.log", flush=True)
    while not stop.is_set():
        time.sleep(1)
    for t in threads:
        t.join(timeout=10)


def _relative(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="normal", help="file name suffix, e.g. normal")
    parser.add_argument("--since", help="only logs after this time, e.g. 30m or 2026-11-21T15:00:00Z")
    parser.add_argument("--out-dir", default=str(OUT_DIR), help="folder for the log files (default data/raw/live)")
    parser.add_argument("--follow", action="store_true", help="keep writing new lines until stopped")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.follow:
        follow(out_dir, args.label, args.since)
    else:
        snapshot(out_dir, args.label, args.since)


if __name__ == "__main__":
    main()
