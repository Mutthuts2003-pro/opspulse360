"""
OpsPulse 360 - Demand / Sales Forecasting
Forecasts daily revenue for the next 7 days. Uses a lightweight,
dependency-free model (linear trend + day-of-week seasonality fitted
with least squares) so it runs anywhere without needing Prophet/statsmodels
installed -- swapping in Prophet/ARIMA/XGBoost in production is a drop-in
replacement for `fit_forecast_model()` below, the rest of the pipeline
(persistence, API, frontend) does not change.
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DATA_DIR, "opspulse.db")
HORIZON_DAYS = 7


def load_daily_revenue(conn):
    orders = pd.read_sql(
        "SELECT \"timestamp\" AS ts, amount FROM fact_orders WHERE status='completed'", conn
    )
    orders["ts"] = pd.to_datetime(orders["ts"])
    daily = orders.groupby(orders["ts"].dt.date)["amount"].sum().rename("revenue").reset_index()
    daily.columns = ["day", "revenue"]
    daily["day"] = pd.to_datetime(daily["day"])
    daily = daily.sort_values("day").reset_index(drop=True)
    return daily


def fit_forecast_model(daily: pd.DataFrame):
    """Linear trend + day-of-week seasonal offsets, fit by least squares."""
    df = daily.copy()
    df["t"] = np.arange(len(df))
    df["dow"] = df["day"].dt.dayofweek

    dow_dummies = pd.get_dummies(df["dow"], prefix="dow", drop_first=True).astype(float)
    X = np.column_stack([np.ones(len(df)), df["t"].values, dow_dummies.values])
    y = df["revenue"].values

    coeffs, *_ = np.linalg.lstsq(X, y, rcond=None)
    residuals = y - X @ coeffs
    resid_std = float(np.std(residuals))

    return {
        "coeffs": coeffs,
        "dow_columns": list(dow_dummies.columns),
        "last_t": int(df["t"].iloc[-1]),
        "last_day": df["day"].iloc[-1],
        "resid_std": resid_std,
    }


def forecast_next_days(model, horizon=HORIZON_DAYS):
    coeffs = model["coeffs"]
    dow_columns = model["dow_columns"]  # e.g. dow_1..dow_6 (Monday=0 dropped as baseline)
    rows = []
    for h in range(1, horizon + 1):
        future_day = model["last_day"] + timedelta(days=h)
        t = model["last_t"] + h
        dow = future_day.dayofweek
        dow_vec = [1.0 if col == f"dow_{dow}" else 0.0 for col in dow_columns]
        x = np.array([1.0, t] + dow_vec)
        point = float(x @ coeffs)
        point = max(point, 0.0)
        rows.append({
            "forecast_day": future_day.strftime("%Y-%m-%d"),
            "predicted_revenue": round(point, 2),
            "lower_bound_80pct": round(max(point - 1.28 * model["resid_std"], 0), 2),
            "upper_bound_80pct": round(point + 1.28 * model["resid_std"], 2),
        })
    return pd.DataFrame(rows)


def main():
    conn = sqlite3.connect(DB_PATH)
    daily = load_daily_revenue(conn)
    if len(daily) < 14:
        print("Not enough history to forecast reliably (need >= 14 days).")
        return

    model = fit_forecast_model(daily)
    forecast_df = forecast_next_days(model, HORIZON_DAYS)
    forecast_df["generated_at"] = datetime.now(timezone.utc).isoformat()
    forecast_df["model"] = "linear_trend_plus_dow_seasonality"

    forecast_df.to_sql("revenue_forecast", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()

    print(f"7-day revenue forecast (fit on {len(daily)} days of history):")
    print(forecast_df.to_string(index=False))


if __name__ == "__main__":
    main()
