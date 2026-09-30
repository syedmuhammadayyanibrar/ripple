from typing import Set, Dict


def calculate_metrics(predicted: Set[str], expected: Set[str]) -> Dict[str, float]:
    tp = len(predicted & expected)
    fp = len(predicted - expected)
    fn = len(expected - predicted)

    if tp + fp == 0:
        precision = 1.0 if len(expected) == 0 else 0.0
    else:
        precision = tp / (tp + fp)

    if tp + fn == 0:
        recall = 1.0 if len(expected) == 0 else 0.0
    else:
        recall = tp / (tp + fn)

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * (precision * recall) / (precision + recall)

    if len(expected) == 0:
        inflation = 1.0 if len(predicted) == 0 else float("inf")
    else:
        inflation = len(predicted) / len(expected)

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "inflation": round(inflation, 4),
    }