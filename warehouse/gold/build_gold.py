"""
OpsPulse 360 - Gold Layer
Builds the business-ready dimensional model (star schema) from the
silver_* tables:

  Dimensions: dim_customer, dim_product, dim_warehouse, dim_date
  Facts:      fact_orders, fact_inventory, fact_delivery

This is the layer BI tools / the FastAPI backend / dbt marts query.
"""
import os
import sqlite3

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
DB_PATH = os.path.join(DATA_DIR, "opspulse.db")


def build_dim_date(conn, start="2025-01-01", end="2026-12-31"):
    dates = pd.date_range(start=start, end=end, freq="D")
    df = pd.DataFrame({"date_key": dates.strftime("%Y%m%d").astype(int), "full_date": dates})
    df["year"] = dates.year
    df["quarter"] = dates.quarter
    df["month"] = dates.month
    df["month_name"] = dates.strftime("%B")
    df["day"] = dates.day
    df["day_of_week"] = dates.strftime("%A")
    df["is_weekend"] = dates.dayofweek.isin([5, 6])
    df.to_sql("dim_date", conn, if_exists="replace", index=False)
    return df


def build_gold():
    conn = sqlite3.connect(DB_PATH)

    # ---- Dimensions ----
    customers = pd.read_sql("SELECT * FROM silver_customers", conn)
    dim_customer = customers.rename(columns={"customer_id": "customer_key"})
    dim_customer.to_sql("dim_customer", conn, if_exists="replace", index=False)

    products = pd.read_sql("SELECT * FROM silver_products", conn)
    dim_product = products.rename(columns={"product_id": "product_key"})
    dim_product["margin_pct"] = (
        (dim_product["selling_price"] - dim_product["cost"]) / dim_product["selling_price"]
    ).round(4)
    dim_product.to_sql("dim_product", conn, if_exists="replace", index=False)

    warehouses = pd.read_sql("SELECT DISTINCT warehouse_id FROM silver_inventory", conn)
    dim_warehouse = warehouses.rename(columns={"warehouse_id": "warehouse_key"})
    dim_warehouse.to_sql("dim_warehouse", conn, if_exists="replace", index=False)

    build_dim_date(conn)

    # ---- fact_orders ----
    orders = pd.read_sql("SELECT * FROM silver_orders", conn)
    orders["timestamp"] = pd.to_datetime(orders["timestamp"])
    orders["date_key"] = orders["timestamp"].dt.strftime("%Y%m%d").astype(int)
    products_cost = products.set_index("product_id")["cost"]
    orders["unit_cost"] = orders["product_id"].map(products_cost).fillna(0)
    orders["cost_total"] = orders["unit_cost"] * orders["quantity"]
    orders["margin_amount"] = (orders["amount"] - orders["cost_total"]).round(2)
    fact_orders = orders.rename(columns={
        "order_id": "order_key", "customer_id": "customer_key",
        "product_id": "product_key", "warehouse_id": "warehouse_key",
    })[["order_key", "customer_key", "product_key", "warehouse_key", "date_key",
        "timestamp", "quantity", "amount", "cost_total", "margin_amount", "status"]]
    fact_orders.to_sql("fact_orders", conn, if_exists="replace", index=False)

    # ---- fact_inventory ----
    inventory = pd.read_sql("SELECT * FROM silver_inventory", conn)
    inventory["updated_at"] = pd.to_datetime(inventory["updated_at"])
    inventory["date_key"] = inventory["updated_at"].dt.strftime("%Y%m%d").astype(int)
    inventory["stock_position"] = inventory["available_qty"] - inventory["reserved_qty"]
    inventory["below_reorder_level"] = inventory["stock_position"] < inventory["reorder_level"]
    fact_inventory = inventory.rename(
        columns={"warehouse_id": "warehouse_key", "product_id": "product_key"}
    )
    fact_inventory.to_sql("fact_inventory", conn, if_exists="replace", index=False)

    # ---- fact_delivery ----
    delivery = pd.read_sql("SELECT * FROM silver_delivery", conn)
    for col in ["pickup_time", "expected_delivery", "actual_delivery"]:
        delivery[col] = pd.to_datetime(delivery[col])
    delivery["date_key"] = delivery["pickup_time"].dt.strftime("%Y%m%d").astype(int)
    delivery["delivery_hours"] = (
        (delivery["actual_delivery"] - delivery["pickup_time"]).dt.total_seconds() / 3600
    ).round(2)
    delivery["sla_breached"] = delivery["actual_delivery"] > delivery["expected_delivery"]
    order_wh = orders.set_index("order_id")["warehouse_id"]
    delivery["warehouse_key"] = delivery["order_id"].map(order_wh)
    fact_delivery = delivery.rename(columns={"order_id": "order_key"})
    fact_delivery.to_sql("fact_delivery", conn, if_exists="replace", index=False)

    # ---- fact_marketing ----
    marketing = pd.read_sql("SELECT * FROM silver_marketing", conn)
    marketing["date"] = pd.to_datetime(marketing["date"])
    marketing["date_key"] = marketing["date"].dt.strftime("%Y%m%d").astype(int)
    import numpy as np
    marketing["ctr"] = (marketing["clicks"] / marketing["impressions"].replace(0, np.nan)).round(4)
    marketing["conversion_rate"] = (marketing["conversions"] / marketing["clicks"].replace(0, np.nan)).round(4)
    marketing["cac"] = (marketing["spend"] / marketing["conversions"].replace(0, np.nan)).round(2)
    fact_marketing = marketing[["campaign_id", "date_key", "channel", "spend", "impressions",
                                 "clicks", "conversions", "ctr", "conversion_rate", "cac"]]
    fact_marketing.to_sql("fact_marketing", conn, if_exists="replace", index=False)

    conn.commit()
    conn.close()
    print("Gold layer built:")
    print(f"  dim_customer:   {len(dim_customer):>7,} rows")
    print(f"  dim_product:    {len(dim_product):>7,} rows")
    print(f"  dim_warehouse:  {len(dim_warehouse):>7,} rows")
    print(f"  fact_orders:    {len(fact_orders):>7,} rows")
    print(f"  fact_inventory: {len(fact_inventory):>7,} rows")
    print(f"  fact_delivery:  {len(fact_delivery):>7,} rows")
    print(f"  fact_marketing: {len(fact_marketing):>7,} rows")


if __name__ == "__main__":
    build_gold()
