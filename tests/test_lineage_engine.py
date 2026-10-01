import pytest
from src.lineage_engine import LineageEngine


def test_single_query_simple_derivation():
    engine = LineageEngine()
    sql = "SELECT a + 1 AS b FROM my_table"
    target_table = "analytics_table"
    engine.add_query(sql, target_table=target_table)
    blast_radius = engine.get_blast_radius("table:my_table.a")
    assert "table:analytics_table.b" in blast_radius


def test_multi_query_pipeline_with_cte():
    engine = LineageEngine()
    q1 = """
    WITH base AS (
        SELECT id, price * (1 - discount) AS net_price 
        FROM raw_orders
    ) 
    SELECT id, net_price FROM base
    """
    engine.add_query(q1, target_table="stg_orders")

    q2 = """
    SELECT id, net_price * 1.05 AS final_price 
    FROM stg_orders
    """
    engine.add_query(q2, target_table="fct_orders")

    blast = engine.get_blast_radius("table:raw_orders.discount")
    assert "table:stg_orders.net_price" in blast
    assert "table:fct_orders.final_price" in blast


def test_wildcard_expansion_with_schema():
    schema = {
        "raw_orders": {
            "id": "int",
            "amount": "float",
        }
    }
    engine = LineageEngine(schema=schema)
    sql = "SELECT * FROM raw_orders"
    engine.add_query(sql, target_table="stg_orders")
    blast = engine.get_blast_radius("table:raw_orders.amount")
    assert "table:stg_orders.amount" in blast


def test_join_unqualified_columns_with_schema():
    schema = {
        "orders": {"order_id": "int", "cust_id": "int"},
        "customers": {"id": "int", "customer_name": "varchar"},
    }
    engine = LineageEngine(schema=schema)
    sql = """
    SELECT 
        order_id, 
        customer_name 
    FROM orders 
    JOIN customers ON orders.cust_id = customers.id
    """
    engine.add_query(sql, target_table="orders_enriched")
    blast = engine.get_blast_radius("table:customers.customer_name")
    assert "table:orders_enriched.customer_name" in blast


def test_relational_influence_vs_derivation():
    schema = {
        "orders": {"order_id": "int", "price": "float", "is_refunded": "boolean"},
        "users": {"id": "int", "name": "varchar"}
    }
    engine = LineageEngine(schema=schema)
    
    sql = """
    SELECT 
        o.order_id,
        o.price * 1.1 AS price_with_tax
    FROM orders AS o
    JOIN users AS u ON o.order_id = u.id
    WHERE o.is_refunded = false
    """
    engine.add_query(sql, target_table="clean_orders")

    deriv_blast = engine.get_derivation_blast_radius("table:orders.is_refunded")
    assert deriv_blast == set()

    rel_blast = engine.get_relational_blast_radius("table:orders.is_refunded")
    assert "relation:clean_orders" in rel_blast


def test_unresolved_construct_detection_modes():
    sql_lateral = "SELECT u.id, l.score FROM users u, LATERAL (SELECT score FROM scores s WHERE s.uid = u.id) l"
    
    eng_none = LineageEngine(sniffer_mode="none")
    eng_none.add_query(sql_lateral, "summary")
    assert eng_none.unresolved_constructs == {}

    eng_targeted = LineageEngine(sniffer_mode="targeted")
    eng_targeted.add_query(sql_lateral, "summary")
    assert eng_targeted.unresolved_constructs == {}

    eng_extended = LineageEngine(sniffer_mode="extended")
    eng_extended.add_query(sql_lateral, "summary")
    assert "summary" in eng_extended.unresolved_constructs
    assert "LATERAL_SUBQUERY" in eng_extended.unresolved_constructs["summary"]