# OpsPulse 360 — Mandatory Interview Questions (Answered)

### Why did you choose a star schema?
See `docs/erd.md` — in short: analytical (read-heavy) workload,
single-hop joins for BI queries, conformed dimensions shared across
order/inventory/delivery/marketing facts, and it's what dbt and most
BI tools are optimized for.

### How would you handle duplicate streaming events?
Two layers of defense: (1) the simulated broker commits consumer
offsets only after a batch is fully processed (at-least-once, not
exactly-once, delivery — mirroring real Kafka's default), so a crash
mid-batch can redeliver events; (2) downstream, `warehouse/silver/build_silver.py`
deduplicates on natural/business keys (`order_id`, `ticket_id`, etc.)
using "keep latest by timestamp" logic, so a duplicate event is
absorbed at the Silver layer even if it was double-processed upstream.
In a real Kafka deployment this would additionally use idempotent
producers (`enable.idempotence=true`) and a dedup key in the consumer
(e.g. Flink's exactly-once sinks, or a staging table with `MERGE`/upsert
semantics keyed on event id).

### What happens if Kafka is unavailable?
Producers (`event_generator.py`) would fail to publish and should
buffer/retry locally or fail fast with alerting rather than silently
drop events — in production this means enabling producer retries with
backoff and monitoring producer error rates. Consumers
(`stream_processor.py`) simply stop receiving new records; because
offsets are only committed after successful processing, no data is
lost — processing resumes from the last committed offset once the
broker recovers. The batch pipeline (Bronze/Silver/Gold, computed
hourly via Airflow) is independent of the streaming path, so KPIs,
alerts and the dashboard's non-realtime pages keep working off the
last successful batch even during a Kafka outage — only the
"Real-Time Monitoring" page would show stale data.

### How would you process 10 million events per day?
That's ~115 events/sec average (likely much higher at peak) — well
within a single Kafka partition's throughput, but the current
single-threaded `stream_processor.py` (SQLite-backed) would not scale.
Changes needed: (1) partition Kafka topics by a high-cardinality key
(e.g. `warehouse_id` or `customer_id` hash) so consumers can scale
horizontally per partition; (2) replace the single-process consumer
with a real stream-processing framework (Spark Structured Streaming or
Flink) running multiple parallel tasks; (3) replace SQLite with a
warehouse that supports concurrent writes at scale (BigQuery streaming
inserts, or a staging Kafka-to-GCS sink with periodic batch load);
(4) move live aggregates to a system built for high-write-throughput
key-value updates (e.g. Bigtable or Redis) rather than a relational
live_metrics table.

### How would you handle schema evolution?
Producers should version event schemas explicitly (e.g. an
`event_schema_version` field, as is implicit here via `event_type`)
and use a schema registry (Confluent Schema Registry / AWS Glue Schema
Registry) with backward-compatible evolution rules (new fields
optional with defaults, no field removal/type changes without a major
version bump). Downstream, dbt's `source()` freshness checks and
explicit column casts in staging models (`stg_orders.sql` etc.) act as
a contract boundary — a source column rename/type change fails loudly
in a staging model's `cast()` rather than silently corrupting a fact
table.

### How would you optimize warehouse/cloud cost?
See `docs/cloud_architecture_cost.md` for the full breakdown. Headline
points: replace a managed Airflow environment with
Scheduler+Functions for small DAGs (biggest single lever), partition
`fact_orders` by date and cluster by `warehouse_id`/`product_id` to
cut bytes-scanned per query, scale Cloud Run to zero when idle, and
apply storage lifecycle rules to age out raw Bronze data to cold
storage.

### How did you validate the accuracy of your KPIs?
Three layers: (1) `tests/test_pipeline.py` checks referential integrity
between facts and dimensions (no orphaned `customer_key`/`product_key`),
non-negative amounts, and uniqueness of dimension primary keys, so KPIs
aren't built on structurally broken data; (2) `dbt_project/models/marts/_marts.yml`
runs 20 dbt tests (`unique`, `not_null`, `relationships`) directly
against the mart tables on every `dbt build`; (3) `tests/test_pipeline.py`
also spot-checks specific KPI values (e.g. `total_revenue > 0`,
all 5 domains present in `kpi_snapshot`) so a KPI-computation bug that
produces an empty or nonsensical result is caught in CI, not in the
dashboard.

### How do you prevent bad data from reaching the analytical layer?
The Silver layer is a hard gate: `build_silver.py` drops (not just
flags) rows that fail null-key checks, duplicate-key checks,
referential-integrity checks, and negative-value checks *before*
anything reaches Gold — bad rows never propagate downstream. Every
rejection is logged with a reason to `dq_report`, which is itself
surfaced on the frontend's "Data Quality / Pipeline" page, so silent
data loss is visible rather than hidden. dbt's `not_null`/`unique`/
`relationships` tests on the mart layer act as a second, independent
gate closer to the BI/serving layer.

### Why did you choose your anomaly-detection method?
Both a statistical method (rolling z-score) and an ML method
(Isolation Forest) were implemented, as required, because they catch
different failure modes: z-score is simple, explainable, and good at
flagging a single metric (revenue) moving sharply outside its recent
trend — but it's univariate and can miss anomalies that only show up
across a *combination* of metrics. Isolation Forest is multivariate
(fed revenue, order count, AOV, SLA breach rate together) and catches
subtler joint anomalies — e.g. revenue looks normal but margin and SLA
breaches both moved together — that a single-metric z-score would
miss. Isolation Forest was chosen over, say, a simple clustering
approach because it doesn't require assuming a cluster shape/count and
handles the modest feature count here efficiently without heavy tuning.

### How would you monitor this application in production?
- **Pipeline health**: Airflow's own UI/alerting for DAG task
  failures/retries/SLA misses (email_on_failure is already configured
  in the DAG's default_args).
- **Data quality**: alert when `dq_report`'s failed-row counts spike
  relative to their historical baseline (not just log them).
- **API**: standard uptime/latency monitoring on the Cloud Run service
  (Cloud Monitoring / Datadog), plus the `/health` endpoint already
  exposed here as a load-balancer health check target.
- **Streaming lag**: monitor consumer lag (`KafkaSim.lag()` /
  Kafka's own consumer-group lag metrics) so a stalled stream
  processor is caught before the Real-Time page goes stale.
- **Model drift**: periodically re-evaluate the Isolation Forest's
  anomaly rate and the forecast's realized error (MAPE) against actuals;
  a rising error rate signals the model needs retraining.
- **Business-level alerting**: the automation layer itself
  (`rules_engine.py` + `notifier.py`) is the production monitoring
  layer for business metrics, already wired to Slack/email.

### What would you change if the business expanded from one region to 20 countries?
- **Data model**: add a `dim_geography`/`dim_currency` dimension;
  store `amount` in both local currency and a normalized reporting
  currency (with an FX-rate table and `date_key` for point-in-time
  conversion) rather than assuming a single currency as this build does.
- **Warehouse**: partition/cluster by country/region in addition to
  date, and consider regional data residency requirements (e.g. GDPR)
  which may require region-specific warehouses rather than one global
  BigQuery dataset.
- **Streaming**: partition Kafka topics by region so regional outages
  don't cascade, and consider regional Kafka clusters with cross-region
  replication for global rollups.
- **Latency**: deploy the backend/frontend behind a global CDN with
  regional Cloud Run deployments rather than a single-region service.
- **Localization**: date/number formatting, multi-language frontend,
  region-specific SLA/business-rule thresholds (a 15% SLA breach
  threshold may not be meaningful/comparable across very different
  logistics markets).
- **Orchestration**: DAGs would need to be parameterized per
  region/timezone rather than a single global hourly schedule.
