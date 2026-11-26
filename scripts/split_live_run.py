"""Split a collected live run in time: a training part and a held-out part (by each line's Docker timestamp).

    python scripts/split_live_run.py data/raw/live_long --train-until 2026-11-25T19:59:00Z --heldout-until 2026-11-25T20:59:00Z

Writes <run>/train/<service>_normal.log (lines before --train-until) and <run>/heldout/<service>_normal.log
(lines from --train-until up to --heldout-until; later lines are dropped). The run's own files are not changed.
Use minute boundaries, so the held-out part has only full 1-minute windows.
"""

import argparse
from pathlib import Path

SERVICES = ["nginx", "app", "postgres", "ssh"]


def to_key(ts):
    """'2026-11-25T19:59:00Z' -> '2026-11-25T19:59:00' (Docker timestamps sort as text from here)."""
    return ts.rstrip("Z")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--train-until", required=True, help="UTC time, e.g. 2026-11-25T19:59:00Z")
    parser.add_argument("--heldout-until", required=True)
    parser.add_argument("--label", default="normal")
    args = parser.parse_args()
    run, cut, end = Path(args.run_dir), to_key(args.train_until), to_key(args.heldout_until)
    for part in ["train", "heldout"]:
        (run / part).mkdir(exist_ok=True)
    for service in SERVICES:
        counts = {"train": 0, "heldout": 0, "dropped": 0}
        with open(run / f"{service}_{args.label}.log", encoding="utf-8", errors="replace") as f, \
                open(run / "train" / f"{service}_{args.label}.log", "w", encoding="utf-8") as train, \
                open(run / "heldout" / f"{service}_{args.label}.log", "w", encoding="utf-8") as heldout:
            for line in f:
                ts = line.split(" ", 1)[0][:19]  # seconds precision is enough for minute boundaries
                if ts < cut:
                    train.write(line)
                    counts["train"] += 1
                elif ts < end:
                    heldout.write(line)
                    counts["heldout"] += 1
                else:
                    counts["dropped"] += 1
        print(f"{service:9s} train {counts['train']:6,}  held out {counts['heldout']:6,}  dropped {counts['dropped']:,}")


if __name__ == "__main__":
    main()
