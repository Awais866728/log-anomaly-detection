"""Save each docker compose service's logs to data/raw/live/<service>_<label>.log and print line counts.

Every line starts with Docker's receive time (RFC 3339, UTC), e.g.
"2026-11-21T16:19:04.364771273Z Accepted password for testuser ...", because some services
(the SSH server) write no timestamp of their own.

Run from the project root:  python scripts/collect_logs.py
"""

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker" / "docker-compose.yml"
OUT_DIR = ROOT / "data" / "raw" / "live"
SERVICES = ["nginx", "app", "postgres", "ssh"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="normal", help="file name suffix, e.g. normal")
    parser.add_argument("--since", help="only logs after this time, e.g. 30m or 2026-11-21T15:00:00Z")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for service in SERVICES:
        command = ["docker", "compose", "-f", str(COMPOSE_FILE), "logs", "--no-color", "--no-log-prefix", "--timestamps"]
        if args.since:
            command += ["--since", args.since]
        result = subprocess.run(command + [service], capture_output=True, text=True, check=True)
        # docker compose logs merges the container's stdout and stderr into stdout
        path = OUT_DIR / f"{service}_{args.label}.log"
        path.write_text(result.stdout)
        print(f"{service:10s} {len(result.stdout.splitlines()):6d} lines -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
