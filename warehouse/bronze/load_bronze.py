"""
OpsPulse 360 - Bronze Layer
Loads the 7 mandatory raw source CSVs into SQLite (data/opspulse.db) with
minimal transformation: only adds ingestion metadata (_ingested_at,
_source_file). Nothing is cleaned, deduplicated, or validated here --
that is the Silver layer's job. This mirrors "raw/immutable storage"
(the Lake requirement) landing directly into bronze schema tables since
this build uses a single local warehouse file instead of a separate
GCS/S3 lake + BigQuery/Snowflake warehouse pair.
"""
import os
import sqlite3
from datetime import datetime, timezone

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
DB_PATH = os.path.join(DATA_DIR, "opspulse.db")

SOURCE_FILES = {
    "bronze_orders": "orders.csv",
    "bronze_customers": "customers.csv",
    "bronze_products": "products.csv",
    "bronze_inventory": "inventory.csv",
    "bronze_delivery": "delivery.csv",
    "bronze_support": "support.csv",
    "bronze_marketing": "marketing.csv",
}


def load_bronze():
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now(timezone.utc).isoformat()
    for table, csv_file in SOURCE_FILES.items():
        path = os.path.join(DATA_DIR, csv_file)
        if not os.path.exists(path):
            print(f"  [skip] {csv_file} not found, run data_generator first")
            continue
        df = pd.read_csv(path)
        df["_ingested_at"] = now
        df["_source_file"] = csv_file
        df.to_sql(table, conn, if_exists="replace", index=False)
        print(f"  loaded {len(df):>7,} rows -> {table}")
    conn.close()


if __name__ == "__main__":
    print(f"Loading bronze layer into {DB_PATH} ...")
    load_bronze()
    print("Bronze load complete.")
