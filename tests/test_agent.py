import pytest
from src.agent_loop import AutonomousDataAgent
from src.agent import ChangeType, RiskLevel


def test_agent_end_to_end_drop_column():
    schema = {
        "raw_orders": {"order_id": "int", "amount": "float", "discount": "float"},
        "stg_orders": {"order_id": "int", "net_price": "float"},
        "raw_users": {"id": "int", "email": "string"}
    }
    queries = [
        {
            "target_table": "stg_orders",
            "sql": "SELECT order_id, amount * (1 - discount) AS net_price FROM raw_orders"
        }
    ]
    agent = AutonomousDataAgent(schema=schema, queries=queries)

    result = agent.execute_change_request(
        user_request="Remove the email field from raw_users for privacy compliance.",
        schema_yaml_str="raw_users:\n  id: int\n  email: string"
    )

    assert result.proposal.target_table == "raw_users"
    assert result.proposal.target_column == "email"
    assert result.proposal.change_type == ChangeType.DROP
    assert result.derivation_blast == []
    assert result.verification_passed is True
    assert result.impact_report.risk_level == RiskLevel.LOW
    assert result.impact_report.recommended_action == "PROCEED"


def test_agent_end_to_end_breaking_rename():
    schema = {
        "raw_orders": {"order_id": "int", "amount": "float", "discount": "float"},
        "stg_orders": {"order_id": "int", "net_price": "float"}
    }
    queries = [
        {
            "target_table": "stg_orders",
            "sql": "SELECT order_id, amount * (1 - discount) AS net_price FROM raw_orders"
        }
    ]
    agent = AutonomousDataAgent(schema=schema, queries=queries)

    result = agent.execute_change_request(
        user_request="Rename discount to discount_pct in raw_orders.",
        schema_yaml_str="raw_orders:\n  order_id: int\n  discount: float"
    )

    assert result.proposal.target_table == "raw_orders"
    assert result.proposal.target_column == "discount"
    assert result.proposal.change_type == ChangeType.RENAME
    assert "table:stg_orders.net_price" in result.derivation_blast
    assert result.verification_passed is False
    assert result.impact_report.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
    assert result.impact_report.recommended_action == "ABORT"


def test_agent_end_to_end_uncertainty_handling():
    schema = {
        "employees": {"emp_id": "int", "manager_id": "int"}
    }
    queries = [
        {
            "target_table": "final_org",
            "sql": """
            WITH RECURSIVE org_chart AS (
              SELECT emp_id, manager_id, 1 AS depth FROM employees WHERE manager_id IS NULL
              UNION ALL
              SELECT e.emp_id, e.manager_id, o.depth + 1 FROM employees e JOIN org_chart o ON e.manager_id = o.emp_id
            )
            SELECT emp_id, depth FROM org_chart
            """
        }
    ]
    agent = AutonomousDataAgent(schema=schema, queries=queries, sniffer_mode="extended")

    result = agent.execute_change_request(
        user_request="Rename manager_id in employees to supervisor_id.",
        schema_yaml_str="employees:\n  emp_id: int\n  manager_id: int"
    )

    assert result.proposal.target_table == "employees"
    assert result.proposal.target_column == "manager_id"
    assert result.verification_uncertain is True
    assert result.impact_report.recommended_action == "MANUAL_AUDIT_REQUIRED"
    assert result.impact_report.risk_level == RiskLevel.HIGH

