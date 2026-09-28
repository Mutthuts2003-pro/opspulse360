"""Marketing analytics endpoints."""
from fastapi import APIRouter
from db import query_records, query_df

router = APIRouter()


@router.get("/by-channel")
def by_channel():
    df = query_df("""
        SELECT channel, SUM(spend) AS spend, SUM(impressions) AS impressions,
               SUM(clicks) AS clicks, SUM(conversions) AS conversions,
               100.0 * SUM(clicks) / NULLIF(SUM(impressions), 0) AS ctr_pct,
               100.0 * SUM(conversions) / NULLIF(SUM(clicks), 0) AS conversion_rate_pct,
               SUM(spend) / NULLIF(SUM(conversions), 0) AS cac
        FROM fact_marketing GROUP BY channel ORDER BY spend DESC
    """)
    return df.to_dict(orient="records")


@router.get("/daily")
def daily_marketing(limit: int = 90):
    df = query_df("""
        SELECT date_key, SUM(spend) AS spend, SUM(clicks) AS clicks, SUM(conversions) AS conversions
        FROM fact_marketing GROUP BY date_key ORDER BY date_key DESC LIMIT ?
    """, (limit,))
    return df.sort_values("date_key").to_dict(orient="records")
