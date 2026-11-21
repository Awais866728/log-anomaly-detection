"""Compare settings chosen on one dataset when they are used on another."""

import pandas as pd


def chosen_settings(val, setting):
    """{(dataset, model): setting value with the best validation F1 (first on ties)}.

    val: validation sweep with columns dataset, model, <setting>, f1.
    """
    best = val.loc[val.groupby(["dataset", "model"], sort=False)["f1"].idxmax()]
    return {(r.dataset, r.model): getattr(r, setting) for r in best.itertuples()}


def chosen_rows(val, test, setting):
    """Test rows at each (dataset, model)'s validation-chosen setting, with its validation F1 as val_f1."""
    val_f1 = val.groupby(["dataset", "model"], sort=False)["f1"].max()
    rows = [test[(test["dataset"] == d) & (test["model"] == m) & (test[setting] == s)].assign(val_f1=val_f1[(d, m)])
            for (d, m), s in chosen_settings(val, setting).items()]
    return pd.concat(rows, ignore_index=True)


def transfer_table(val, test, setting, pairs=(("HDFS", "BGL"), ("BGL", "HDFS"))):
    """Test F1 with a dataset's own validation-chosen setting vs the setting chosen on another dataset.

    val / test: sweeps with columns dataset, model, <setting>, f1 (test also precision, recall, false_alarm_rate).
    pairs: (source, target) = setting chosen on source, used on target.
    """
    chosen = chosen_settings(val, setting)
    test = test.set_index(["dataset", "model", setting])
    rows = []
    for source, target in pairs:
        for model in test.loc[target].index.get_level_values("model").unique():
            own, moved = chosen[(target, model)], chosen[(source, model)]
            own_row, moved_row = test.loc[(target, model, own)], test.loc[(target, model, moved)]
            rows.append({
                "model": model, "applied to": target, "setting from": source,
                "own setting": own, "own f1": own_row["f1"],
                "transferred setting": moved, "transferred f1": moved_row["f1"],
                "f1 change": moved_row["f1"] - own_row["f1"],
                "transferred precision": moved_row["precision"], "transferred recall": moved_row["recall"],
                "transferred false_alarm_rate": moved_row["false_alarm_rate"],
            })
    return pd.DataFrame(rows)
