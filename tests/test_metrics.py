import pytest
from src.metrics import calculate_metrics


def test_perfect_prediction():
    predicted = {"table:orders.price", "table:orders.total"}
    expected = {"table:orders.price", "table:orders.total"}

    m = calculate_metrics(predicted, expected)
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["f1"] == 1.0
    assert m["inflation"] == 1.0


def test_over_flagging_table_baseline_behavior():
    predicted = {
        "table:stg.id", "table:stg.price", 
        "table:fct.id", "table:fct.price"
    }
    expected = {"table:stg.price", "table:fct.price"}

    m = calculate_metrics(predicted, expected)
    assert m["precision"] == 0.5
    assert m["recall"] == 1.0
    assert m["inflation"] == 2.0