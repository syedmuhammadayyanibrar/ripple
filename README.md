# Ripple: SQL Column-Level Lineage & Autonomous Agent Loop

Ripple is a column-level SQL lineage engine and autonomous agent verification platform designed to evaluate and prevent breaking data-model changes across multi-table analytical pipelines.

---

## 🎯 Research Questions

1. **Core Lineage Precision vs Table-Level Baseline**: How accurately can column-level lineage predict the true downstream blast radius of a schema change compared to coarse table-level baselines across standard and adversarial SQL pipelines?
2. **Autonomous Agent Trust & Failure Modes**: When an autonomous data engineering agent proposes a migration, how often does its self-reported impact assessment match the true blast radius — and does that reliability degrade when the underlying lineage engine fails on complex SQL constructs?
3. **The Generalization Boundary of Uncertainty Detection**: Can rule-based syntactic construct sniffing eliminate false-confidence outages across unseen unresolvable SQL constructs, or is it fundamentally bounded as an enumerative heuristic?

---

## 📊 Empirical Findings

### 1. Core Lineage Benchmark: Standard Pipelines (8 Generalization Test Cases)

Evaluated across easy, medium, and hard multi-table analytical pipelines:

| Metric | Column-Level Lineage (Ripple) | Table-Level Baseline | Impact / Difference |
| :--- | :--- | :--- | :--- |
| **Macro-Avg Precision** | **100.0%** | 42.9% | **+57.1% precision** (eliminates false alarms) |
| **Macro-Avg Recall** | **100.0%** | 100.0% | Both identify 100% of true breaking changes |
| **Macro-Avg F1 Score** | **1.000** | 0.596 | **+67.8% F1 improvement** |
| **Blast-Radius Inflation** | **1.00x** | **2.42x** | Table baseline over-flags damage by 242% |

On standard SQL (CTEs, joins, aggregations, wildcards), column-level lineage pinpoints the exact downstream impact without flagging unrelated columns in downstream tables.

---

### 2. Core Lineage Benchmark: Adversarial Pipelines (7 Hard Test Cases)

When tested against complex SQL constructs designed to stress AST traversal:

| Metric | Column-Level Lineage (Ripple) | Table-Level Baseline | Analysis |
| :--- | :--- | :--- | :--- |
| **Macro-Avg Precision** | 21.4% | **50.0%** | Column lineage drops edges on complex AST subqueries |
| **Macro-Avg Recall** | 28.6% (2/7 resolved) | **100.0%** (7/7 identified) | Table baseline catches downstream tables, column engine misses |
| **Macro-Avg F1 Score** | 0.238 | **0.667** | Table baseline is more robust under AST failures |
| **Blast-Radius Inflation** | 0.71x (under-predicts) | 2.00x (over-predicts) | **Lineage suffers hazardous silent under-prediction** |

#### Construct-by-Construct Breakdown
1. **Window Functions (`OVER (PARTITION BY ... ORDER BY ...)`)**: Fully resolved (F1: 1.00, Inflation: 1.00x).
2. **Set Operations (`UNION ALL`)**: Lineage maps column to both branch projections (F1: 0.00, Noisy Over-prediction).
3. **Correlated Subqueries**: Scalar subquery traces to synthetic projection AST (F1: 0.00, Noisy Over-prediction).
4. **Conditional Subqueries (`CASE WHEN (SELECT ...)`)**: Traces to projection alias + synthetic node (F1: 0.67, Noisy Over-prediction).
5. **Recursive CTEs (`WITH RECURSIVE`)**: **Silent Drop** — returns 0 columns (F1: 0.00, Under-prediction).
6. **Lateral Subqueries (`CROSS JOIN LATERAL (...)`)**: **Silent Drop** — returns 0 columns (F1: 0.00, Under-prediction).
7. **Exists Predicates (`EXISTS(SELECT ...)`)**: **Silent Drop** — returns 0 columns (F1: 0.00, Under-prediction).

---

### 3. Autonomous Agent Trust Benchmark (16 Scenarios: 8 Standard, 8 Adversarial)

