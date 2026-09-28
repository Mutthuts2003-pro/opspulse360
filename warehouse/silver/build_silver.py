"""
OpsPulse 360 - Silver Layer
Reads bronze_* tables, applies cleaning / standardization / deduplication
/ validation, and writes silver_* tables. Also writes a data-quality
report (dq_report table) capturing what was rejected and why, which
backs the "Data-quality / pipeline-monitoring page" application
requirement.
"""
import os
import sqlite3
from datetime import datetime, timezone

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
DB_PATH = os.path.join(DATA_DIR, "opspulse.db")


def _dq_log(rows, table, rule, count):
    rows.append({
        "table_name": table,
        "rule": rule,
        "failed_rows": count,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    })


def build_silver():
    conn = sqlite3.connect(DB_PATH)
    dq_rows = []

    # ---- customers ----
    customers = pd.read_sql("SELECT * FROM bronze_customers", conn)
    before = len(customers)
    customers = customers.dropna(subset=["customer_id"])
    customers = customers.drop_duplicates(subset=["customer_id"])
    _dq_log(dq_rows, "silver_customers", "null_or_dup_customer_id", before - len(customers))
    customers.to_sql("silver_customers", conn, if_exists="replace", index=False)

    # ---- products ----
    products = pd.read_sql("SELECT * FROM bronze_products", conn)
    before = len(products)
    products = products.dropna(subset=["product_id"])
    products = products.drop_duplicates(subset=["product_id"])
    invalid_price = products[products["selling_price"] <= 0]
    _dq_log(dq_rows, "silver_products", "non_positive_selling_price", len(invalid_price))
    products = products[products["selling_price"] > 0]
    _dq_log(dq_rows, "silver_products", "null_or_dup_product_id", before - len(products) - len(invalid_price))
    products.to_sql("silver_products", conn, if_exists="replace", index=False)

    valid_customer_ids = set(customers["customer_id"])
    valid_product_ids = set(products["product_id"])

    # ---- orders ----
    orders = pd.read_sql("SELECT * FROM bronze_orders", conn)
    before = len(orders)
    orders = orders.dropna(subset=["order_id", "customer_id", "product_id", "amount"])
    dup_mask = orders.duplicated(subset=["order_id"])
    _dq_log(dq_rows, "silver_orders", "duplicate_order_id", int(dup_mask.sum()))
    orders = orders[~dup_mask]

    ref_bad = ~orders["customer_id"].isin(valid_customer_ids) | ~orders["product_id"].isin(valid_product_ids)
    _dq_log(dq_rows, "silver_orders", "referential_integrity_customer_or_product", int(ref_bad.sum()))
    orders = orders[~ref_bad]

    neg_amount = orders["amount"] < 0
    _dq_log(dq_rows, "silver_orders", "negative_amount", int(neg_amount.sum()))
    orders = orders[~neg_amount]
    orders["timestamp"] = pd.to_datetime(orders["timestamp"], errors="coerce")
    bad_ts = orders["timestamp"].isna()
    _dq_log(dq_rows, "silver_orders", "invalid_timestamp", int(bad_ts.sum()))
    orders = orders[~bad_ts]
    _dq_log(dq_rows, "silver_orders", "rows_dropped_total", before - len(orders))
    orders.to_sql("silver_orders", conn, if_exists="replace", index=False)

    # ---- inventory ----
    inventory = pd.read_sql("SELECT * FROM bronze_inventory", conn)
    before = len(inventory)
    inventory = inventory.dropna(subset=["warehouse_id", "product_id"])
    inventory = inventory.drop_duplicates(subset=["warehouse_id", "product_id"], keep="last")
    neg_qty = (inventory["available_qty"] < 0) | (inventory["reserved_qty"] < 0)
    _dq_log(dq_rows, "silver_inventory", "negative_quantity", int(neg_qty.sum()))
    inventory = inventory[~neg_qty]
    _dq_log(dq_rows, "silver_inventory", "rows_dropped_total", before - len(inventory))
    inventory.to_sql("silver_inventory", conn, if_exists="replace", index=False)

    # ---- delivery ----
    delivery = pd.read_sql("SELECT * FROM bronze_delivery", conn)
    before = len(delivery)
    delivery = delivery.dropna(subset=["order_id"])
    delivery = delivery.drop_duplicates(subset=["order_id"], keep="last")
    for col in ["pickup_time", "expected_delivery", "actual_delivery"]:
        delivery[col] = pd.to_datetime(delivery[col], errors="coerce")
    _dq_log(dq_rows, "silver_delivery", "rows_dropped_total", before - len(delivery))
    delivery.to_sql("silver_delivery", conn, if_exists="replace", index=False)

    # ---- support ----
    support = pd.read_sql("SELECT * FROM bronze_support", conn)
    before = len(support)
    support = support.dropna(subset=["ticket_id"])
    support = support.drop_duplicates(subset=["ticket_id"])
    _dq_log(dq_rows, "silver_support", "rows_dropped_total", before - len(support))
    support.to_sql("silver_support", conn, if_exists="replace", index=False)

    # ---- marketing ----
    marketing = pd.read_sql("SELECT * FROM bronze_marketing", conn)
    before = len(marketing)
    marketing = marketing.dropna(subset=["campaign_id", "date"])
    marketing = marketing.drop_duplicates(subset=["campaign_id", "date", "channel"])
    _dq_log(dq_rows, "silver_marketing", "rows_dropped_total", before - len(marketing))
    marketing.to_sql("silver_marketing", conn, if_exists="replace", index=False)

    # ---- persist DQ report ----
    dq_df = pd.DataFrame(dq_rows)
    dq_df.to_sql("dq_report", conn, if_exists="replace", index=False)

    conn.commit()
    conn.close()
    print(f"Silver build complete. {len(dq_rows)} data-quality checks logged to dq_report.")
    return dq_df


if __name__ == "__main__":
    df = build_silver()
    print(df.to_string(index=False))
