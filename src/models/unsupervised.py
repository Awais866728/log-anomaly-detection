"""Unsupervised anomaly detectors (PCA, Isolation Forest) and threshold helpers."""

import time

import numpy as np
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest

from src.evaluation.metrics import evaluate


def time_split(df, train_frac=0.7, order_col="order"):
    """Sort by first-appearance order and split into (train, test) without shuffling."""
    df = df.sort_values(order_col).reset_index(drop=True)
    n_train = int(len(df) * train_frac)
    return df.iloc[:n_train], df.iloc[n_train:]


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


class IForestDetector:
    """Isolation Forest on raw counts; score = -score_samples, so higher means more anomalous."""

    def __init__(self, n_estimators=100, random_state=42):
        self.model = IsolationForest(n_estimators=n_estimators, random_state=random_state, n_jobs=-1)

    def fit(self, X):
        self.model.fit(X)
        return self

    def score(self, X):
        return -self.model.score_samples(X)


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
