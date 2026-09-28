"""
OpsPulse 360 - Live Event Generator
Continuously publishes simulated order, payment, delivery, and inventory
events to the (simulated) Kafka broker. This plays the role of the
"Event Generator" box in the required flow:

    Event Generator -> Kafka Topic -> Stream Processor -> Analytical Store -> API -> Live Dashboard

Run forever (Ctrl+C to stop):
    python event_generator.py --interval 0.5

Run a fixed number of ticks (used by CI / demo scripts):
    python event_generator.py --ticks 200 --interval 0
"""
import argparse
import csv
import os
import random
import time
import uuid
from datetime import datetime, timezone

from kafka_sim import KafkaSim

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load_ids(filename, col):
    path = os.path.join(DATA_DIR, filename)
    ids = []
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ids.append(row[col])
    return ids or [f"{col.upper()}_FALLBACK_1"]


def make_order_event(customer_ids, product_ids, warehouse_ids):
    qty = random.randint(1, 4)
    price = round(random.uniform(50, 6000), 2)
    return {
        "event_type": "order_created",
        "order_id": f"OL{uuid.uuid4().hex[:10]}",
        "customer_id": random.choice(customer_ids),
        "product_id": random.choice(product_ids),
        "warehouse_id": random.choice(warehouse_ids),
        "quantity": qty,
        "amount": round(price * qty, 2),
        "status": "completed" if random.random() > 0.06 else "cancelled",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def make_payment_event(order_event):
    return {
        "event_type": "payment_processed",
        "order_id": order_event["order_id"],
        "amount": order_event["amount"],
        "result": "success" if random.random() > 0.04 else "failed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def make_delivery_event(order_event, partners):
    sla_breach = random.random() < 0.12
    return {
        "event_type": "delivery_update",
        "order_id": order_event["order_id"],
        "partner": random.choice(partners),
        "status": random.choice(["picked_up", "in_transit", "delivered", "delayed"]),
        "sla_breach": sla_breach,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def make_inventory_event(warehouse_ids, product_ids):
    return {
        "event_type": "inventory_adjustment",
        "warehouse_id": random.choice(warehouse_ids),
        "product_id": random.choice(product_ids),
        "delta_qty": random.randint(-15, 5),  # mostly depletion from sales
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run(interval: float, ticks: int):
    bus = KafkaSim()
    customer_ids = _load_ids("customers.csv", "customer_id")
    product_ids = _load_ids("products.csv", "product_id")
    warehouse_ids = [f"WH{str(i).zfill(2)}" for i in range(1, 7)]
    partners = ["Shadowfax", "Delhivery", "Ekart", "BlueDart", "Xpressbees"]

    count = 0
    print(f"[event_generator] publishing to topics: orders.events, payments.events, "
          f"delivery.events, inventory.events")
    while ticks == 0 or count < ticks:
        order_evt = make_order_event(customer_ids, product_ids, warehouse_ids)
        o_off = bus.produce("orders.events", order_evt, key=order_evt["order_id"])

        pay_evt = make_payment_event(order_evt)
        bus.produce("payments.events", pay_evt, key=pay_evt["order_id"])

        if random.random() < 0.7:
            del_evt = make_delivery_event(order_evt, partners)
            bus.produce("delivery.events", del_evt, key=del_evt["order_id"])

        if random.random() < 0.5:
            inv_evt = make_inventory_event(warehouse_ids, product_ids)
            bus.produce("inventory.events", inv_evt, key=inv_evt["warehouse_id"] + inv_evt["product_id"])

        count += 1
        if count % 25 == 0:
            print(f"[event_generator] published {count} order-cycles "
                  f"(orders.events offset={o_off})")
        if interval > 0:
            time.sleep(interval)

    print(f"[event_generator] done. total order-cycles published: {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=0.5, help="seconds between ticks (0 = as fast as possible)")
    parser.add_argument("--ticks", type=int, default=0, help="number of ticks to run, 0 = run forever")
    args = parser.parse_args()
    run(args.interval, args.ticks)
