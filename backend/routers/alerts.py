"""Alert center endpoints (severity, status, acknowledge/resolve actions)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db import get_conn, query_records

router = APIRouter()


@router.get("/")
def list_alerts(status: str = None, severity: str = None):
    sql = "SELECT * FROM alerts WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if severity:
        sql += " AND severity = ?"
        params.append(severity)
    sql += " ORDER BY created_at DESC"
    try:
        return query_records(sql, tuple(params))
    except Exception:
        return []


class AlertUpdate(BaseModel):
    status: str  # ACKNOWLEDGED | RESOLVED


@router.patch("/{alert_id}")
def update_alert(alert_id: str, update: AlertUpdate):
    if update.status not in ("OPEN", "ACKNOWLEDGED", "RESOLVED"):
        raise HTTPException(400, "status must be OPEN, ACKNOWLEDGED or RESOLVED")
    conn = get_conn()
    cur = conn.execute("UPDATE alerts SET status = ? WHERE alert_id = ?", (update.status, alert_id))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "alert not found")
    conn.close()
    return {"alert_id": alert_id, "status": update.status}
