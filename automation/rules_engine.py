"""
OpsPulse 360 - Automation: Business Rules Engine + Notifications
Implements the 4 mandatory rules:
  1. Inventory below reorder level AND forecast demand exceeds available inventory -> HIGH inventory alert
  2. Delivery SLA breach % exceeds threshold -> notify operations
  3. Revenue materially below expected (forecast) -> business anomaly alert
  4. Payment failure rate crosses threshold -> notify relevant team

Alerts are persisted to `alerts` (severity + status, backing the
"Alert Center" application page) and at least one rule fires a REAL
notification via email (SMTP) or Slack (incoming webhook) -- see
notifier.py. Both are config-driven through environment variables so
this runs safely with no credentials configured (it logs what WOULD be
sent and marks the alert as notified=False in that case).
"""
import os
import sqlite3
from datetime import datetime, timezone

import pandas as pd

from notifier import send_notification

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DATA_DIR, "opspulse.db")

# ---- configurable thresholds ----
SLA_BREACH_THRESHOLD_PCT = float(os.environ.get("SLA_BREACH_THRESHOLD_PCT", 15.0))
REVENUE_SHORTFALL_THRESHOLD_PCT = float(os.environ.get("REVENUE_SHORTFALL_THRESHOLD_PCT", 20.0))
PAYMENT_FAILURE_THRESHOLD_PCT = float(os.environ.get("PAYMENT_FAILURE_THRESHOLD_PCT", 5.0))


