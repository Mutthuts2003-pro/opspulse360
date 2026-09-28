# OpsPulse 360 — Data Dictionary

Covers every table produced by the pipeline, grouped by layer. Column
types are as materialized in `data/opspulse.db` (SQLite / DuckDB
equivalents are the same logical types).

## Source (raw CSVs, `data/*.csv`)

| Dataset | Key fields |
|---|---|
| `orders.csv` | order_id, customer_id, product_id, warehouse_id, timestamp, quantity, amount, status |
| `customers.csv` | customer_id, city, state, segment, registration_date |
| `products.csv` | product_id, category, brand, cost, selling_price, supplier_id |
| `inventory.csv` | warehouse_id, product_id, available_qty, reserved_qty, reorder_level, updated_at |
| `delivery.csv` | order_id, partner, pickup_time, expected_delivery, actual_delivery, status |
| `support.csv` | ticket_id, customer_id, order_id, issue_type, priority, created_at, resolved_at |
| `marketing.csv` | campaign_id, date, channel, spend, impressions, clicks, conversions |

## Bronze layer (`bronze_*`)

Exact copy of the source CSV columns, plus:
| Column | Type | Description |
|---|---|---|
| `_ingested_at` | timestamp (ISO 8601, UTC) | When `load_bronze.py` loaded this row |
| `_source_file` | string | Originating CSV filename |

## Silver layer (`silver_*`)

Same business columns as bronze, after: null/duplicate removal on
primary keys, referential-integrity filtering (orders must reference
valid customer/product), type casting (dates/timestamps cast, numeric
sanity checks), and negative-value rejection. See `dq_report` below
for exact counts per rule per run.

| Table | Notable transformations vs. bronze |
|---|---|
| `silver_orders` | dedup on `order_id`; drops rows with unknown `customer_id`/`product_id`; drops negative `amount`; drops unparseable `timestamp` |
| `silver_customers` | dedup on `customer_id` |
| `silver_products` | dedup on `product_id`; drops `selling_price <= 0` |
| `silver_inventory` | dedup on (`warehouse_id`,`product_id`), keep latest; drops negative quantities |
| `silver_delivery` | dedup on `order_id`, keep latest |
| `silver_support` | dedup on `ticket_id` |
| `silver_marketing` | dedup on (`campaign_id`,`date`,`channel`) |

## Gold layer — star schema (`dim_*`, `fact_*`)

See `docs/erd.md` for the full entity-relationship diagram and column
list. Summary:

| Table | Type | Grain |
|---|---|---|
| `dim_customer` | dimension | one row per customer |
| `dim_product` | dimension | one row per product |
| `dim_warehouse` | dimension | one row per warehouse |
| `dim_date` | dimension | one row per calendar day |
| `fact_orders` | fact | one row per order line |
| `fact_inventory` | fact | one row per warehouse/product snapshot |
| `fact_delivery` | fact | one row per order's delivery record |
| `fact_marketing` | fact | one row per campaign per day |

## Live / streaming tables (`live_*`, populated by `streaming/stream_processor.py`)

| Table | Description |
|---|---|
| `live_metrics` | key-value running totals: `live_revenue_total`, `live_orders_total`, `live_payments_total`, `live_payment_failures_total`, `live_delivery_events_total`, `live_sla_breaches_total` |
| `live_order_stream` | raw order-created events as they arrive |
| `live_payment_stream` | raw payment-processed events |
| `live_delivery_stream` | raw delivery-update events |
| `live_inventory_stream` | raw inventory-adjustment events |

## Analytics & intelligence output tables

| Table | Produced by | Description |
|---|---|---|
| `kpi_snapshot` | `analytics/kpi_engine.py` | long-format KPI values: `domain`, `metric`, `value`, `dims`, `computed_at` — covers sales, customers, inventory, delivery, marketing |
| `anomaly_report` | `ml/anomaly_detection.py` | daily revenue panel with `revenue_zscore`, `is_anomaly_statistical`, `iforest_score`, `is_anomaly_iforest` |
| `anomaly_explanations` | `ml/anomaly_detection.py` | up to 3 explained anomalies per run: `day`, `revenue`, `baseline_avg_revenue`, `explanation`, `recommended_action` |
| `revenue_forecast` | `ml/forecasting.py` | 7-day forward forecast: `forecast_day`, `predicted_revenue`, `lower_bound_80pct`, `upper_bound_80pct` |
| `dq_report` | `warehouse/silver/build_silver.py` | data-quality check log: `table_name`, `rule`, `failed_rows`, `checked_at` |
| `alerts` | `automation/rules_engine.py` | triggered business-rule alerts: `alert_id`, `rule`, `severity`, `status`, `entity`, `message` |

## dbt project tables (parallel DuckDB warehouse, `data/opspulse_dbt.duckdb`)

Same logical model as the Gold layer above, built via
`dbt_project/models/{staging,intermediate,marts}/`. Staging models are
materialized as views (`stg_orders`, `stg_customers`, ...), marts as
tables (`dim_customer`, `fact_orders`, ...). See `dbt_project/models/`
for the SQL and `models/marts/_marts.yml` for column-level tests.
