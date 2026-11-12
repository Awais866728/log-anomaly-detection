"""Random Forest training, evaluation and explanation helpers."""

import time

import numpy as np
import pandas as pd
import shap
from imblearn.over_sampling import SMOTE
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

from src.evaluation.metrics import evaluate

SEED = 42


def train_rf(X_train, y_train, method="none", n_estimators=100, random_state=SEED):
    """Train a Random Forest with method 'none', 'balanced' or 'smote'; returns (model, fit_seconds)."""
    start = time.perf_counter()
    if method == "smote":
        X_train, y_train = SMOTE(random_state=random_state).fit_resample(X_train, y_train)
    class_weight = "balanced" if method == "balanced" else None
    model = RandomForestClassifier(
        n_estimators=n_estimators, class_weight=class_weight, random_state=random_state, n_jobs=-1
    ).fit(X_train, y_train)
    return model, time.perf_counter() - start


def evaluate_rf(model, X_test, y_test):
    """metrics.evaluate on the predicted labels plus ROC-AUC on the anomaly probability."""
    proba = model.predict_proba(X_test)[:, 1]
    return {**evaluate(y_test, model.predict(X_test)), "roc_auc": roc_auc_score(y_test, proba)}


def top_importances(model, feature_names, templates, n=10):
    """Top n impurity-based feature importances with their template text."""
    return (
        pd.DataFrame({"event": feature_names, "importance": model.feature_importances_})
        .assign(template=lambda d: d["event"].map(templates))
        .nlargest(n, "importance")
        .reset_index(drop=True)
    )


def shap_top_events(model, x, feature_names, templates, n=3, background=None):
    """SHAP contributions to the anomaly class for one sample (1-row DataFrame); returns the top n."""
    if background is None:
        explainer = shap.TreeExplainer(model)
    else:
        # needed for very deep trees (e.g. BGL), where the default algorithm gives wrong values
        explainer = shap.TreeExplainer(model, data=background, feature_perturbation="interventional")
    values = explainer.shap_values(x)
    # older shap returns a list per class, newer an array (samples, features, classes)
    anomaly = values[1] if isinstance(values, list) else values[..., 1]
    return (
        pd.DataFrame({"event": feature_names, "count": x.iloc[0].to_numpy(), "shap": np.ravel(anomaly)})
        .assign(template=lambda d: d["event"].map(templates))
        .nlargest(n, "shap")
        .reset_index(drop=True)
    )
