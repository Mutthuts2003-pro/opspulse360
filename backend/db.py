"""Shared SQLite connection helper for all routers."""
import os
import sqlite3
import math

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DATA_DIR, "opspulse.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()


def query_records(sql: str, params: tuple = ()) -> list:
    df = query_df(sql, params)
    records = df.to_dict(orient="records")
    # Sanitize NaN/NaT -> None. Doing this on the raw dicts (not the
    # DataFrame) is necessary because assigning None into a float64
    # column snaps back to NaN (pandas can't hold None in a float
    # column) -- and Starlette's JSONResponse calls json.dumps with
    # allow_nan=False, so a stray NaN raises "Out of range float
    # values are not JSON compliant" at response time.
    for rec in records:
        for k, v in rec.items():
            if isinstance(v, float) and math.isnan(v):
                rec[k] = None
    return records
