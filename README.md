# Ripple: SQL Column-Level Lineage & Autonomous Agent Loop

Ripple is a column-level SQL lineage engine and autonomous agent verification platform designed to evaluate and prevent breaking data-model changes across multi-table analytical pipelines.

## 🎯 Research Questions
1. **Core Lineage**: How accurately can column-level lineage predict the true downstream blast radius of a data-model change compared to coarse table-level baselines?
2. **Autonomous Agent Trust**: When an autonomous agent proposes a data-model change, how often does its self-reported impact assessment match the true blast radius — and does its reliability degrade when the underlying lineage engine fails on complex SQL constructs?

---

## 📊 Empirical Findings

### 1. Lineage Engine Benchmark (Generalization Set: 8 Pipelines)
Evaluated across easy, medium, and hard multi-table analytical pipelines:

| Metric | Column-Level Lineage (Ripple) | Table-Level Baseline | Impact / Difference |
| :--- | :--- | :--- | :--- |
| **Macro-Avg Precision** | **100.0%** | 42.9% | **+57.1% precision** (eliminates false alarms) |
| **Macro-Avg Recall** | **100.0%** | 100.0% | Both identify 100% of true breaking changes |
| **Macro-Avg F1 Score** | **1.000** | 0.596 | **+67.8% F1 improvement** |
| **Blast-Radius Inflation** | **1.00x** | **2.42x** | Table baseline over-flags damage by 242% |

### 2. Autonomous Agent Reliability Benchmark (8 Change Requests)
Evaluated across both standard and adversarial SQL pipelines to measure agent trust:

| Metric | Standard SQL | Adversarial SQL | Overall |
| :--- | :--- | :--- | :--- |
| **Blast Radius Match Rate** | **100.0%** | 25.0% | **62.5%** |
| **False Confidence Failure Rate** | **0.0%** | **50.0%** | **25.0%** |

### Key Discovery: The Silent Lineage Failure Trap
When underlying lineage fails silently on complex constructs (e.g., recursive CTEs or set operations), downstream deterministic checks receive an empty blast radius. As a result, the autonomous agent falsely reports `LOW RISK` and issues a `PROCEED` recommendation on breaking schema migrations. This reveals that agent guardrails must actively flag dialect unparseability rather than assuming empty blast radius equals safety.

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
│  Ripple Lineage Engine  │  ──> Column-Level & Relational Graphs
└──────────┬──────────────┘
           │ Blast Radiuses
           ▼
┌─────────────────────────┐
│  Deterministic Verifier │  <── Rule-based checks (Type cast, Drop, Rename)
└──────────┬──────────────┘
           │ Verification Results
           ▼
┌─────────────────────────┐
│   Impact Report Agent   │  ──> Audited ImpactReport (Risk & Recommendation)
└─────────────────────────┘
```

1. **Structured Change Proposal (`src/agent.py`)**:
   - Converts natural language requests into typed `ChangeProposal` objects with schema catalog grounding.
   - Enforces structured JSON output (`response_schema`).

2. **Deterministic Verification Layer (`src/verifier.py`)**:
   - Hardcoded rule checks independent of LLM reasoning:
     - `DESTRUCTIVE_DROP_CHECK`: Blocks dropping columns with downstream dependencies.
     - `RENAME_PROPAGATION_CHECK`: Identifies unmigrated downstream references.
     - `TYPE_COMPATIBILITY_CHECK`: Prevents invalid numeric-to-string conversions impacting downstream arithmetic.
     - `RELATIONAL_CONTROL_SHIFT`: Surfaces predicate, join, and group-by shifts.

3. **Autonomous Agent Loop (`src/agent_loop.py`)**:
   - Orchestrates LLM proposal generation, Ripple lineage computation, deterministic verification, and impact reporting.

---

## 📁 Repository Structure

```text
ripple/
├── src/
│   ├── __init__.py
│   ├── agent.py               # Propose-change and impact-report generation
│   ├── agent_loop.py          # End-to-end autonomous agent loop orchestrator
│   ├── lineage_engine.py      # Column-level derivation & relational-influence engine
│   ├── table_baseline.py      # Coarse table-level lineage baseline
│   ├── verifier.py            # Deterministic rule-based verification engine
│   └── metrics.py             # Precision, Recall, F1, Inflation calculator
├── tests/
│   ├── __init__.py
│   ├── test_agent.py          # End-to-end agent loop tests
│   ├── test_lineage_engine.py # Unit tests for lineage engine
│   ├── test_metrics.py        # Unit tests for scoring logic
│   ├── test_table_baseline.py # Unit tests for table baseline
│   └── test_verifier.py       # Unit tests for deterministic checks
├── data/
│   ├── schema.yaml            # Data warehouse catalog definitions
│   ├── dev_queries.yaml       # 10 development benchmark queries
│   ├── test_queries.yaml      # 8 held-out test benchmark queries
│   ├── adversarial_queries.yaml # 4 adversarial stress test queries
│   └── agent_eval_cases.yaml  # 8 autonomous agent evaluation scenarios
├── evaluate.py                # Lineage engine benchmark runner
├── evaluate_agent.py          # Autonomous agent reliability benchmark runner
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

### 2. Run Test Suite (15 Passing Tests)
```bash
pytest
```

### 3. Run Benchmarks
```bash
# Run core lineage engine benchmarks
python evaluate.py --dataset data/test_queries.yaml
python evaluate.py --dataset data/adversarial_queries.yaml

# Run autonomous agent reliability benchmark
python evaluate_agent.py
```
