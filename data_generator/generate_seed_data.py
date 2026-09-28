"""
OpsPulse 360 - Synthetic Source Data Generator
Generates the 7 mandatory datasets (Orders, Customers, Products, Inventory,
Delivery, Support, Marketing) as CSV files simulating the "Source" layer
(transactional DB + files) described in the architecture.

Run:
    python generate_seed_data.py --out ../data --scale 1.0
"""
import argparse
import csv
import os
import random
import uuid
from datetime import datetime, timedelta

random.seed(42)

CITIES = [
    ("Bengaluru", "Karnataka"), ("Mumbai", "Maharashtra"), ("Delhi", "Delhi"),
    ("Hyderabad", "Telangana"), ("Chennai", "Tamil Nadu"), ("Pune", "Maharashtra"),
    ("Kolkata", "West Bengal"), ("Ahmedabad", "Gujarat"), ("Jaipur", "Rajasthan"),
    ("Lucknow", "Uttar Pradesh"),
]
SEGMENTS = ["Consumer", "SMB", "Enterprise"]
CATEGORIES = ["Electronics", "Apparel", "Home & Kitchen", "Beauty", "Grocery", "Sports", "Books"]
BRANDS = ["Aurora", "Nimbus", "Vertex", "Solace", "Pinnacle", "Northline", "Cobalt"]
WAREHOUSES = [f"WH{str(i).zfill(2)}" for i in range(1, 7)]
DELIVERY_PARTNERS = ["Shadowfax", "Delhivery", "Ekart", "BlueDart", "Xpressbees"]
ORDER_STATUSES = ["completed", "completed", "completed", "cancelled", "returned", "pending"]
ISSUE_TYPES = ["damaged_item", "wrong_item", "late_delivery", "payment_issue", "refund_request", "product_query"]
PRIORITIES = ["low", "medium", "high", "urgent"]
CHANNELS = ["google_ads", "meta_ads", "email", "affiliate", "organic_social", "influencer"]

START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2026, 9, 26)


def rand_date(start=START_DATE, end=END_DATE):
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def gen_customers(n, out_dir):
    rows = []
    for i in range(1, n + 1):
        city, state = random.choice(CITIES)
        rows.append({
            "customer_id": f"C{str(i).zfill(6)}",
            "city": city,
            "state": state,
            "segment": random.choice(SEGMENTS),
            "registration_date": rand_date(START_DATE, END_DATE - timedelta(days=1)).strftime("%Y-%m-%d"),
        })
    _write_csv(out_dir, "customers.csv", rows)
    return [r["customer_id"] for r in rows]


def gen_products(n, out_dir):
    rows = []
    for i in range(1, n + 1):
        cost = round(random.uniform(50, 5000), 2)
        margin_pct = random.uniform(0.15, 0.55)
        rows.append({
            "product_id": f"P{str(i).zfill(5)}",
            "category": random.choice(CATEGORIES),
            "brand": random.choice(BRANDS),
            "cost": cost,
            "selling_price": round(cost * (1 + margin_pct), 2),
            "supplier_id": f"S{str(random.randint(1, 40)).zfill(3)}",
        })
    _write_csv(out_dir, "products.csv", rows)
    return [r["product_id"] for r in rows]


def gen_orders(n, customer_ids, product_ids, out_dir):
    rows = []
    order_ids = []
    for i in range(1, n + 1):
        oid = f"O{str(i).zfill(7)}"
        order_ids.append(oid)
        qty = random.randint(1, 5)
        price_lookup = round(random.uniform(50, 6000), 2)
        rows.append({
            "order_id": oid,
            "customer_id": random.choice(customer_ids),
            "product_id": random.choice(product_ids),
            "warehouse_id": random.choice(WAREHOUSES),
            "timestamp": rand_date().strftime("%Y-%m-%d %H:%M:%S"),
            "quantity": qty,
            "amount": round(price_lookup * qty, 2),
            "status": random.choice(ORDER_STATUSES),
        })
    _write_csv(out_dir, "orders.csv", rows)
    return order_ids


