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
