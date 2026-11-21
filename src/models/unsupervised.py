"""Unsupervised anomaly detectors (PCA, Isolation Forest) and threshold helpers."""

import time

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest

from src.evaluation.metrics import evaluate


def time_split(df, train_frac=0.7, order_col="order"):
    """Sort by first-appearance order and split into (train, test) without shuffling."""
    df = df.sort_values(order_col).reset_index(drop=True)
    n_train = int(len(df) * train_frac)
    return df.iloc[:n_train], df.iloc[n_train:]


def time_split_val(df, fit_frac=0.6, val_frac=0.1, order_col="order"):
    """Time-ordered (fit, validation, test) split: first 60%, next 10%, last 30%.

    The test part is the same as time_split(df, fit_frac + val_frac).
    """
    train, test = time_split(df, fit_frac + val_frac, order_col)
    n_fit = int(len(df) * fit_frac)
    return train.iloc[:n_fit], train.iloc[n_fit:], test


class TfidfZeroMean:
    """TF-IDF weighting followed by zero-mean normalisation, as in He et al. (2016) / loglizer."""

    def fit(self, X):
        X = np.asarray(X, dtype=float)
        doc_freq = (X > 0).sum(axis=0)
        self.idf = np.log(len(X) / (doc_freq + 1e-8))
        self.mean = (X * self.idf).mean(axis=0)
        return self

    def transform(self, X):
        return np.asarray(X, dtype=float) * self.idf - self.mean


class PCADetector:
    """Score = squared reconstruction error after projecting onto the main PCA components."""

    def __init__(self, variance=0.95):
        self.variance = variance

    def fit(self, X):
        self.tfidf = TfidfZeroMean().fit(X)
        self.pca = PCA(n_components=self.variance).fit(self.tfidf.transform(X))
        return self

    def score(self, X):
        Z = self.tfidf.transform(X)
        return ((Z - self.pca.inverse_transform(self.pca.transform(Z))) ** 2).sum(axis=1)


def unseen_columns(X_train):
    """Boolean mask of event columns that are always 0 in the training rows."""
    return np.asarray(X_train).sum(axis=0) == 0


def has_unseen(X, unseen):
    """True for rows with at least one event from an unseen_columns mask."""
    return np.asarray(X)[:, unseen].sum(axis=1) > 0


class IForestDetector:
    """Isolation Forest on raw counts; score = -score_samples, so higher means more anomalous.

    max_samples: rows per tree ("auto" = 256, 1.0 = all training rows).
    flag_unseen: add 1 to the score of rows with an event that is always 0 in training. Trees can't split
    on such constant columns, and -score_samples is at most 1, so these rows score above every normal row.
    """

    def __init__(self, n_estimators=100, random_state=42, max_samples="auto", flag_unseen=False):
        self.model = IsolationForest(n_estimators=n_estimators, max_samples=max_samples,
                                     random_state=random_state, n_jobs=-1)
        self.flag_unseen = flag_unseen

    def fit(self, X):
        X = np.asarray(X)
        self.model.fit(X)
        self.unseen = unseen_columns(X)
        return self

    def score(self, X):
        X = np.asarray(X)
        scores = -self.model.score_samples(X)
        if self.flag_unseen:
            scores = scores + has_unseen(X, self.unseen)
        return scores


def fit_and_score(detector, X_train, X_test):
    """Fit on X_train and score both sets; returns (train_scores, test_scores, fit_seconds, score_seconds)."""
    start = time.perf_counter()
    detector.fit(X_train)
    fit_seconds = time.perf_counter() - start

    start = time.perf_counter()
    train_scores, test_scores = detector.score(X_train), detector.score(X_test)
    score_seconds = time.perf_counter() - start
    return train_scores, test_scores, fit_seconds, score_seconds


def threshold_sweep(model_name, train_scores, test_scores, y_test, percentiles):
    """Evaluate the test set with thresholds at the given percentiles of the training scores."""
    rows = []
    for pct in percentiles:
        threshold = np.percentile(train_scores, pct)
        metrics = evaluate(y_test, test_scores > threshold)
        rows.append({
            "model": model_name,
            "percentile": pct,
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "false_alarm_rate": metrics["false_alarm_rate"],
        })
    return rows


