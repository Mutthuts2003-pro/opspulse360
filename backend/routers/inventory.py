"""Inventory analytics endpoints."""
from fastapi import APIRouter, Query
from db import query_records, query_df

router = APIRouter()


@router.get("/status")
def inventory_status(limit: int = Query(200, le=2000)):
    return query_records(
        "SELECT * FROM fact_inventory ORDER BY below_reorder_level DESC, stock_position ASC LIMIT ?", (limit,)
    )


@router.get("/at-risk")
def at_risk_items():
    return query_records(
        "SELECT * FROM fact_inventory WHERE below_reorder_level = 1 ORDER BY stock_position ASC"
    )


@router.get("/by-warehouse")
def by_warehouse():
    df = query_df("""
        SELECT warehouse_key, COUNT(*) AS sku_count,
               SUM(CASE WHEN below_reorder_level = 1 THEN 1 ELSE 0 END) AS skus_below_reorder,
               AVG(stock_position) AS avg_stock_position
        FROM fact_inventory GROUP BY warehouse_key
    """)
    return df.to_dict(orient="records")
