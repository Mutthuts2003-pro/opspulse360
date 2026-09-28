"""Customer analytics endpoints."""
from fastapi import APIRouter, Query
from db import query_records, query_df

router = APIRouter()


@router.get("/")
def list_customers(limit: int = Query(50, le=500)):
    return query_records("SELECT * FROM dim_customer LIMIT ?", (limit,))


@router.get("/by-segment")
def by_segment():
    df = query_df("""
        SELECT c.segment, COUNT(DISTINCT f.customer_key) AS customers,
               SUM(f.amount) AS revenue, COUNT(*) AS orders
        FROM fact_orders f JOIN dim_customer c ON f.customer_key = c.customer_key
        WHERE f.status = 'completed'
        GROUP BY c.segment ORDER BY revenue DESC
    """)
    return df.to_dict(orient="records")


@router.get("/by-city")
def by_city(limit: int = Query(15, le=100)):
    df = query_df("""
        SELECT c.city, COUNT(DISTINCT f.customer_key) AS customers, SUM(f.amount) AS revenue
        FROM fact_orders f JOIN dim_customer c ON f.customer_key = c.customer_key
        WHERE f.status = 'completed'
        GROUP BY c.city ORDER BY revenue DESC LIMIT ?
    """, (limit,))
    return df.to_dict(orient="records")
