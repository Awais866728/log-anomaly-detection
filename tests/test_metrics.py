import pytest

from src.evaluation.metrics import evaluate


def test_hand_checked_example():
    # index:   0  1  2  3  4  5  6  7  8  9
    y_true = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0]
    y_pred = [1, 1, 1, 0, 1, 0, 0, 0, 0, 0]
    # TP = idx 0,1,2 -> 3   FN = idx 3 -> 1   FP = idx 4 -> 1   TN = idx 5-9 -> 5
    result = evaluate(y_true, y_pred)

    assert (result["tp"], result["fp"], result["tn"], result["fn"]) == (3, 1, 5, 1)
    assert result["precision"] == pytest.approx(3 / 4)  # TP / (TP + FP)
    assert result["recall"] == pytest.approx(3 / 4)  # TP / (TP + FN)
    assert result["f1"] == pytest.approx(0.75)  # 2PR / (P + R)
    assert result["false_alarm_rate"] == pytest.approx(1 / 6)  # FP / (FP + TN)


def test_no_predicted_anomalies():
    result = evaluate([1, 0, 0, 1], [0, 0, 0, 0])

    assert (result["tp"], result["fp"], result["tn"], result["fn"]) == (0, 0, 2, 2)
    assert result["precision"] == 0.0
    assert result["recall"] == 0.0
    assert result["f1"] == 0.0
    assert result["false_alarm_rate"] == 0.0


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        evaluate([0, 1], [0])