To test how an autonomous agent (e.g. Alkera AI pattern) behaves when its lineage engine fails, we evaluated 16 real change requests across three verifier architectures:

| Verifier Architecture | False Confidence (Hazardous) | Uncertain Audits Flagged | Adversarial Safe Decisions | Standard SQL Reliability |
| :--- | :--- | :--- | :--- | :--- |
| **Binary Verifier (Baseline)** | **3 of 16 (18.8%)** | 0 of 16 (0.0%) | 5 of 8 (62.5%) | **8 of 8 (100.0%)** |
| **Targeted Ternary (Seen Only)** | **2 of 16 (12.5%)** | 1 of 16 (6.2%) | 6 of 8 (75.0%) | **8 of 8 (100.0%)** |
| **Extended Ternary (Seen + Unseen)** | **0 of 16 (0.0%)** | 3 of 16 (18.8%) | **8 of 8 (100.0%)** | **8 of 8 (100.0%)** |

> [!IMPORTANT]
> **Reporting Precision on Small Samples**: In an evaluation suite of 16 cases, every single failure represents a 6.25% shift. We report exact fractions ($N/\text{total}$) alongside percentages to avoid the illusion of statistical precision.

---

### 4. Key Discovery: The "Silent Lineage Failure Trap" & Failure Taxonomy

Our empirical benchmark reveals a non-obvious, critical vulnerability in lineage-driven autonomous agents:

#### The Vulnerability
When an AST lineage parser encounters an unresolvable SQL construct (such as a recursive CTE or lateral join), it does **not** throw an exception. Instead, it silently returns an empty set of downstream columns (`set()`). 
A standard binary verifier assumes:
$$\text{len}(\text{blast\_radius}) = 0 \implies \text{Safe to Proceed}$$
This creates a **catastrophic false-confidence outage**: the agent reports `LOW RISK` and issues a `PROCEED` recommendation on a change that will actually break production downstream.

#### Two Distinct Failure Modes in Adversarial SQL
It is critical to distinguish between two fundamentally different failure modes:
1. **Silent Under-prediction (Hazardous False Confidence)**: The engine returns 0 columns when downstream breakage exists (`agent_06` recursive CTE, `agent_13` lateral subquery, `agent_15` exists predicate). The agent falsely greenlights a breaking change.
2. **Noisy Over-prediction (Cautious False Alarm)**: The engine returns more columns than the true blast radius due to synthetic AST nodes (`agent_05` union, `agent_07` correlated subquery, `agent_14` case subquery, `agent_16` pivot). Here the agent flags `CRITICAL RISK` and halts execution (`ABORT`). While imprecise, this failure is **safe** from silent production outages.

#### The Generalization Boundary (Seen vs. Unseen Constructs)
- When we first implemented the ternary state detector, it targeted the constructs we had observed failing: `exp.Union` and recursive CTEs. On our initial 8-case suite, it achieved 0/8 false confidence.
- However, when evaluated on **unseen unresolvable constructs** (`LATERAL` joins and `EXISTS` subqueries), the targeted detector failed to flag uncertainty on **2 of 8 adversarial cases** (`agent_13` and `agent_15`), allowing silent false confidence to return.
- **Architectural Conclusion**: Syntactic construct sniffing is an enumerative heuristic (whack-a-mole). While extending the sniffer to cover lateral subqueries and exists predicates caught those specific cases (reducing false confidence to 0/16 in our benchmark), a production autonomous agent cannot rely solely on syntax blacklists. True reliability requires **structural graph-completeness audits**: if a source table appears in a query's AST, but 0 columns are traced downstream, the verifier must surface an uncertainty flag before deployment.

---

## 🏗️ Architecture & Core Components

Ripple operates as an end-to-end agentic platform:

