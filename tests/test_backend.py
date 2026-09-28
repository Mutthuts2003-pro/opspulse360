"""
OpsPulse 360 - Backend API Test Suite
Exercises every FastAPI route via TestClient (in-process, no server
needed) against the already-built data/opspulse.db. Covers the
"Backend API Requirements" (dashboard KPIs, revenue, orders, inventory,
customers, delivery, alerts) plus auth and error handling.

Run:
    pytest tests/test_backend.py -v
"""
import os
import sys

import pytest

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


def test_health_check():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["database_present"] is True


@pytest.mark.parametrize("path", [
    "/api/dashboard/kpis",
    "/api/dashboard/summary",
    "/api/sales/revenue/daily",
    "/api/sales/revenue/by-category",
    "/api/sales/revenue/by-warehouse",
    "/api/sales/orders",
    "/api/inventory/status",
    "/api/inventory/at-risk",
    "/api/inventory/by-warehouse",
    "/api/customers/",
    "/api/customers/by-segment",
    "/api/customers/by-city",
    "/api/delivery/performance-by-partner",
    "/api/delivery/sla-trend",
    "/api/delivery/recent",
    "/api/marketing/by-channel",
    "/api/marketing/daily",
    "/api/alerts/",
    "/api/realtime/metrics",
    "/api/realtime/orders/recent",
    "/api/realtime/pipeline-status",
    "/api/intelligence/forecast",
    "/api/intelligence/anomalies",
    "/api/intelligence/anomalies/explanations",
    "/api/intelligence/anomalies/timeline",
])
def test_endpoint_returns_200_and_valid_json(path):
    r = client.get(path)
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert body is not None


def test_dashboard_kpis_cover_all_domains():
    r = client.get("/api/dashboard/kpis")
    domains = {row["domain"] for row in r.json()}
    for expected in ["sales", "customers", "inventory", "delivery", "marketing"]:
        assert expected in domains


def test_forecast_returns_seven_days():
    r = client.get("/api/intelligence/forecast")
    assert r.status_code == 200
    assert len(r.json()) == 7


def test_login_succeeds_for_both_roles():
    for username, password, role in [
        ("executive", "exec123", "executive"),
        ("ops", "ops123", "operations"),
    ]:
        r = client.post("/api/auth/login", json={"username": username, "password": password})
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == role
        assert "access_token" in body


def test_login_rejects_bad_password():
    r = client.post("/api/auth/login", json={"username": "executive", "password": "wrong"})
    assert r.status_code == 401


def test_authenticated_me_endpoint():
    login = client.post("/api/auth/login", json={"username": "executive", "password": "exec123"})
    token = login.json()["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "executive"


def test_me_endpoint_rejects_missing_token():
    r = client.get("/api/auth/me")
    assert r.status_code in (401, 403)


def test_alerts_have_required_fields():
    r = client.get("/api/alerts/")
    alerts = r.json()
    assert len(alerts) > 0
    for field in ["alert_id", "severity", "status"]:
        assert field in alerts[0]


def test_404_for_unknown_route():
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
