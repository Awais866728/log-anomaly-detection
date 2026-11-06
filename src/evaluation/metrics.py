"""Anomaly detection metrics. Labels are binary: 1 = anomaly (positive class), 0 = normal."""

import numpy as np


def _safe_div(num, den):
    # 0.0 instead of NaN/ZeroDivisionError, e.g. precision when nothing is predicted as anomaly
    return num / den if den else 0.0


def evaluate(y_true, y_pred):
    """Return precision, recall, F1, false alarm rate and confusion matrix counts."""
    y_true = np.asarray(y_true).astype(int).ravel()
    y_pred = np.asarray(y_pred).astype(int).ravel()
    if y_true.shape != y_pred.shape:
        raise ValueError(f"y_true and y_pred differ in length: {y_true.size} vs {y_pred.size}")

    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    false_alarm_rate = _safe_div(fp, fp + tn)

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_alarm_rate": false_alarm_rate,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }
