"""
OpsPulse 360 - Simulated Kafka Broker
--------------------------------------
A minimal message-broker substitute for Apache Kafka, used because this
environment cannot run a real Kafka/Zookeeper cluster. It reproduces the
concepts that matter for the assignment:

  - Named topics with an append-only, offset-ordered log (durable: backed
    by SQLite, not just an in-memory list, so events survive a restart --
    same durability guarantee Kafka gives you).
  - Multiple producers can publish to a topic concurrently (thread-safe).
  - Multiple consumer groups can each read the topic independently and
    track their own committed offset (mirrors Kafka consumer groups).
  - At-least-once delivery semantics: a consumer only advances its offset
    after successfully processing a batch.

NOTE FOR THE README / INTERVIEW: in production this class would be
swapped for `kafka-python` / `confluent-kafka` talking to a real broker.
The producer/consumer *interface* below (`produce`, `poll`) is written to
mirror the real Kafka client API on purpose, so swapping in a real broker
later only means changing this one module, not any downstream code.
"""
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "kafka_sim.db")


class KafkaSim:
    _lock = threading.Lock()

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS topic_log (
                    topic TEXT NOT NULL,
                    offset INTEGER NOT NULL,
                    key TEXT,
                    payload TEXT NOT NULL,
                    produced_at TEXT NOT NULL,
                    PRIMARY KEY (topic, offset)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS consumer_offsets (
                    consumer_group TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    committed_offset INTEGER NOT NULL,
                    PRIMARY KEY (consumer_group, topic)
                )
            """)
            conn.commit()

    # ---------------- Producer API ----------------
    def produce(self, topic: str, value: dict, key: str = None):
        payload = json.dumps(value, default=str)
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                "SELECT COALESCE(MAX(offset), -1) + 1 FROM topic_log WHERE topic = ?", (topic,)
            )
            next_offset = cur.fetchone()[0]
            conn.execute(
                "INSERT INTO topic_log (topic, offset, key, payload, produced_at) VALUES (?, ?, ?, ?, ?)",
                (topic, next_offset, key, payload, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        return next_offset

    # ---------------- Consumer API ----------------
    def poll(self, topic: str, consumer_group: str, max_records: int = 100):
        """Fetch new records for a consumer group since its last committed offset."""
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT committed_offset FROM consumer_offsets WHERE consumer_group=? AND topic=?",
                (consumer_group, topic),
            )
            row = cur.fetchone()
            start_offset = (row[0] + 1) if row else 0
            cur = conn.execute(
                "SELECT offset, key, payload, produced_at FROM topic_log "
                "WHERE topic=? AND offset >= ? ORDER BY offset ASC LIMIT ?",
                (topic, start_offset, max_records),
            )
            records = [
                {"offset": r[0], "key": r[1], "value": json.loads(r[2]), "produced_at": r[3]}
                for r in cur.fetchall()
            ]
        return records

    def commit(self, topic: str, consumer_group: str, offset: int):
        with self._lock, self._conn() as conn:
            conn.execute(
                """INSERT INTO consumer_offsets (consumer_group, topic, committed_offset)
                   VALUES (?, ?, ?)
                   ON CONFLICT(consumer_group, topic)
                   DO UPDATE SET committed_offset = excluded.committed_offset""",
                (consumer_group, topic, offset),
            )
            conn.commit()

    def topic_size(self, topic: str) -> int:
        with self._conn() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM topic_log WHERE topic=?", (topic,))
            return cur.fetchone()[0]

    def lag(self, topic: str, consumer_group: str) -> int:
        size = self.topic_size(topic)
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT committed_offset FROM consumer_offsets WHERE consumer_group=? AND topic=?",
                (consumer_group, topic),
            )
            row = cur.fetchone()
            committed = (row[0] + 1) if row else 0
        return max(0, size - committed)


if __name__ == "__main__":
    # smoke test
    bus = KafkaSim()
    off = bus.produce("orders.events", {"order_id": "O0000001", "amount": 999.0}, key="O0000001")
    print("produced at offset", off)
    recs = bus.poll("orders.events", consumer_group="stream-processor")
    print("polled", len(recs), "records")
    if recs:
        bus.commit("orders.events", "stream-processor", recs[-1]["offset"])
    print("lag after commit:", bus.lag("orders.events", "stream-processor"))
