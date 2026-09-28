"""Real-time monitoring endpoints - reads the live_* tables populated by the stream processor."""
from fastapi import APIRouter
from db import query_records, query_df

router = APIRouter()


@router.get("/metrics")
def live_metrics():
    return query_records("SELECT * FROM live_metrics")


@router.get("/orders/recent")
def recent_live_orders(limit: int = 25):
    return query_records(
        "SELECT * FROM live_order_stream ORDER BY event_ts DESC LIMIT ?", (limit,)
    )


@router.get("/pipeline-status")
def pipeline_status():
    """Backs the Data-quality / pipeline-monitoring page."""
    dq = query_records("SELECT * FROM dq_report ORDER BY checked_at DESC") if True else []
    return {"data_quality_checks": dq}
