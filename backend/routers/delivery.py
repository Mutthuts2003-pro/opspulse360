"""Delivery analytics endpoints."""
from fastapi import APIRouter
from db import query_records, query_df

router = APIRouter()


@router.get("/performance-by-partner")
def performance_by_partner():
    df = query_df("""
        SELECT partner, COUNT(*) AS deliveries,
               AVG(delivery_hours) AS avg_delivery_hours,
               100.0 * SUM(CASE WHEN sla_breached = 1 THEN 1 ELSE 0 END) / COUNT(*) AS sla_breach_pct
        FROM fact_delivery GROUP BY partner ORDER BY sla_breach_pct ASC
    """)
    return df.to_dict(orient="records")


@router.get("/sla-trend")
def sla_trend():
    df = query_df("""
        SELECT date(pickup_time) AS day,
               100.0 * SUM(CASE WHEN sla_breached = 1 THEN 1 ELSE 0 END) / COUNT(*) AS sla_breach_pct,
               COUNT(*) AS deliveries
        FROM fact_delivery GROUP BY day ORDER BY day
    """)
    return df.to_dict(orient="records")


@router.get("/recent")
def recent_deliveries(limit: int = 50):
    return query_records("SELECT * FROM fact_delivery ORDER BY pickup_time DESC LIMIT ?", (limit,))
