"""Executive/Operations dashboard KPI endpoints."""
from fastapi import APIRouter, HTTPException
from db import query_records, query_df

router = APIRouter()


@router.get("/kpis")
def all_kpis():
    """All KPI snapshot values across the 5 domains (sales, customers, inventory, delivery, marketing)."""
    try:
        return query_records("SELECT * FROM kpi_snapshot ORDER BY domain, metric")
    except Exception:
        raise HTTPException(503, "kpi_snapshot not found - run analytics/kpi_engine.py first")


@router.get("/kpis/{domain}")
def kpis_by_domain(domain: str):
    df = query_df("SELECT * FROM kpi_snapshot WHERE domain = ? ORDER BY metric", (domain,))
    if df.empty:
        raise HTTPException(404, f"No KPIs found for domain '{domain}'")
    return df.to_dict(orient="records")


@router.get("/summary")
def executive_summary():
    """A compact top-line summary for the executive dashboard landing page."""
    df = query_df("SELECT * FROM kpi_snapshot")
    if df.empty:
        raise HTTPException(503, "kpi_snapshot not found - run analytics/kpi_engine.py first")
    def g(metric):
        row = df[df["metric"] == metric]
        return float(row["value"].iloc[0]) if not row.empty and row["value"].iloc[0] is not None else None
    return {
        "total_revenue": g("total_revenue"),
        "total_orders": g("total_orders"),
        "average_order_value": g("average_order_value"),
        "on_time_delivery_pct": g("on_time_delivery_pct"),
        "stockout_risk_item_count": g("stockout_risk_item_count"),
        "estimated_roas": g("estimated_roas"),
        "total_customers": g("total_customers"),
        "repeat_customer_rate_pct": g("repeat_customer_rate_pct"),
    }