def _new_alert(rows, rule, severity, message, entity=""):
    rows.append({
        "alert_id": f"ALRT-{len(rows) + 1:05d}-{int(datetime.now().timestamp())}",
        "rule": rule,
        "severity": severity,          # LOW / MEDIUM / HIGH / CRITICAL
        "status": "OPEN",              # OPEN / ACKNOWLEDGED / RESOLVED
        "entity": entity,
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


def rule_inventory_stockout_risk(conn, rows):
    """Rule 1: inventory below reorder level AND recent product demand suggests it'll run out."""
    inv = pd.read_sql("SELECT * FROM fact_inventory", conn)
    orders = pd.read_sql(
        "SELECT product_key, quantity, \"timestamp\" AS ts FROM fact_orders WHERE status='completed'", conn
    )
    orders["ts"] = pd.to_datetime(orders["ts"])
    recent = orders[orders["ts"] >= orders["ts"].max() - pd.Timedelta(days=7)]
    avg_daily_demand = recent.groupby("product_key")["quantity"].sum() / 7.0

    at_risk = inv[inv["below_reorder_level"] == 1].copy()
    at_risk["avg_daily_demand"] = at_risk["product_key"].map(avg_daily_demand).fillna(0)
    at_risk["days_of_cover"] = at_risk["stock_position"] / at_risk["avg_daily_demand"].replace(0, 1e-9)
    high_risk = at_risk[(at_risk["avg_daily_demand"] > 0) & (at_risk["days_of_cover"] < 3)]

    for _, r in high_risk.iterrows():
        _new_alert(
            rows, "inventory_stockout_risk", "HIGH",
            f"Product {r['product_key']} at warehouse {r['warehouse_key']} is below reorder level "
            f"({r['stock_position']} units) with ~{r['avg_daily_demand']:.1f} units/day demand "
            f"(~{r['days_of_cover']:.1f} days of cover left).",
            entity=f"{r['warehouse_key']}:{r['product_key']}",
        )
    return len(high_risk)


def rule_delivery_sla_breach(conn, rows):
    """Rule 2: delivery SLA breach % exceeds threshold -> notify operations."""
    fd = pd.read_sql("SELECT * FROM fact_delivery", conn)
    if fd.empty:
        return 0
    breach_pct = fd["sla_breached"].astype(bool).mean() * 100
    if breach_pct > SLA_BREACH_THRESHOLD_PCT:
        _new_alert(
            rows, "delivery_sla_breach", "HIGH",
            f"Overall delivery SLA breach rate is {breach_pct:.1f}%, above the "
            f"{SLA_BREACH_THRESHOLD_PCT:.0f}% threshold. Operations team notified.",
            entity="delivery_network",
        )
        return 1
    return 0


def rule_revenue_anomaly(conn, rows):
    """Rule 3: latest actual daily revenue materially below forecast -> business anomaly alert."""
    try:
        forecast = pd.read_sql("SELECT * FROM revenue_forecast ORDER BY forecast_day ASC", conn)
    except Exception:
        return 0
    if forecast.empty:
        return 0
    orders = pd.read_sql(
        "SELECT \"timestamp\" AS ts, amount FROM fact_orders WHERE status='completed'", conn
    )
    orders["ts"] = pd.to_datetime(orders["ts"])
    last_actual_day = orders["ts"].dt.date.max()
    last_actual_rev = orders[orders["ts"].dt.date == last_actual_day]["amount"].sum()

    matching_forecast = forecast[forecast["forecast_day"] == str(last_actual_day)]
    expected = matching_forecast["predicted_revenue"].iloc[0] if not matching_forecast.empty else None

    if expected and expected > 0:
        shortfall_pct = (expected - last_actual_rev) / expected * 100
        if shortfall_pct > REVENUE_SHORTFALL_THRESHOLD_PCT:
            _new_alert(
                rows, "revenue_anomaly", "CRITICAL",
                f"Revenue on {last_actual_day} was {last_actual_rev:,.0f}, "
                f"{shortfall_pct:.1f}% below the forecast of {expected:,.0f}.",
                entity=str(last_actual_day),
            )
            return 1
    return 0


def rule_payment_failure_rate(conn, rows):
    """Rule 4: payment failure rate crosses threshold -> notify relevant team."""
    try:
        conn_check = conn.execute(
            "SELECT metric_value FROM live_metrics WHERE metric_key='live_payments_total'"
        ).fetchone()
        fail_check = conn.execute(
            "SELECT metric_value FROM live_metrics WHERE metric_key='live_payment_failures_total'"
        ).fetchone()
    except Exception:
        return 0
    if not conn_check or not conn_check[0]:
        return 0
    total = conn_check[0]
    failures = fail_check[0] if fail_check else 0
    failure_pct = (failures / total * 100) if total else 0
    if failure_pct > PAYMENT_FAILURE_THRESHOLD_PCT:
        _new_alert(
            rows, "payment_failure_rate", "HIGH",
            f"Payment failure rate is {failure_pct:.1f}% ({int(failures)}/{int(total)} payments), "
            f"above the {PAYMENT_FAILURE_THRESHOLD_PCT:.0f}% threshold. Payments/engineering team notified.",
            entity="payments_platform",
        )
        return 1
    return 0


def main():
    conn = sqlite3.connect(DB_PATH)
    rows = []

    n1 = rule_inventory_stockout_risk(conn, rows)
    n2 = rule_delivery_sla_breach(conn, rows)
    n3 = rule_revenue_anomaly(conn, rows)
    n4 = rule_payment_failure_rate(conn, rows)

    print(f"Rule 1 (inventory stockout risk): {n1} alert(s)")
    print(f"Rule 2 (delivery SLA breach):      {n2} alert(s)")
    print(f"Rule 3 (revenue anomaly):          {n3} alert(s)")
    print(f"Rule 4 (payment failure rate):     {n4} alert(s)")

    alerts_df = pd.DataFrame(rows)
    notified_flags = []
    for _, alert in alerts_df.iterrows() if not alerts_df.empty else []:
        if alert["severity"] in ("HIGH", "CRITICAL"):
            ok = send_notification(
                subject=f"[OpsPulse 360] {alert['severity']} alert: {alert['rule']}",
                message=alert["message"],
            )
            notified_flags.append(ok)
        else:
            notified_flags.append(False)

    if not alerts_df.empty:
        alerts_df["notified"] = notified_flags
        # append to existing alerts table rather than replace, so history accumulates
        try:
            existing = pd.read_sql("SELECT * FROM alerts", conn)
            alerts_df = pd.concat([existing, alerts_df], ignore_index=True)
        except Exception:
            pass
        alerts_df.to_sql("alerts", conn, if_exists="replace", index=False)
    else:
        try:
            pd.read_sql("SELECT * FROM alerts", conn)
        except Exception:
            pd.DataFrame(columns=["alert_id", "rule", "severity", "status", "entity", "message",
                                   "created_at", "notified"]).to_sql("alerts", conn, if_exists="replace", index=False)

    conn.commit()
    conn.close()
    print(f"\nTotal new alerts this run: {len(rows)}")


if __name__ == "__main__":
    main()