def choose_percentile(model_name, train_scores, val_scores, y_val, test_scores, y_test, percentiles):
    """Pick the percentile with the best validation F1 (first one on ties), then evaluate the test set with it.

    Returns (validation rows for all percentiles, one test row for the chosen percentile).
    """
    val_rows = threshold_sweep(model_name, train_scores, val_scores, y_val, percentiles)
    best = max(val_rows, key=lambda r: r["f1"])
    test_row = threshold_sweep(model_name, train_scores, test_scores, y_test, [best["percentile"]])[0]
    return val_rows, {**test_row, "val_f1": best["f1"]}


def validated_sweeps(counts, detectors, percentiles, order_col="order"):
    """Fit each detector on the normal rows of the first 60%; evaluate every percentile on the next 10% and the last 30%.

    detectors: {name: detector}. Returns (validation table, test table), one row per detector and percentile.
    The test table also has flag_rate (share of test rows above the threshold).
    """
    event_cols = counts.filter(regex=r"^E\d+$").columns
    fit, val, test = time_split_val(counts, order_col=order_col)
    X_fit = fit.loc[fit["Label"] == 0, event_cols].to_numpy()
    X_val, y_val = val[event_cols].to_numpy(), val["Label"].to_numpy()
    X_test, y_test = test[event_cols].to_numpy(), test["Label"].to_numpy()

    val_rows, test_rows = [], []
    for name, detector in detectors.items():
        detector.fit(X_fit)
        fit_scores, test_scores = detector.score(X_fit), detector.score(X_test)
        val_rows += threshold_sweep(name, fit_scores, detector.score(X_val), y_val, percentiles)
        for row in threshold_sweep(name, fit_scores, test_scores, y_test, percentiles):
            row["flag_rate"] = float((test_scores > np.percentile(fit_scores, row["percentile"])).mean())
            test_rows.append(row)
    return pd.DataFrame(val_rows), pd.DataFrame(test_rows)


def pick_best(val_table, test_table, setting="percentile", group="model"):
    """Per group, the setting with the best validation F1 (first on ties) and its test row (with val_f1)."""
    best = val_table.loc[val_table.groupby(group, sort=False)["f1"].idxmax(), [group, setting, "f1"]]
    return best.rename(columns={"f1": "val_f1"}).merge(test_table, on=[group, setting])


def validated_results(counts, detectors, percentiles, order_col="order"):
    """Fit each detector on the normal rows of the first 60%, pick the percentile on the next 10%, test on the last 30%.

    detectors: {name: detector}. Returns (validation table, test table with one row per detector).
    """
    val_table, test_table = validated_sweeps(counts, detectors, percentiles, order_col)
    chosen = pick_best(val_table, test_table)
    return val_table, chosen[[c for c in chosen.columns if c != "flag_rate"]]


def score_unlabelled(counts, detector, train_frac=0.7, order_col="window"):
    """Fit on the first train_frac of windows (assumed normal) and score the rest.

    Returns (test windows, test scores, training scores).
    """
    event_cols = counts.filter(regex=r"^E\d+$").columns
    train, test = time_split(counts, train_frac, order_col)
    train_scores, test_scores, _, _ = fit_and_score(detector, train[event_cols].to_numpy(), test[event_cols].to_numpy())
    return test, test_scores, train_scores


def top_flagged(windows, scores, templates, n=5, n_events=3, known_events=None):
    """The n highest-scoring windows with their most frequent events (template text).

    windows: rows of a *_sequences table (with "window" and "EventSequence"), in the same order as scores.
    known_events: if given, also list the window's events that are not in this set.
    """
    rows = []
    for pos in np.argsort(-scores, kind="stable")[:n]:
        seq = pd.Series(windows["EventSequence"].iloc[pos])
        top = seq.value_counts().head(n_events)
        row = {
            "window": windows["window"].iloc[pos],
            "score": scores[pos],
            "lines": len(seq),
            "top events": "; ".join(f"{e} x{c}: {templates[e]}" for e, c in top.items()),
        }
        if known_events is not None:
            row["unseen events"] = "; ".join(f"{e}: {templates[e]}" for e in dict.fromkeys(seq) if e not in known_events)
        rows.append(row)
    return pd.DataFrame(rows)
