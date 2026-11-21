"""Random Forest training, evaluation and explanation helpers."""

import json
import time

import numpy as np
import pandas as pd
import shap
from imblearn.over_sampling import SMOTE
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

from src.evaluation.metrics import evaluate
from src.models.unsupervised import has_unseen, time_split_val, unseen_columns

SEED = 42
METHODS = ["none", "balanced", "smote"]


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


def select_rf_method(counts, order_col="order", methods=METHODS):
    """Fit each imbalance method on the first 60%, choose by F1 on the next 10%, evaluate the choice on the last 30%.

    Returns a dict with the validation table, the test row of the chosen method, its model, the three parts
    and the event columns.
    """
    event_cols = list(counts.filter(regex=r"^E\d+$").columns)
    fit, val, test = time_split_val(counts, order_col=order_col)
    models, val_rows = {}, []
    for method in methods:
        models[method], fit_s = train_rf(fit[event_cols], fit["Label"], method=method)
        val_rows.append({"method": method, **evaluate_rf(models[method], val[event_cols], val["Label"]),
                         "train_seconds": fit_s})
    val_table = pd.DataFrame(val_rows)
    best = val_table.loc[val_table["f1"].idxmax(), "method"]  # first method on ties
    test_row = {"method": best, "val_f1": val_table["f1"].max(),
                **evaluate_rf(models[best], test[event_cols], test["Label"])}
    return {"val": val_table, "test": test_row, "model": models[best], "method": best,
            "parts": (fit, val, test), "event_cols": event_cols}


def hybrid_predict(model, X, unseen):
    """Anomaly if the Random Forest says so OR the row has an event from the unseen_columns mask."""
    return ((model.predict(X) == 1) | has_unseen(X, unseen)).astype(int)


def explain_alert(model, x, window_id, dataset, feature_names, templates, unseen,
                  model_name="Random Forest", background=None, n=3):
    """JSON-ready explanation of one flagged window (x: 1-row DataFrame).

    reason "model": the Random Forest flags it; top_events are the n events with the largest SHAP value.
    reason "unseen event": only the unseen-event rule flags it; top_events are its unseen events (shap = None).
    """
    proba = float(model.predict_proba(x)[0, 1])
    alert = {"window_id": window_id if isinstance(window_id, str) else int(window_id), "dataset": dataset,
             "model": model_name, "anomaly_probability": round(proba, 4)}
    if model.predict(x)[0] == 1:
        top = shap_top_events(model, x, feature_names, templates, n=n, background=background)
        alert["reason"] = "model"
        alert["top_events"] = [{"event": r.event, "template": r.template, "count": int(r.count), "shap": round(float(r.shap), 4)}
                               for r in top.itertuples()]
    else:
        counts = x.iloc[0]
        new = counts[np.asarray(unseen) & (counts.to_numpy() > 0)].sort_values(ascending=False, kind="stable")
        if new.empty:
            raise ValueError(f"window {window_id} is not flagged by the model or the unseen-event rule")
        alert["reason"] = "unseen event"
        alert["top_events"] = [{"event": e, "template": templates[e], "count": int(c), "shap": None} for e, c in new.items()]
    return alert


def example_alerts(model, test, event_cols, unseen, dataset, templates, id_col,
                   n=20, n_unseen=5, background=None, seed=SEED):
    """Explanations for n flagged test windows: up to n_unseen flagged only by the unseen-event rule, the rest by
    the model. Picked at random (seed), returned in time order."""
    X = test[event_cols]
    by_model = model.predict(X) == 1
    unseen_only = has_unseen(X, unseen) & ~by_model
    rng = np.random.default_rng(seed)
    pick_unseen = rng.choice(np.flatnonzero(unseen_only), min(n_unseen, unseen_only.sum()), replace=False)
    pick_model = rng.choice(np.flatnonzero(by_model), min(n - len(pick_unseen), by_model.sum()), replace=False)
    return [explain_alert(model, X.iloc[[pos]], test[id_col].iloc[pos], dataset, event_cols, templates, unseen,
                          background=background)
            for pos in np.sort(np.concatenate([pick_model, pick_unseen]))]


def save_alerts(alerts, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2, ensure_ascii=False)
