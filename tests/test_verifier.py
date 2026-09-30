import pytest
from src.agent import ChangeProposal, ChangeType
from src.verifier import DeterministicVerifier


def test_destructive_drop_blocked():
    verifier = DeterministicVerifier()
    proposal = ChangeProposal(
        target_table="raw_orders",
        target_column="discount",
        change_type=ChangeType.DROP,
        old_value="float",
        new_value=None,
        sql_statement="ALTER TABLE raw_orders DROP COLUMN discount;",
        intent_summary="Remove discount column."
    )
    derivation_blast = {"table:stg_orders.net_price", "table:fct_orders.final_price"}
    relational_blast = set()
    table_blast = {"table:stg_orders.id", "table:stg_orders.net_price"}

    result = verifier.verify(proposal, derivation_blast, relational_blast, table_blast)

    assert result.passed is False
    assert len(result.issues) == 1
    assert "Destructive DROP blocked" in result.issues[0]


def test_safe_drop_passes():
    verifier = DeterministicVerifier()
    proposal = ChangeProposal(
        target_table="raw_users",
        target_column="email",
        change_type=ChangeType.DROP,
        old_value="string",
        new_value=None,
        sql_statement="ALTER TABLE raw_users DROP COLUMN email;",
        intent_summary="Remove email column."
    )
    derivation_blast = set()
    relational_blast = set()
    table_blast = set()

    result = verifier.verify(proposal, derivation_blast, relational_blast, table_blast)

    assert result.passed is True
    assert len(result.issues) == 0
    assert result.details.get("drop_safe") is True


def test_breaking_rename():
    verifier = DeterministicVerifier()
    proposal = ChangeProposal(
        target_table="raw_orders",
        target_column="discount",
        change_type=ChangeType.RENAME,
        old_value="discount",
        new_value="discount_pct",
        sql_statement="ALTER TABLE raw_orders RENAME COLUMN discount TO discount_pct;",
        intent_summary="Rename column."
    )
    derivation_blast = {"table:stg_orders.net_price"}
    relational_blast = set()
    table_blast = {"table:stg_orders.net_price"}

    result = verifier.verify(proposal, derivation_blast, relational_blast, table_blast)

    assert result.passed is False
    assert "Breaking RENAME detected" in result.issues[0]


def test_incompatible_type_alteration():
    verifier = DeterministicVerifier()
    proposal = ChangeProposal(
        target_table="raw_orders",
        target_column="amount",
        change_type=ChangeType.ALTER_TYPE,
        old_value="float",
        new_value="varchar",
        sql_statement="ALTER TABLE raw_orders ALTER COLUMN amount TYPE VARCHAR;",
        intent_summary="Change type."
    )
    derivation_blast = {"table:fct_revenue.total_revenue"}
    relational_blast = set()
    table_blast = {"table:fct_revenue.total_revenue"}

    result = verifier.verify(proposal, derivation_blast, relational_blast, table_blast)

    assert result.passed is False
    assert "Incompatible Type Cast" in result.issues[0]


def test_relational_control_shift_warning():
    verifier = DeterministicVerifier()
    proposal = ChangeProposal(
        target_table="raw_orders",
        target_column="status",
        change_type=ChangeType.MODIFY_LOGIC,
        old_value="string",
        new_value="string",
        sql_statement="UPDATE raw_orders SET status = lower(status);",
        intent_summary="Normalize status."
    )
    derivation_blast = set()
    relational_blast = {"relation:clean_orders"}
    table_blast = set()

    result = verifier.verify(proposal, derivation_blast, relational_blast, table_blast)

    assert result.passed is True
    assert len(result.warnings) == 1
    assert "Relational Control Shift" in result.warnings[0]
