"""Detection results of fault-injection runs, from the detection service's alert log.

runs:   docs/fault_runs.csv written by scripts/inject_faults.py (one row per run, plus "experiment" start/end rows)
alerts: the JSON-lines file the detection service writes when ALERT_LOG is set (one alert per line)
"""

import json

import pandas as pd

LIVE_SOURCES = ["nginx", "app", "postgres", "ssh"]


def load_runs(path):
    runs = pd.read_csv(path)
    for col in ["fault_start", "fault_end"]:
        runs[col] = pd.to_datetime(runs[col], utc=True, format="ISO8601")
    experiment = runs[runs["scenario"] == "experiment"]
    faults = runs[runs["scenario"] != "experiment"].reset_index(drop=True)
    return faults, experiment["fault_start"].min(), experiment["fault_start"].max()


def load_alerts(path):
    """Live-service alerts with window_start (start of the 1-minute window) and alert_time as UTC timestamps."""
    with open(path, encoding="utf-8") as f:
        alerts = pd.DataFrame([json.loads(line) for line in f if line.strip()])
    alerts = alerts[alerts["source"].isin(LIVE_SOURCES)].copy()
    alerts["alert_time"] = pd.to_datetime(alerts["alert_time"], utc=True, format="ISO8601")
    alerts["window_start"] = pd.to_datetime(alerts["window_id"].astype(float), unit="s", utc=True)
    return alerts.sort_values("alert_time").reset_index(drop=True)


def detection_results(faults, alerts, within=180):
    """Per run: detected (an Alert for an affected service within `within` s of the fault start), latency
    (first such alert time - fault start, seconds), models that fired and alert levels.

    The *_any columns also count "New template" warnings.
    """
    rows = []
    for run in faults.itertuples():
        affected = run.affected.split(",")
        in_time = alerts[alerts["source"].isin(affected) & (alerts["alert_time"] >= run.fault_start)
                         & (alerts["alert_time"] <= run.fault_start + pd.Timedelta(seconds=within))]
        model_alerts = in_time[in_time["level"] == "Alert"]
        first_alert = model_alerts["alert_time"].min() if len(model_alerts) else None
        first_any = in_time["alert_time"].min() if len(in_time) else None
        rows.append({
            "run": run.run, "scenario": run.scenario, "fault_start": run.fault_start, "fault_end": run.fault_end,
            "detected": len(model_alerts) > 0,
            "latency_s": (first_alert - run.fault_start).total_seconds() if first_alert is not None else None,
            "first_alert_service": model_alerts.iloc[0]["source"] if len(model_alerts) else None,
            "models_fired": ", ".join(sorted({m for ms in model_alerts["flagged_by"] for m in ms})),
            "alerts": len(model_alerts),
            "new_template_warnings": int((in_time["level"] == "New template").sum()),
            "detected_any": len(in_time) > 0,
            "latency_any_s": (first_any - run.fault_start).total_seconds() if first_any is not None else None,
            "levels": ", ".join(sorted(in_time["level"].unique())),
        })
    return pd.DataFrame(rows)


def scenario_summary(results):
    """Detection rate and median / min / max latency per scenario."""
    return results.groupby("scenario", sort=False).agg(
        runs=("run", "size"), detected=("detected", "sum"), detection_rate=("detected", "mean"),
        median_latency_s=("latency_s", "median"), min_latency_s=("latency_s", "min"), max_latency_s=("latency_s", "max"),
        detected_incl_new_template=("detected_any", "sum"), median_latency_incl_new_template_s=("latency_any_s", "median"),
    ).reset_index()


def fault_windows(faults, recovery=120):
    """Time ranges that are not normal: each fault plus `recovery` seconds after its end."""
    return [(r.fault_start, r.fault_end + pd.Timedelta(seconds=recovery)) for r in faults.itertuples()]


def false_alerts(faults, alerts, experiment_start, experiment_end, recovery=120, window=60):
    """Alerts in normal periods: their 1-minute window overlaps no fault (plus recovery time).

    The first 2 minutes of the experiment are skipped (the service drops the partly collected first window).
    Returns (per-alert table, normal hours, summary per service and level).
    """
    excluded = fault_windows(faults, recovery)
    span_start = experiment_start + pd.Timedelta(minutes=2)
    w = alerts[(alerts["window_start"] >= span_start) & (alerts["window_start"] < experiment_end)]

    def overlaps(start):
        end = start + pd.Timedelta(seconds=window)
        return any(start < e and end > s for s, e in excluded)

    normal = w[~w["window_start"].map(overlaps)]
    # normal time: the 1-minute windows of the span that overlap no fault range
    minutes = pd.date_range(span_start.ceil("min"), experiment_end.floor("min"), freq="min", inclusive="left")
    normal_hours = sum(not overlaps(m) for m in minutes) / 60
    summary = (normal.groupby(["source", "level"]).size().rename("alerts").reset_index()
               .assign(per_hour=lambda d: d["alerts"] / normal_hours))
    return normal, normal_hours, summary
