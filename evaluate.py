import argparse
import copy
from typing import Any
import yaml

from src.lineage_engine import LineageEngine
from src.table_baseline import TableBaseline
from src.metrics import calculate_metrics


def load_yaml(file_path: str) -> Any:
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_benchmark(dataset_path: str, schema_path: str = "data/schema.yaml"):
    schema = load_yaml(schema_path)
    test_cases = load_yaml(dataset_path)

    col_results = []
    tbl_results = []

    print(f"\n{'='*85}")
    print(f"BENCHMARK RUN: {dataset_path} ({len(test_cases)} Test Cases)")
    print(f"{'='*85}")
    print(
        f"{'Query ID':<35} | {'Diff':<6} | {'Col F1':<8} {'Col Infl':<8} | {'Tbl F1':<8} {'Tbl Infl':<8}"
    )
    print(f"{'-'*35}-+-{'-'*6}-+-{'-'*8}-{'-'*8}-+-{'-'*8}-{'-'*8}")

    for tc in test_cases:
        tc_id = tc["id"]
        difficulty = tc["difficulty"]
        expected = set(tc["expected_blast_radius"])
        target_change = tc["target_change"]

        col_engine = LineageEngine(schema=copy.deepcopy(schema))
        for q in tc["queries"]:
            col_engine.add_query(q["sql"], q["target_table"])
        col_pred = col_engine.get_blast_radius(target_change)
        col_m = calculate_metrics(col_pred, expected)
        col_results.append((difficulty, col_m))

        tbl_engine = TableBaseline(schema=copy.deepcopy(schema))
        for q in tc["queries"]:
            tbl_engine.add_query(q["sql"], q["target_table"])
        tbl_pred = tbl_engine.get_blast_radius(target_change)
        tbl_m = calculate_metrics(tbl_pred, expected)
        tbl_results.append((difficulty, tbl_m))

        print(
            f"{tc_id:<35} | {difficulty:<6} | {col_m['f1']:<8.2f} {col_m['inflation']:<7.2f}x | {tbl_m['f1']:<8.2f} {tbl_m['inflation']:<7.2f}x"
        )

    def summarize(results):
        n = len(results)
        return {
            "precision": sum(r[1]["precision"] for r in results) / n,
            "recall": sum(r[1]["recall"] for r in results) / n,
            "f1": sum(r[1]["f1"] for r in results) / n,
            "inflation": sum(r[1]["inflation"] for r in results) / n,
        }

    col_summary = summarize(col_results)
    tbl_summary = summarize(tbl_results)

    print(f"{'='*85}")
    print("AGGREGATE BENCHMARK RESULTS")
    print(f"{'='*85}")
    print(f"{'Metric':<25} | {'Column-Level Lineage':<22} | {'Table-Level Baseline':<22}")
    print(f"{'-'*25}-+-{'-'*22}-+-{'-'*22}")
    print(
        f"{'Macro-Avg Precision':<25} | {col_summary['precision']*100:<21.1f}% | {tbl_summary['precision']*100:<21.1f}%"
    )
    print(
        f"{'Macro-Avg Recall':<25} | {col_summary['recall']*100:<21.1f}% | {tbl_summary['recall']*100:<21.1f}%"
    )
    print(
        f"{'Macro-Avg F1 Score':<25} | {col_summary['f1']:<22.3f} | {tbl_summary['f1']:<22.3f}"
    )
    print(
        f"{'Blast-Radius Inflation':<25} | {col_summary['inflation']:<21.2f}x | {tbl_summary['inflation']:<21.2f}x"
    )
    print(f"{'='*85}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/dev_queries.yaml")
    args = parser.parse_args()
    run_benchmark(args.dataset)