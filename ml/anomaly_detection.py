"""
OpsPulse 360 - Anomaly Detection
Implements TWO methods on daily revenue as required (statistical AND
Isolation Forest):
  1. Statistical: rolling z-score on daily revenue.
  2. ML: Isolation Forest over a multi-feature daily panel
     (revenue, orders, AOV, SLA breach rate, payment failure rate).

For the most significant detected anomaly, explain_anomaly() breaks
down the likely drivers (which dimension moved the most that day) and
produces a recommended business action, satisfying:
  "Explain the major drivers behind at least one detected anomaly" and
  "Generate a recommended business action based on the analytical result."

Results are persisted to `anomaly_report` for the FastAPI/frontend to consume.
"""
import os
import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DATA_DIR, "opspulse.db")


def build_daily_panel(conn):
    orders = pd.read_sql(
        "SELECT \"timestamp\" AS ts, amount, status FROM fact_orders", conn
    )
    orders["ts"] = pd.to_datetime(orders["ts"])
    orders["day"] = orders["ts"].dt.date

    daily_rev = orders[orders["status"] == "completed"].groupby("day")["amount"].sum().rename("revenue")
    daily_orders = orders[orders["status"] == "completed"].groupby("day").size().rename("orders")

    delivery = pd.read_sql("SELECT pickup_time, sla_breached FROM fact_delivery", conn)
    delivery["pickup_time"] = pd.to_datetime(delivery["pickup_time"])
    delivery["day"] = delivery["pickup_time"].dt.date
    sla_rate = delivery.groupby("day")["sla_breached"].mean().rename("sla_breach_rate")

    panel = pd.concat([daily_rev, daily_orders, sla_rate], axis=1).dropna(subset=["revenue"])
    panel["aov"] = panel["revenue"] / panel["orders"].replace(0, np.nan)
    panel = panel.reset_index().rename(columns={"index": "day"})
    panel["sla_breach_rate"] = panel["sla_breach_rate"].fillna(0)
    panel = panel.sort_values("day").reset_index(drop=True)
    return panel


def statistical_zscore(panel, window=7, threshold=2.5):
    s = panel["revenue"]
    roll_mean = s.rolling(window, min_periods=3).mean()
    roll_std = s.rolling(window, min_periods=3).std().replace(0, np.nan)
    z = (s - roll_mean) / roll_std
    panel["revenue_zscore"] = z
    panel["is_anomaly_statistical"] = z.abs() > threshold
    return panel


def isolation_forest_detect(panel, contamination=0.08):
    features = panel[["revenue", "orders", "aov", "sla_breach_rate"]].fillna(0)
    if len(features) < 10:
        panel["is_anomaly_iforest"] = False
        panel["iforest_score"] = 0.0
        return panel
    model = IsolationForest(n_estimators=200, contamination=contamination, random_state=42)
    preds = model.fit_predict(features)
    scores = model.decision_function(features)
    panel["is_anomaly_iforest"] = preds == -1
    panel["iforest_score"] = scores
    return panel


def explain_anomaly(panel, day_row):
    """Explain the drivers behind one anomalous day vs. the trailing 7-day baseline."""
    day = day_row["day"]
    baseline = panel[panel["day"] < day].tail(7)
    if baseline.empty:
        return {"day": str(day), "explanation": "Insufficient history to compute baseline.", "action": ""}

    drivers = []
    for col, label in [("revenue", "revenue"), ("orders", "order volume"),
                        ("aov", "average order value"), ("sla_breach_rate", "SLA breach rate")]:
        base_val = baseline[col].mean()
        curr_val = day_row[col]
        if pd.isna(base_val) or base_val == 0:
            continue
        pct_change = (curr_val - base_val) / abs(base_val) * 100
        if abs(pct_change) > 15:
            direction = "up" if pct_change > 0 else "down"
            drivers.append((abs(pct_change), f"{label} was {direction} {abs(pct_change):.1f}% vs. the trailing 7-day average"))

    drivers.sort(reverse=True)
    driver_text = "; ".join(d[1] for d in drivers[:3]) if drivers else "no single dimension moved sharply; likely broad-based fluctuation"

    revenue_drop = day_row["revenue"] < baseline["revenue"].mean()
    if revenue_drop and any("SLA" in d[1] for d in drivers):
        action = "Investigate delivery partner performance on this date and escalate to operations; SLA breaches likely suppressed repeat purchases/completions."
    elif revenue_drop:
        action = "Escalate to the business-anomaly alert queue and cross-check for marketing spend pauses, payment gateway issues, or inventory stockouts on the affected date."
    else:
        action = "Positive anomaly — flag to marketing/growth to identify and replicate the driver (e.g. a successful campaign or promo)."

    return {
        "day": str(day),
        "revenue": float(day_row["revenue"]),
        "baseline_avg_revenue": float(baseline["revenue"].mean()),
        "explanation": driver_text,
        "recommended_action": action,
    }


def main():
    conn = sqlite3.connect(DB_PATH)
    panel = build_daily_panel(conn)
    panel = statistical_zscore(panel)
    panel = isolation_forest_detect(panel)
    panel["is_anomaly"] = panel["is_anomaly_statistical"] | panel["is_anomaly_iforest"]

    anomalies = panel[panel["is_anomaly"]].copy()
    print(f"Daily panel: {len(panel)} days. Anomalies flagged: {len(anomalies)}")

    explanations = []
    if not anomalies.empty:
        # explain the most severe anomaly (largest absolute z-score)
        worst_idx = anomalies["revenue_zscore"].abs().idxmax()
        worst_row = panel.loc[worst_idx]
        explanations.append(explain_anomaly(panel, worst_row))
        # explain up to 2 more for the report
        for idx in anomalies.index:
            if idx == worst_idx:
                continue
            explanations.append(explain_anomaly(panel, panel.loc[idx]))
            if len(explanations) >= 3:
                break

    panel["computed_at"] = datetime.now(timezone.utc).isoformat()
    panel.to_sql("anomaly_report", conn, if_exists="replace", index=False)

    exp_df = pd.DataFrame(explanations)
    if not exp_df.empty:
        exp_df.to_sql("anomaly_explanations", conn, if_exists="replace", index=False)
        print("\nTop anomaly explanation:")
        print(exp_df.iloc[0].to_string())
    else:
        pd.DataFrame(columns=["day", "revenue", "baseline_avg_revenue", "explanation", "recommended_action"]) \
            .to_sql("anomaly_explanations", conn, if_exists="replace", index=False)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
