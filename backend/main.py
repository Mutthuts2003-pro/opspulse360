"""
OpsPulse 360 - FastAPI Backend
Entry point. Registers routers for dashboard KPIs, revenue, orders,
inventory, customers, delivery, marketing, alerts, real-time metrics,
forecasting/anomalies, and auth. Run:

    uvicorn main:app --reload --port 8000

Docs auto-generated at /docs (Swagger) and /redoc.
"""
import os
import sqlite3
from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import dashboard, sales, inventory, customers, delivery, marketing, alerts, realtime, intelligence, auth

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DATA_DIR, "opspulse.db")

app = FastAPI(
    title="OpsPulse 360 API",
    description="Backend API for the OpsPulse 360 enterprise analytics platform.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(sqlite3.OperationalError)
async def db_not_ready_handler(request, exc):
    return JSONResponse(
        status_code=503,
        content={
            "error": "warehouse_not_built",
            "detail": "A required table is missing. Run warehouse/build_warehouse.py, "
                      "analytics/kpi_engine.py, ml/anomaly_detection.py, ml/forecasting.py "
                      "and automation/rules_engine.py first.",
            "message": str(exc),
        },
    )


@app.get("/", tags=["health"])
def root():
    return {"service": "OpsPulse 360 API", "status": "ok", "docs": "/docs"}


@app.get("/health", tags=["health"])
def health():
    ok = os.path.exists(DB_PATH)
    return {"database_present": ok, "path": DB_PATH}


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(sales.router, prefix="/api/sales", tags=["sales"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["inventory"])
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(delivery.router, prefix="/api/delivery", tags=["delivery"])
app.include_router(marketing.router, prefix="/api/marketing", tags=["marketing"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(realtime.router, prefix="/api/realtime", tags=["realtime"])
app.include_router(intelligence.router, prefix="/api/intelligence", tags=["intelligence"])
