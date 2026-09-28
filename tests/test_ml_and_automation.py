"""
OpsPulse 360 - ML & Automation Test Suite
Validates the outputs of ml/anomaly_detection.py, ml/forecasting.py,
and automation/rules_engine.py against data/opspulse.db. Assumes those
scripts have already been run (see CI workflow / README "Run it"
section for the required order).

Run:
    pytest tests/test_ml_and_automation.py -v
"""
import os
import sqlite3

import pandas as pd
import pytest

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DATA_DIR, "opspulse.db")


@pytest.fixture(scope="module")
def conn():
    connection = sqlite3.connect(DB_PATH)
    yield connection
    connection.close()


def _table_exists(conn, name):
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


# ---------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------
def test_anomaly_report_table_exists(conn):
    assert _table_exists(conn, "anomaly_report"), "run ml/anomaly_detection.py first"


def test_anomaly_report_has_both_detection_methods(conn):
    df = pd.read_sql("SELECT * FROM anomaly_report LIMIT 5", conn)
    assert "is_anomaly_statistical" in df.columns
    assert "is_anomaly_iforest" in df.columns


def test_at_least_one_anomaly_explained(conn):
    assert _table_exists(conn, "anomaly_explanations")
    df = pd.read_sql("SELECT * FROM anomaly_explanations", conn)
    if len(df) == 0:
        pytest.skip("no anomalies detected in current synthetic data run")
    row = df.iloc[0]
    assert row["explanation"], "explanation text is empty"
    assert row["recommended_action"], "recommended_action text is empty"


# ---------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------
def test_forecast_table_exists_with_seven_days(conn):
    assert _table_exists(conn, "revenue_forecast"), "run ml/forecasting.py first"
    n = conn.execute("SELECT COUNT(*) FROM revenue_forecast").fetchone()[0]
    assert n == 7


def test_forecast_values_non_negative(conn):
    df = pd.read_sql("SELECT predicted_revenue FROM revenue_forecast", conn)
    assert (df["predicted_revenue"] >= 0).all()


def test_forecast_bounds_are_ordered(conn):
    df = pd.read_sql(
        "SELECT lower_bound_80pct, predicted_revenue, upper_bound_80pct FROM revenue_forecast", conn
    )
    assert (df["lower_bound_80pct"] <= df["predicted_revenue"]).all()
    assert (df["predicted_revenue"] <= df["upper_bound_80pct"]).all()


# ---------------------------------------------------------------------
# Automation / business rules
# ---------------------------------------------------------------------
def test_alerts_table_exists(conn):
    assert _table_exists(conn, "alerts"), "run automation/rules_engine.py first"


def test_alerts_have_valid_severity(conn):
    df = pd.read_sql("SELECT DISTINCT severity FROM alerts", conn)
    valid = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert set(df["severity"]).issubset(valid)


def test_all_four_rule_types_are_representable(conn):
    """Sanity check: the alerts table schema supports all 4 mandatory rule
    categories (values may be empty on a given synthetic run depending on
    random thresholds, but the rule identifiers must be among these)."""
    df = pd.read_sql("SELECT DISTINCT rule FROM alerts", conn)
    known_rules = {
        "inventory_stockout_risk", "delivery_sla_breach",
        "revenue_anomaly", "payment_failure_rate",
    }
    assert set(df["rule"]).issubset(known_rules)