def gen_inventory(product_ids, out_dir):
    rows = []
    for wh in WAREHOUSES:
        for pid in product_ids:
            if random.random() < 0.6:  # not every product in every warehouse
                continue
            reorder_level = random.randint(20, 100)
            available = random.randint(0, 400)
            rows.append({
                "warehouse_id": wh,
                "product_id": pid,
                "available_qty": available,
                "reserved_qty": random.randint(0, min(50, available)),
                "reorder_level": reorder_level,
                "updated_at": rand_date(END_DATE - timedelta(days=3), END_DATE).strftime("%Y-%m-%d %H:%M:%S"),
            })
    _write_csv(out_dir, "inventory.csv", rows)


def gen_delivery(order_ids, out_dir):
    rows = []
    for oid in order_ids:
        if random.random() < 0.1:
            continue  # some orders have no delivery record yet (pending/cancelled)
        pickup = rand_date()
        expected = pickup + timedelta(days=random.randint(1, 5))
        sla_hit = random.random() < 0.82
        actual = expected + (timedelta(hours=random.randint(-12, 6)) if sla_hit
                              else timedelta(hours=random.randint(7, 72)))
        rows.append({
            "order_id": oid,
            "partner": random.choice(DELIVERY_PARTNERS),
            "pickup_time": pickup.strftime("%Y-%m-%d %H:%M:%S"),
            "expected_delivery": expected.strftime("%Y-%m-%d %H:%M:%S"),
            "actual_delivery": actual.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "delivered" if random.random() < 0.93 else "in_transit",
        })
    _write_csv(out_dir, "delivery.csv", rows)


def gen_support(customer_ids, order_ids, out_dir):
    rows = []
    n = int(len(order_ids) * 0.12)
    for i in range(1, n + 1):
        created = rand_date()
        resolved = created + timedelta(hours=random.randint(1, 120)) if random.random() < 0.85 else None
        rows.append({
            "ticket_id": f"T{str(i).zfill(6)}",
            "customer_id": random.choice(customer_ids),
            "order_id": random.choice(order_ids),
            "issue_type": random.choice(ISSUE_TYPES),
            "priority": random.choice(PRIORITIES),
            "created_at": created.strftime("%Y-%m-%d %H:%M:%S"),
            "resolved_at": resolved.strftime("%Y-%m-%d %H:%M:%S") if resolved else "",
        })
    _write_csv(out_dir, "support.csv", rows)


def gen_marketing(out_dir):
    rows = []
    d = START_DATE
    while d <= END_DATE:
        for ch in CHANNELS:
            impressions = random.randint(2000, 60000)
            clicks = int(impressions * random.uniform(0.01, 0.08))
            conversions = int(clicks * random.uniform(0.01, 0.12))
            spend = round(clicks * random.uniform(3, 25), 2)
            rows.append({
                "campaign_id": f"CMP_{ch}_{d.strftime('%Y%m')}",
                "date": d.strftime("%Y-%m-%d"),
                "channel": ch,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions,
            })
        d += timedelta(days=1)
    _write_csv(out_dir, "marketing.csv", rows)


def _write_csv(out_dir, filename, rows):
    if not rows:
        return
    path = os.path.join(out_dir, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {len(rows):>7,} rows -> {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="../data")
    parser.add_argument("--scale", type=float, default=1.0, help="scale factor for row counts")
    args = parser.parse_args()
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), args.out))
    os.makedirs(out_dir, exist_ok=True)

    n_customers = int(3000 * args.scale)
    n_products = int(600 * args.scale)
    n_orders = int(20000 * args.scale)

    print(f"Generating OpsPulse 360 seed data into {out_dir} (scale={args.scale}) ...")
    customer_ids = gen_customers(n_customers, out_dir)
    product_ids = gen_products(n_products, out_dir)
    order_ids = gen_orders(n_orders, customer_ids, product_ids, out_dir)
    gen_inventory(product_ids, out_dir)
    gen_delivery(order_ids, out_dir)
    gen_support(customer_ids, order_ids, out_dir)
    gen_marketing(out_dir)
    print("Done.")


if __name__ == "__main__":
    main()
