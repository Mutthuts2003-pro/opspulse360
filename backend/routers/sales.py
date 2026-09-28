"""Sales / revenue analytics endpoints."""
from fastapi import APIRouter, Query
from db import query_records, query_df

router = APIRouter()


@router.get("/revenue/daily")
def daily_revenue(limit: int = Query(90, le=1000)):
    df = query_df("""
        SELECT date(\"timestamp\") AS day, SUM(amount) AS revenue, COUNT(*) AS orders
        FROM fact_orders WHERE status = 'completed'
        GROUP BY day ORDER BY day DESC LIMIT ?
    """, (limit,))
    return df.sort_values("day").to_dict(orient="records")


@router.get("/revenue/by-category")
def revenue_by_category():
    df = query_df("""
        SELECT p.category, SUM(f.amount) AS revenue, SUM(f.quantity) AS units, COUNT(*) AS orders
        FROM fact_orders f JOIN dim_product p ON f.product_key = p.product_key
        WHERE f.status = 'completed'
        GROUP BY p.category ORDER BY revenue DESC
    """)
    return df.to_dict(orient="records")


@router.get("/revenue/by-warehouse")
def revenue_by_warehouse():
    df = query_df("""
        SELECT warehouse_key AS warehouse, SUM(amount) AS revenue, COUNT(*) AS orders
        FROM fact_orders WHERE status = 'completed'
        GROUP BY warehouse_key ORDER BY revenue DESC
    """)
    return df.to_dict(orient="records")


@router.get("/orders")
def list_orders(limit: int = Query(50, le=500), status: str = None):
    sql = "SELECT * FROM fact_orders"
    params = ()
    if status:
        sql += " WHERE status = ?"
        params = (status,)
    sql += " ORDER BY \"timestamp\" DESC LIMIT ?"
    params = params + (limit,)
    return query_records(sql, params)
