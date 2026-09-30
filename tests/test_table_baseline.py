import pytest
from src.table_baseline import TableBaseline


def test_table_baseline_coarse_granularity():
    schema = {
        "raw_orders": {"id": "int", "price": "float", "discount": "float"},
        "stg_orders": {"id": "int", "net_price": "float", "notes": "string"},
        "fct_orders": {"id": "int", "final_price": "float"}
    }
    baseline = TableBaseline(schema=schema)

    baseline.add_query(
        "SELECT id, price * (1 - discount) AS net_price, 'ok' AS notes FROM raw_orders", 
        target_table="stg_orders"
    )

    baseline.add_query(
        "SELECT id, net_price * 1.05 AS final_price FROM stg_orders", 
        target_table="fct_orders"
    )

    blast = baseline.get_blast_radius("table:raw_orders.discount")

    assert "table:stg_orders.id" in blast
    assert "table:stg_orders.net_price" in blast
    assert "table:stg_orders.notes" in blast
    assert "table:fct_orders.id" in blast
    assert "table:fct_orders.final_price" in blast
    assert len(blast) == 5