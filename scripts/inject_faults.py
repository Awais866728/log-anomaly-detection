"""Inject faults into the Docker test environment and record when each one starts and ends (UTC).

Scenarios (each lasts about 60 s):
  db        database failure: stop the postgres container for 60 s, then start it again
  overload  traffic overload: an extra Locust run with many users for 60 s, on top of the normal traffic
  ssh       password guessing: 30 failed SSH logins in 60 s (wrong passwords, mostly invalid users)

Normal traffic runs for the whole experiment, as in the normal log run used to train the live packs:
Locust with 20 users and occasional successful SSH logins (scripts/ssh_normal_activity.py).

    python scripts/inject_faults.py --runs 5                     # 5 x db, overload, ssh, in rotation (~2 h)
    python scripts/inject_faults.py --scenarios ssh --runs 1 --warmup 60 --gap 60   # quick test

One CSV row per run is appended to --out as soon as the run ends: run, scenario, affected services,
fault_start, fault_end (ISO 8601 UTC) and details. The first row before the runs (scenario "experiment")
marks the start of the experiment, and a final row marks its end.
"""

import argparse
import csv
import logging
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
DOCKER = ROOT / "docker"
COMPOSE = ["docker", "compose", "-f", str(DOCKER / "docker-compose.yml")]
LOCUST = [str(Path(sys.executable).parent / "locust"), "-f", str(DOCKER / "locust" / "locustfile.py"), "--headless",
          "--host", "http://localhost:8080"]
AFFECTED = {"db": "postgres,app,nginx", "overload": "nginx,app,postgres", "ssh": "ssh"}
FIELDS = ["run", "scenario", "affected", "fault_start", "fault_end", "details"]
FAULT_SECONDS = 60


def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def log(message):
    print(f"{now():%H:%M:%S} UTC  {message}", flush=True)


def database_failure():
    start = now()
    subprocess.run(COMPOSE + ["stop", "postgres"], check=True, capture_output=True)
    time.sleep(max(0.0, FAULT_SECONDS - (now() - start).total_seconds()))
    subprocess.run(COMPOSE + ["start", "postgres"], check=True, capture_output=True)
    return start, now(), "postgres stopped, started again after 60 s"


def traffic_overload(users):
    start = now()
    subprocess.run(LOCUST + ["-u", str(users), "-r", str(users), "-t", f"{FAULT_SECONDS}s", "--only-summary"],
                   cwd=DOCKER, capture_output=True)  # Locust exits 1 when requests fail, which is expected here
    return start, now(), f"{users} extra Locust users for 60 s (normal: 20)"


def password_guessing(attempts=30, port=2222):
    users = ["root", "admin", "oracle", "test", "ubuntu", "postgres", "guest", "user", "ftp", "pi"]
    start, failures, refused = now(), 0, 0
    t0 = time.monotonic()
    for i in range(attempts):
        time.sleep(max(0.0, t0 + i * FAULT_SECONDS / attempts - time.monotonic()))  # evenly over 60 s
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # local test server only
        try:
            client.connect("127.0.0.1", port=port, username=random.choice(users), password=f"guess{i}",
                           look_for_keys=False, allow_agent=False, timeout=5, banner_timeout=5, auth_timeout=5)
        except paramiko.AuthenticationException:
            failures += 1
        except Exception:  # OpenSSH's per-source penalties refuse some connections after repeated failures
            refused += 1
        finally:
            client.close()
    return start, now(), f"{attempts} attempts: {failures} failed passwords, {refused} connections refused"


def background_traffic(total_seconds):
    """Normal traffic for the whole experiment: 20 Locust users and occasional successful SSH logins."""
    minutes = total_seconds / 60
    locust = subprocess.Popen(LOCUST + ["-u", "20", "-r", "2", "-t", f"{int(total_seconds)}s"], cwd=DOCKER,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logins = max(1, round(minutes * 60 / 90))  # same rate as the 90-minute normal run (60 logins)
    ssh = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "ssh_normal_activity.py"), "--minutes", f"{minutes:.1f}",
                            "--logins", str(logins)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return [locust, ssh]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", nargs="+", default=["db", "overload", "ssh"], choices=list(AFFECTED))
    parser.add_argument("--runs", type=int, default=5, help="runs per scenario (done in rotation)")
    parser.add_argument("--warmup", type=float, default=300, help="seconds of normal traffic before the first run")
    parser.add_argument("--gap", type=float, default=420,
                        help="seconds from one fault's end to the next fault's start (3-min detection window + 5 min normal)")
    parser.add_argument("--overload-users", type=int, default=300)
    parser.add_argument("--no-background", action="store_true", help="don't start the normal traffic (already running)")
    parser.add_argument("--out", default=str(ROOT / "docs" / "fault_runs.csv"))
    args = parser.parse_args()
    logging.getLogger("paramiko").setLevel(logging.CRITICAL)
    os.environ.setdefault("SSH_USER", "testuser")

    plan = [s for _ in range(args.runs) for s in args.scenarios]
    total = args.warmup + len(plan) * (FAULT_SECONDS + 15 + args.gap)  # 15 s slack per run
    background = [] if args.no_background else background_traffic(total)

    out = Path(args.out)
    new_file = not out.exists()
    with open(out, "a", newline="") as f:
        writer = csv.DictWriter(f, FIELDS)
        if new_file:
            writer.writeheader()
        experiment_start = now()
        writer.writerow({"run": 0, "scenario": "experiment", "affected": "", "fault_start": iso(experiment_start),
                         "fault_end": "", "details": f"start; {len(plan)} runs, gap {args.gap:.0f} s"})
        f.flush()
        log(f"{len(plan)} runs planned (~{total / 60:.0f} min); warm-up {args.warmup:.0f} s of normal traffic")
        time.sleep(args.warmup)

        for run, scenario in enumerate(plan, start=1):
            log(f"run {run}/{len(plan)}: {scenario} starts")
            if scenario == "db":
                start, end, details = database_failure()
            elif scenario == "overload":
                start, end, details = traffic_overload(args.overload_users)
            else:
                start, end, details = password_guessing()
            writer.writerow({"run": run, "scenario": scenario, "affected": AFFECTED[scenario],
                             "fault_start": iso(start), "fault_end": iso(end), "details": details})
            f.flush()
            log(f"run {run}/{len(plan)}: {scenario} ended ({details}); {args.gap:.0f} s normal traffic")
            time.sleep(args.gap)

        writer.writerow({"run": len(plan) + 1, "scenario": "experiment", "affected": "", "fault_start": iso(now()),
                         "fault_end": "", "details": "end"})
    for p in background:
        p.terminate()
    log("done")


if __name__ == "__main__":
    main()
