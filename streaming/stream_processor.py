"""
OpsPulse 360 - Stream Processor
Consumes events from the (simulated) Kafka topics and maintains a
continuously-updated set of "live" aggregate tables in SQLite
(data/opspulse.db, table prefix live_*). This is the component the
FastAPI real-time endpoints read from, and is the "Stream Processor"
+ "Analytical Store" steps in the required flow.

In a real deployment this module's logic (windowed aggregation, running
totals) is exactly what you'd port into a PySpark Structured Streaming
or Flink job reading from the real Kafka topics.

Run:
    python stream_processor.py --batch-size 50 --loop-forever
    python stream_processor.py --once     # process whatever is available and exit
"""
import argparse
import os
import sqlite3
import time
from datetime import datetime, timezone

from kafka_sim import KafkaSim

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "opspulse.db")
CONSUMER_GROUP = "stream-processor-v1"
TOPICS = ["orders.events", "payments.events", "delivery.events", "inventory.events"]


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_live_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS live_metrics (
        metric_key TEXT PRIMARY KEY,
        metric_value REAL,
        updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS live_order_stream (
        order_id TEXT,
        customer_id TEXT,
        product_id TEXT,
        warehouse_id TEXT,
        quantity INTEGER,
        amount REAL,
        status TEXT,
        event_ts TEXT
    );
    CREATE TABLE IF NOT EXISTS live_payment_stream (
        order_id TEXT, amount REAL, result TEXT, event_ts TEXT
    );
    CREATE TABLE IF NOT EXISTS live_delivery_stream (
        order_id TEXT, partner TEXT, status TEXT, sla_breach INTEGER, event_ts TEXT
    );
    CREATE TABLE IF NOT EXISTS live_inventory_stream (
        warehouse_id TEXT, product_id TEXT, delta_qty INTEGER, event_ts TEXT
    );
    """)
    conn.commit()


def _bump(conn, key, delta=None, set_value=None):
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute("SELECT metric_value FROM live_metrics WHERE metric_key=?", (key,))
    row = cur.fetchone()
    if set_value is not None:
        new_val = set_value
    else:
        new_val = (row[0] if row else 0) + (delta or 0)
    conn.execute(
        """INSERT INTO live_metrics (metric_key, metric_value, updated_at) VALUES (?, ?, ?)
           ON CONFLICT(metric_key) DO UPDATE SET metric_value=excluded.metric_value, updated_at=excluded.updated_at""",
        (key, new_val, now),
    )


def process_batch(bus: KafkaSim, conn, batch_size=100):
    total_processed = 0
    for topic in TOPICS:
        records = bus.poll(topic, CONSUMER_GROUP, max_records=batch_size)
        if not records:
            continue
        for rec in records:
            v = rec["value"]
            et = v.get("event_type")
            if et == "order_created":
                conn.execute(
                    "INSERT INTO live_order_stream VALUES (?,?,?,?,?,?,?,?)",
                    (v["order_id"], v["customer_id"], v["product_id"], v["warehouse_id"],
                     v["quantity"], v["amount"], v["status"], v["timestamp"]),
                )
                if v["status"] == "completed":
                    _bump(conn, "live_revenue_total", delta=v["amount"])
                    _bump(conn, "live_orders_total", delta=1)
            elif et == "payment_processed":
                conn.execute(
                    "INSERT INTO live_payment_stream VALUES (?,?,?,?)",
                    (v["order_id"], v["amount"], v["result"], v["timestamp"]),
                )
                if v["result"] == "failed":
                    _bump(conn, "live_payment_failures_total", delta=1)
                _bump(conn, "live_payments_total", delta=1)
            elif et == "delivery_update":
                conn.execute(
                    "INSERT INTO live_delivery_stream VALUES (?,?,?,?,?)",
                    (v["order_id"], v["partner"], v["status"], int(v["sla_breach"]), v["timestamp"]),
                )
                _bump(conn, "live_delivery_events_total", delta=1)
                if v["sla_breach"]:
                    _bump(conn, "live_sla_breaches_total", delta=1)
            elif et == "inventory_adjustment":
                conn.execute(
                    "INSERT INTO live_inventory_stream VALUES (?,?,?,?)",
                    (v["warehouse_id"], v["product_id"], v["delta_qty"], v["timestamp"]),
                )
            total_processed += 1
        bus.commit(topic, CONSUMER_GROUP, records[-1]["offset"])
    conn.commit()
    return total_processed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--loop-forever", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    args = parser.parse_args()

    bus = KafkaSim()
    conn = get_conn()
    init_live_tables(conn)

    if args.once or not args.loop_forever:
        n = process_batch(bus, conn, args.batch_size)
        print(f"[stream_processor] processed {n} events (single pass)")
        return

    print("[stream_processor] running continuously, Ctrl+C to stop...")
    try:
        while True:
            n = process_batch(bus, conn, args.batch_size)
            if n:
                print(f"[stream_processor] processed {n} events")
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("[stream_processor] stopped.")


if __name__ == "__main__":
    main()
