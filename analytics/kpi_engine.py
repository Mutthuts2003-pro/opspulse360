"""
OpsPulse 360 - KPI Analytics Engine
Computes the minimum required KPIs across all 5 domains (Sales,
Customers, Inventory, Delivery, Marketing) from the gold-layer star
schema, and persists them to a `kpi_snapshot` table that the FastAPI
backend serves. Run after warehouse/build_warehouse.py.
"""
import os
import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DATA_DIR, "opspulse.db")


def _snap(rows, domain, metric, value, dims=None):
    rows.append({
        "domain": domain,
        "metric": metric,
        "value": None if value is None or pd.isna(value) else float(value),
        "dims": dims or "",
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })


def compute_sales_kpis(conn, rows):
    fo = pd.read_sql("SELECT * FROM fact_orders WHERE status='completed'", conn)
    revenue = fo["amount"].sum()
    orders = len(fo)
    aov = revenue / orders if orders else 0
    units = fo["quantity"].sum()
    margin = fo["margin_amount"].sum()
    margin_pct = (margin / revenue * 100) if revenue else 0

    fo["order_ts"] = pd.to_datetime(fo["timestamp"])
    fo["month"] = fo["order_ts"].dt.to_period("M")
    monthly = fo.groupby("month")["amount"].sum().sort_index()
    growth_pct = None
    if len(monthly) >= 2:
        prev, curr = monthly.iloc[-2], monthly.iloc[-1]
        growth_pct = ((curr - prev) / prev * 100) if prev else None

    _snap(rows, "sales", "total_revenue", revenue)
    _snap(rows, "sales", "total_orders", orders)
    _snap(rows, "sales", "average_order_value", aov)
    _snap(rows, "sales", "total_units_sold", units)
    _snap(rows, "sales", "total_margin", margin)
    _snap(rows, "sales", "margin_pct", margin_pct)
    _snap(rows, "sales", "mom_revenue_growth_pct", growth_pct)


def compute_customer_kpis(conn, rows):
    customers = pd.read_sql("SELECT * FROM dim_customer", conn)
    fo = pd.read_sql("SELECT customer_key, \"timestamp\" AS order_ts FROM fact_orders WHERE status='completed'", conn)
    fo["order_ts"] = pd.to_datetime(fo["order_ts"])

    orders_per_cust = fo.groupby("customer_key").size()
    repeat_customers = (orders_per_cust >= 2).sum()
    repeat_rate = (repeat_customers / len(orders_per_cust) * 100) if len(orders_per_cust) else 0

    customers["registration_date"] = pd.to_datetime(customers["registration_date"])
    last_30 = customers[customers["registration_date"] >= (customers["registration_date"].max() - pd.Timedelta(days=30))]
    new_customers_30d = len(last_30)

    seg_perf = fo.merge(customers[["customer_key", "segment"]], on="customer_key", how="left")
    seg_revenue = seg_perf.groupby("segment").size()

    _snap(rows, "customers", "total_customers", len(customers))
    _snap(rows, "customers", "repeat_customer_rate_pct", repeat_rate)
    _snap(rows, "customers", "new_customers_last_30d", new_customers_30d)
    for seg, cnt in seg_revenue.items():
        _snap(rows, "customers", "orders_by_segment", cnt, dims=f"segment={seg}")


def compute_inventory_kpis(conn, rows):
    fi = pd.read_sql("SELECT * FROM fact_inventory", conn)
    fo = pd.read_sql("SELECT product_key, quantity FROM fact_orders WHERE status='completed'", conn)

    stockout_risk_items = int((fi["stock_position"] <= 0).sum())
    below_reorder = int(fi["below_reorder_level"].sum())
    avg_stock = fi["stock_position"].mean()

    units_sold_by_product = fo.groupby("product_key")["quantity"].sum()
    avg_stock_by_product = fi.groupby("product_key")["stock_position"].mean()
    turnover = (units_sold_by_product / avg_stock_by_product.replace(0, np.nan)).dropna()
    inventory_turnover = turnover.mean() if len(turnover) else 0
    days_of_inventory = (365 / inventory_turnover) if inventory_turnover else None

    _snap(rows, "inventory", "stockout_risk_item_count", stockout_risk_items)
    _snap(rows, "inventory", "items_below_reorder_level", below_reorder)
    _snap(rows, "inventory", "avg_stock_position", avg_stock)
    _snap(rows, "inventory", "inventory_turnover_ratio", inventory_turnover)
    _snap(rows, "inventory", "days_of_inventory", days_of_inventory)


def compute_delivery_kpis(conn, rows):
    fd = pd.read_sql("SELECT * FROM fact_delivery", conn)
    total = len(fd)
    on_time = int((~fd["sla_breached"].astype(bool)).sum())
    on_time_pct = (on_time / total * 100) if total else 0
    sla_breach_pct = 100 - on_time_pct
    avg_delivery_hours = fd["delivery_hours"].mean()

    by_partner = fd.groupby("partner").agg(
        deliveries=("order_key", "count"),
        sla_breach_rate=("sla_breached", lambda s: s.astype(bool).mean() * 100),
    ).reset_index()

    _snap(rows, "delivery", "on_time_delivery_pct", on_time_pct)
    _snap(rows, "delivery", "sla_breach_pct", sla_breach_pct)
    _snap(rows, "delivery", "avg_delivery_hours", avg_delivery_hours)
    for _, r in by_partner.iterrows():
        _snap(rows, "delivery", "partner_sla_breach_pct", r["sla_breach_rate"], dims=f"partner={r['partner']}")


def compute_marketing_kpis(conn, rows):
    fm = pd.read_sql("SELECT * FROM fact_marketing", conn)
    total_spend = fm["spend"].sum()
    total_clicks = fm["clicks"].sum()
    total_impr = fm["impressions"].sum()
    total_conv = fm["conversions"].sum()

    ctr = (total_clicks / total_impr * 100) if total_impr else 0
    conv_rate = (total_conv / total_clicks * 100) if total_clicks else 0
    cac = (total_spend / total_conv) if total_conv else None

    # Rough ROAS assumption: revenue per conversion approximated from overall AOV
    fo = pd.read_sql("SELECT amount FROM fact_orders WHERE status='completed'", conn)
    aov = fo["amount"].mean() if len(fo) else 0
    est_revenue = total_conv * aov
    roas = (est_revenue / total_spend) if total_spend else None

    by_channel = fm.groupby("channel").agg(spend=("spend", "sum"), conversions=("conversions", "sum")).reset_index()
    by_channel["cac"] = by_channel["spend"] / by_channel["conversions"].replace(0, np.nan)

    _snap(rows, "marketing", "total_spend", total_spend)
    _snap(rows, "marketing", "ctr_pct", ctr)
    _snap(rows, "marketing", "conversion_rate_pct", conv_rate)
    _snap(rows, "marketing", "cac", cac)
    _snap(rows, "marketing", "estimated_roas", roas)
    for _, r in by_channel.iterrows():
        _snap(rows, "marketing", "channel_cac", r["cac"], dims=f"channel={r['channel']}")


def main():
    conn = sqlite3.connect(DB_PATH)
    rows = []
    compute_sales_kpis(conn, rows)
    compute_customer_kpis(conn, rows)
    compute_inventory_kpis(conn, rows)
    compute_delivery_kpis(conn, rows)
    compute_marketing_kpis(conn, rows)

    df = pd.DataFrame(rows)
    df.to_sql("kpi_snapshot", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()
    print(f"Computed {len(df)} KPI records across 5 domains -> kpi_snapshot table")
    print(df.groupby("domain").size())


if __name__ == "__main__":
    main()
