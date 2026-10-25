"""Turn parsed log lines into fixed-window event-count features.

Run from the project root:  python -m src.features.build_features
"""

from pathlib import Path

import pandas as pd

from src.parsing.drain_parser import parse_log_file

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def bgl_line_labels(path):
    """BGL lines start with their label: '-' for normal, an alert category otherwise."""
    with open(path, encoding="utf-8", errors="replace") as f:
        return [line.split(maxsplit=1)[0] for line in f if line.strip()]


def window_event_counts(cluster_ids, line_is_anomaly, window_size=20):
    """Split lines in order into windows of ``window_size`` and count each template per window.

    Returns (X, y): X has one row per window and one column per template ("E<cluster id>"),
    y is 1 if any line in the window is an anomaly. A final partial window is dropped.
    """
    lines = pd.DataFrame({"ClusterId": list(cluster_ids), "Anomaly": list(line_is_anomaly)})
    n_windows = len(lines) // window_size
    lines = lines.iloc[: n_windows * window_size]
    lines["Window"] = lines.index // window_size

    X = pd.crosstab(lines["Window"], lines["ClusterId"])
    # Keep a column for every template, even ones only seen in a dropped partial window
    all_ids = sorted(set(cluster_ids))
    X = X.reindex(columns=all_ids, fill_value=0)
    X.columns = [f"E{cid}" for cid in all_ids]
    X.index.name = "window"

    y = lines.groupby("Window")["Anomaly"].any().astype(int).rename("label")
    return X, y


def build_bgl_2k(window_size=20):
    log_path = RAW / "BGL" / "BGL_2k.log"
    parsed = parse_log_file(log_path, "BGL")
    is_anomaly = [label != "-" for label in bgl_line_labels(log_path)]

    X, y = window_event_counts(parsed["ClusterId"], is_anomaly, window_size)
    templates = parsed.drop_duplicates("ClusterId").sort_values("ClusterId")
    templates = pd.DataFrame({"column": "E" + templates["ClusterId"].astype(str), "template": templates["Template"]})
    return X, y, templates


def main():
    X, y, templates = build_bgl_2k()

    PROCESSED.mkdir(parents=True, exist_ok=True)
    X.join(y).to_csv(PROCESSED / "bgl_2k_windows.csv")
    templates.to_csv(PROCESSED / "bgl_2k_templates.csv", index=False)

    print(f"X shape: {X.shape}  (windows x templates)")
    print(f"y shape: {y.shape}")
    print(f"Anomaly windows: {y.sum()} of {len(y)} ({y.mean():.1%})")


if __name__ == "__main__":
    main()