```
 Natural Language Request
           │
           ▼
┌─────────────────────────┐
│   Propose-Change Agent  │  <── Schema Catalog Grounding
└──────────┬──────────────┘
           │ Structured ChangeProposal
           ▼
┌─────────────────────────┐
│  Ripple Lineage Engine  │  ──> Derivation Graph (G_val) & Relational Graph (G_rel)
└──────────┬──────────────┘  ──> AST Construct Sniffer (Unresolvable Flags)
           │ Column & Relational Blast Radiuses
           ▼
┌─────────────────────────┐
│  Deterministic Verifier │  <── Ternary Logic (SAFE, BREAKING, UNCERTAIN)
└──────────┬──────────────┘
           │ Audited Verdict & Issues
           ▼
┌─────────────────────────┐
│   Impact Report Agent   │  ──> Audited ImpactReport (Risk & Recommendation)
└─────────────────────────┘
```

1. **Structured Change Proposal (`src/agent.py`)**:
   - Converts natural-language requests into typed Pydantic `ChangeProposal` models grounded in the schema catalog.
2. **Dual-Graph Lineage Engine (`src/lineage_engine.py`)**:
   - Derivation Graph ($G_{val}$): Tracks direct column value transformations.
   - Relational Influence Graph ($G_{rel}$): Tracks row filtering, predicates, join conditions, and grouping shifts.
   - Sniffer Subsystem: Analyzes AST expressions for known resolution limits (`sniffer_mode`: `none`, `targeted`, `extended`).
3. **Deterministic Verification Layer (`src/verifier.py`)**:
   - Implements rule-based ternary checks independent of LLM hallucination:
     - `SAFE`: Zero blast radius and verified resolvable AST $\to$ `PROCEED`.
     - `BREAKING`: Non-zero downstream dependencies $\to$ `ABORT`.
     - `UNCERTAIN`: Zero blast radius with unresolvable AST construct $\to$ `MANUAL_AUDIT_REQUIRED`.
     - `RELATIONAL_WARNING`: Preserves predicate and join control flow shifts.
4. **Autonomous Agent Loop (`src/agent_loop.py`)**:
   - Coordinates proposal generation, lineage computation, deterministic checks, and structured report synthesis.

---

## 📁 Repository Structure

```text
ripple/
├── src/
│   ├── __init__.py
│   ├── agent.py               # Pydantic models, LLM call, and structured proposal parsing
│   ├── agent_loop.py          # Autonomous agent orchestrator
│   ├── lineage_engine.py      # Dual-graph column & relational lineage engine
│   ├── table_baseline.py      # Coarse table-level baseline comparison engine
│   ├── verifier.py            # Deterministic rule-based ternary verifier
│   └── metrics.py             # Precision, Recall, F1, and Inflation metrics
├── tests/
│   ├── __init__.py
│   ├── test_agent.py          # End-to-end agent loop & uncertainty handling tests
│   ├── test_lineage_engine.py # Unit tests for lineage traversal & sniffer modes
│   ├── test_metrics.py        # Unit tests for scoring logic
│   ├── test_table_baseline.py # Unit tests for table baseline
│   └── test_verifier.py       # Unit tests for ternary verification checks
├── data/
│   ├── schema.yaml            # E-commerce warehouse catalog schema
│   ├── dev_queries.yaml       # 10 development benchmark queries
│   ├── test_queries.yaml      # 8 held-out test benchmark queries
│   ├── adversarial_queries.yaml # 7 hard adversarial stress test queries
│   └── agent_eval_cases.yaml  # 16 autonomous agent evaluation scenarios
├── evaluate.py                # Lineage engine benchmark runner
├── evaluate_agent.py          # Agent reliability & generalization ablation runner
├── requirements.txt           # Project dependencies
└── README.md
```

---

## 🚀 Quickstart & Verification

### 1. Installation
```bash
git clone https://github.com/syedmuhammadayyanibrar/ripple.git
cd ripple

python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run Test Suite (18 Passing Tests)
```bash
pytest
```

### 3. Run Core Lineage Benchmarks
```bash
# Standard held-out test queries (8 queries)
python evaluate.py --dataset data/test_queries.yaml

# Adversarial SQL queries (7 queries)
python evaluate.py --dataset data/adversarial_queries.yaml
```

### 4. Run Agent Reliability & Generalization Ablation Benchmark
```bash
# Evaluates all 16 scenarios across Binary, Targeted Ternary, and Extended Ternary modes
python evaluate_agent.py
```
