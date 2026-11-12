"""A few successful SSH logins spread over a time period, each running a couple of ordinary commands.

Run from the project root:  python scripts/ssh_normal_activity.py --minutes 10 --logins 6
"""

import argparse
import os
import random
import time

import paramiko

COMMANDS = ["whoami", "uptime", "ls -la", "df -h", "date", "cat /etc/os-release"]


def login(host, port, user, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # local test server only
    client.connect(host, port=port, username=user, password=password, look_for_keys=False, allow_agent=False)
    for cmd in random.sample(COMMANDS, 2):
        _, stdout, _ = client.exec_command(cmd)
        stdout.channel.recv_exit_status()
        time.sleep(random.uniform(1, 4))
    client.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=10)
    parser.add_argument("--logins", type=int, default=6)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2222)
    args = parser.parse_args()
    user = os.environ.get("SSH_USER", "testuser")
    password = os.environ.get("SSH_PASSWORD", "testpass")

    # random login times spread over the whole period
    total = args.minutes * 60
    times = sorted(random.uniform(0, total) for _ in range(args.logins))
    start = time.monotonic()
    for i, t in enumerate(times, start=1):
        time.sleep(max(0, start + t - time.monotonic()))
        login(args.host, args.port, user, password)
        print(f"[{time.strftime('%H:%M:%S')}] login {i}/{args.logins} as {user} ok", flush=True)
    time.sleep(max(0, start + total - time.monotonic()))


if __name__ == "__main__":
    main()
