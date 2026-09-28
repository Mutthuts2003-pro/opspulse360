"""Forecasting + anomaly detection endpoints."""
from fastapi import APIRouter
from db import query_records

router = APIRouter()


@router.get("/forecast")
def revenue_forecast():
    return query_records("SELECT * FROM revenue_forecast ORDER BY forecast_day")


@router.get("/anomalies")
def anomalies(limit: int = 60):
    return query_records(
        "SELECT * FROM anomaly_report WHERE is_anomaly = 1 ORDER BY day DESC LIMIT ?", (limit,)
    )


@router.get("/anomalies/explanations")
def anomaly_explanations():
    return query_records("SELECT * FROM anomaly_explanations")


@router.get("/anomalies/timeline")
def anomaly_timeline(limit: int = 120):
    return query_records("SELECT * FROM anomaly_report ORDER BY day DESC LIMIT ?", (limit,))
