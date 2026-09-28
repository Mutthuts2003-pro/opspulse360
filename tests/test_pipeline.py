"""
OpsPulse 360 - Pipeline Test Suite
Tests the Bronze -> Silver -> Gold warehouse, the data-quality checks,
and the KPI engine output. Assumes the pipeline has already been run
(warehouse/build_warehouse.py, analytics/kpi_engine.py) against the
data/opspulse.db produced by data_generator/generate_seed_data.py --
this mirrors how the CI workflow sequences things.

Run:
    pytest tests/test_pipeline.py -v
"""
import os
import sqlite3

import pandas as pd
import pytest

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DATA_DIR, "opspulse.db")


@pytest.fixture(scope="module")
def conn():
    assert os.path.exists(DB_PATH), (
        "opspulse.db not found -- run warehouse/build_warehouse.py first"
    )
    connection = sqlite3.connect(DB_PATH)
    yield connection
    connection.close()


def _table_exists(conn, name):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


# ---------------------------------------------------------------------
# Bronze layer
# ---------------------------------------------------------------------
@pytest.mark.parametrize("table", [
    "bronze_orders", "bronze_customers", "bronze_products",
    "bronze_inventory", "bronze_delivery", "bronze_support", "bronze_marketing",
])
def test_bronze_tables_exist_and_nonempty(conn, table):
    assert _table_exists(conn, table), f"{table} missing"
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    assert n > 0, f"{table} is empty"


# ---------------------------------------------------------------------
# Silver layer: data quality
# ---------------------------------------------------------------------
def test_silver_orders_has_no_null_keys(conn):
    n = conn.execute(
        "SELECT COUNT(*) FROM silver_orders WHERE order_id IS NULL OR customer_id IS NULL"
    ).fetchone()[0]
    assert n == 0


def test_silver_orders_no_duplicate_order_id(conn):
    dupes = conn.execute(
        "SELECT COUNT(*) FROM (SELECT order_id, COUNT(*) c FROM silver_orders GROUP BY order_id HAVING c > 1)"
    ).fetchone()[0]
    assert dupes == 0


def test_silver_orders_referential_integrity_to_customers(conn):
    orphans = conn.execute("""
        SELECT COUNT(*) FROM silver_orders o
        LEFT JOIN silver_customers c ON o.customer_id = c.customer_id
        WHERE c.customer_id IS NULL
    """).fetchone()[0]
    assert orphans == 0


def test_silver_products_positive_price(conn):
    bad = conn.execute("SELECT COUNT(*) FROM silver_products WHERE selling_price <= 0").fetchone()[0]
    assert bad == 0


def test_dq_report_was_generated(conn):
    assert _table_exists(conn, "dq_report")
    n = conn.execute("SELECT COUNT(*) FROM dq_report").fetchone()[0]
    assert n > 0


# ---------------------------------------------------------------------
# Gold layer: star schema
# ---------------------------------------------------------------------
@pytest.mark.parametrize("table", [
    "dim_customer", "dim_product", "dim_warehouse", "dim_date",
    "fact_orders", "fact_inventory", "fact_delivery", "fact_marketing",
])
def test_gold_tables_exist_and_nonempty(conn, table):
    assert _table_exists(conn, table), f"{table} missing"
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    assert n > 0, f"{table} is empty"


def test_fact_orders_customer_key_matches_dim_customer(conn):
    orphans = conn.execute("""
        SELECT COUNT(*) FROM fact_orders f
        LEFT JOIN dim_customer d ON f.customer_key = d.customer_key
        WHERE d.customer_key IS NULL
    """).fetchone()[0]
    assert orphans == 0


def test_fact_orders_product_key_matches_dim_product(conn):
    orphans = conn.execute("""
        SELECT COUNT(*) FROM fact_orders f
        LEFT JOIN dim_product d ON f.product_key = d.product_key
        WHERE d.product_key IS NULL
    """).fetchone()[0]
    assert orphans == 0


def test_fact_orders_amount_non_negative(conn):
    bad = conn.execute("SELECT COUNT(*) FROM fact_orders WHERE amount < 0").fetchone()[0]
    assert bad == 0


def test_dim_customer_primary_key_unique(conn):
    dupes = conn.execute(
        "SELECT COUNT(*) FROM (SELECT customer_key, COUNT(*) c FROM dim_customer GROUP BY customer_key HAVING c > 1)"
    ).fetchone()[0]
    assert dupes == 0


# ---------------------------------------------------------------------
# KPI engine output
# ---------------------------------------------------------------------
def test_kpi_snapshot_covers_all_five_domains(conn):
    assert _table_exists(conn, "kpi_snapshot"), "run analytics/kpi_engine.py first"
    domains = pd.read_sql("SELECT DISTINCT domain FROM kpi_snapshot", conn)["domain"].tolist()
    for expected in ["sales", "customers", "inventory", "delivery", "marketing"]:
        assert expected in domains, f"KPI domain '{expected}' missing from kpi_snapshot"


def test_sales_kpis_present(conn):
    metrics = pd.read_sql(
        "SELECT metric FROM kpi_snapshot WHERE domain='sales'", conn
    )["metric"].tolist()
    for expected in ["total_revenue", "total_orders", "average_order_value"]:
        assert expected in metrics


def test_total_revenue_is_positive(conn):
    val = conn.execute(
        "SELECT value FROM kpi_snapshot WHERE domain='sales' AND metric='total_revenue'"
    ).fetchone()
    assert val is not None and val[0] > 0
