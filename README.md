# Ripple: SQL Column-Level Lineage & Blast-Radius Engine

Ripple is a column-level SQL lineage and blast-radius analysis engine designed to quantify the downstream impact of data-model changes across multi-table analytical pipelines.

## 🎯 Research Question
> **How accurately can column-level lineage predict the true downstream blast radius of a data-model change, and how does it compare with table-level lineage?**

---

## 📊 Empirical Findings

### 1. Held-Out Generalization Benchmark (8 Pipelines)
Evaluated against unseen multi-table pipelines across easy, medium, and hard tiers:

| Metric | Column-Level Lineage (Ripple) | Table-Level Baseline | Impact / Difference |
| :--- | :--- | :--- | :--- |
| **Macro-Avg Precision** | **100.0%** | 42.9% | **+57.1% precision** (eliminates false alarms) |
| **Macro-Avg Recall** | **100.0%** | 100.0% | Both identify 100% of true breaking changes |
| **Macro-Avg F1 Score** | **1.000** | 0.596 | **+67.8% F1 improvement** |
| **Blast-Radius Inflation** | **1.00x** | **2.42x** | Table baseline over-flags damage by 242% |

### 2. Adversarial Stress Benchmark (4 Edge Cases)
Genuinely adversarial constructs designed to stress-test AST lineage limitations:

| Query ID | Construct | Column F1 | Table F1 | Failure Mode |
| :--- | :--- | :--- | :--- | :--- |
| `adv_01` | `UNION ALL` Set Operation | 0.00 | 0.67 | Synthetic AST token projection on `exp.Union` |
| `adv_02` | Correlated Scalar Subquery | 0.00 | 0.67 | Correlation filter key dropped from derivation |
| `adv_03` | Window Function (`ROW_NUMBER`) | 1.00 | 0.67 | Passed (expression tree captures partition keys) |
| `adv_04` | Recursive Self-Referencing CTE | 0.00 | 0.67 | Recursive union branch pruned to avoid cycles |

---

## 🔬 Adversarial Failure Analysis & Production Fixes

1. **Set Operations (`UNION / UNION ALL`)**:
   - *Failure:* Calling `.selects` on an `exp.Union` root AST node returns synthetic branch tokens (`UNION`, `1`) rather than the projected column aliases.
   - *Production Fix:* Detect `exp.Union` nodes, extract projections from `parsed.this.selects`, and trace each union arm independently to the unified destination relation.

2. **Correlated Scalar Subqueries**:
   - *Failure:* Inner `WHERE` correlation predicates (`WHERE o2.user_id = o1.user_id`) are classified as row filters rather than value derivations, dropping outer key dependencies.
   - *Production Fix:* Apply AST query decorrelation (rewriting scalar subqueries into equivalent `LEFT JOIN` + `GROUP BY` CTEs) prior to lineage extraction.

3. **Recursive CTEs**:
   - *Failure:* Lineage extraction parses only the base non-recursive anchor member and prunes the recursive self-referential arm to avoid traversal cycles.
   - *Production Fix:* Implement a cycle-guarded fixed-point unrolling algorithm to traverse the recursive step up to depth $N$.

---

## 🏗️ Architecture & Core Components

Ripple separates query dependencies into two orthogonal graphs:

1. **Derivation Lineage Graph ($G_{val}$)**:
   - Tracks data flow: which source column values are transformed and poured into destination column values (`SELECT a + 1 AS b`).
   - Uses `sqlglot` AST parsing, resolves table aliases (`FROM users AS u -> raw_users`), and isolates CTE namespaces (`cte:target.base.col`) to prevent cross-query collisions.
   - Leverages schema catalog qualification to expand wildcards (`SELECT *`).

2. **Relational-Influence Graph ($G_{rel}$)**:
   - Tracks control flow: which columns govern row survivability, join cardinality, or aggregation bucketing (`WHERE`, `JOIN ... ON`, `GROUP BY`, `HAVING`).
   - Isolates predicate dependencies from column calculation values, preventing artificial blast-radius inflation while ensuring pipeline governance.

3. **Evaluation Harness (`src/metrics.py`, `evaluate.py`)**:
   - Computes Precision, Recall, F1, and Blast-Radius Inflation across human-verified ground-truth pipelines.
   - Compares Ripple directly against a table-level baseline (`src/table_baseline.py`).

---

## 📁 Repository Structure

```text
ripple/
├── src/
│   ├── __init__.py
│   ├── lineage_engine.py      # Column-level derivation & relational-influence engine
│   ├── table_baseline.py      # Coarse table-level lineage baseline
│   └── metrics.py             # Precision, Recall, F1, Inflation calculator
├── tests/
│   ├── __init__.py
│   ├── test_lineage_engine.py # Unit tests for derivation, CTEs, wildcards, joins, relational influence
│   ├── test_metrics.py        # Unit tests for scoring logic
│   └── test_table_baseline.py # Unit tests for table baseline
├── data/
│   ├── schema.yaml            # Data warehouse catalog definitions
│   ├── dev_queries.yaml       # 10 development benchmark queries
│   ├── test_queries.yaml      # 8 held-out test benchmark queries
│   └── adversarial_queries.yaml # 4 adversarial stress test queries
├── evaluate.py                # Benchmark runner and reporting CLI
├── requirements.txt           # Project dependencies
└── README.md
```

---

## 🚀 Quickstart

### 1. Installation
```bash
git clone https://github.com/syedmuhammadayyanibrar/ripple.git
cd ripple

python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run Test Suite
```bash
pytest
```

### 3. Run Benchmark Evaluations
```bash
# Run on development dataset
python evaluate.py --dataset data/dev_queries.yaml

# Run on held-out test dataset
python evaluate.py --dataset data/test_queries.yaml

# Run on adversarial stress dataset
python evaluate.py --dataset data/adversarial_queries.yaml
```

---

## 💻 Programmatic Usage

```python
from src.lineage_engine import LineageEngine

schema = {
    "raw_orders": {"order_id": "int", "price": "float", "discount": "float", "status": "string"},
    "stg_orders": {"order_id": "int", "net_price": "float"}
}

engine = LineageEngine(schema=schema)

# 1. Add pipeline queries
engine.add_query(
    sql="SELECT order_id, price * (1 - discount) AS net_price FROM raw_orders WHERE status = 'active'",
    target_table="stg_orders"
)

# 2. Query Derivation Blast Radius (Value changes)
deriv_blast = engine.get_derivation_blast_radius("table:raw_orders.discount")
# -> {'table:stg_orders.net_price'}

# 3. Query Relational Influence Blast Radius (Row membership changes)
rel_blast = engine.get_relational_blast_radius("table:raw_orders.status")
# -> {'relation:stg_orders'}
```
