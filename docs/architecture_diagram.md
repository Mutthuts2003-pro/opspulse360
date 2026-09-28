# OpsPulse 360 — Architecture Diagram

## End-to-end flow

```mermaid
flowchart TB
    subgraph SRC["1. Source Layer"]
        S1[("Orders / Customers / Products\nInventory / Delivery / Support\nMarketing (CSV files)")]
    end

    subgraph STREAM["2. Streaming Layer"]
        EG["Event Generator\n(streaming/event_generator.py)"]
        KAFKA[["Kafka Topics\norders.events / payments.events\ndelivery.events / inventory.events\n(streaming/kafka_sim.py — simulated broker;\nreal Kafka available via docker-compose --profile kafka)"]]
        SP["Stream Processor\n(streaming/stream_processor.py)\nconsumer group: stream-processor-v1"]
    end

    subgraph LAKE_WH["3-4. Lake + Warehouse (Bronze/Silver/Gold)"]
        BRONZE[("Bronze\nraw, minimally modified")]
        SILVER[("Silver\ncleaned, deduped, validated\n+ dq_report")]
        GOLD[("Gold — Star Schema\ndim_customer, dim_product,\ndim_warehouse, dim_date\nfact_orders, fact_inventory,\nfact_delivery, fact_marketing")]
        LIVE[("live_* tables\n(real-time aggregates)")]
    end

    subgraph DBT["5. Transformation (dbt)"]
        STG["staging models\n(stg_orders, stg_customers, ...)"]
        INT["intermediate models\n(int_orders_enriched, ...)"]
        MART["mart models\n(dims + facts, 20 dbt tests)"]
    end

    subgraph ORCH["Orchestration"]
        AF["Airflow DAG\nopspulse_pipeline\n(hourly schedule)"]
    end

    subgraph ANALYTICS["6-7. Analytics + Intelligence"]
        KPI["KPI Engine\n(analytics/kpi_engine.py)\nSales / Customers / Inventory\nDelivery / Marketing"]
        ANOM["Anomaly Detection\n(ml/anomaly_detection.py)\nz-score + Isolation Forest\n+ driver explanation"]
        FCST["Forecasting\n(ml/forecasting.py)\n7-day revenue forecast"]
    end

    subgraph AUTOMATION["8. Automation"]
        RULES["Business Rules Engine\n(automation/rules_engine.py)\n4 mandatory rules"]
        NOTIFY["Notifier\n(automation/notifier.py)\nSlack / Email"]
    end

    subgraph APP["9-10. Application"]
        API["FastAPI Backend\n27 REST endpoints\nJWT auth, 2 roles"]
        FE["Frontend Dashboard\n(frontend/index.html)\nExec / Ops / Realtime / Analytics\nForecast / Alerts / Data Quality"]
    end

    subgraph CLOUD["11-12. Cloud & DevOps"]
        DOCKER["Docker\nbackend + pipeline images"]
        CI["GitHub Actions CI/CD\ntest -> dbt -> build -> deploy"]
        DEPLOY[("Cloud Deployment\nGCP/AWS/Azure")]
    end

    S1 --> BRONZE
    S1 --> EG
    EG --> KAFKA
    KAFKA --> SP
    SP --> LIVE

    BRONZE --> SILVER --> GOLD
    S1 --> STG --> INT --> MART
    MART -.dbt tests.-> MART

    AF -.schedules.-> BRONZE
    AF -.schedules.-> STG
    AF -.schedules.-> KPI
    AF -.schedules.-> ANOM
    AF -.schedules.-> RULES

    GOLD --> KPI
    GOLD --> ANOM
    GOLD --> FCST
    ANOM --> RULES
    GOLD --> RULES
    LIVE --> RULES
    RULES --> NOTIFY

    KPI --> API
    ANOM --> API
    FCST --> API
    RULES --> API
    LIVE --> API
    GOLD --> API
    API --> FE

    API --> DOCKER --> CI --> DEPLOY
```

## Minimum streaming demonstration (assignment §6)

```mermaid
flowchart LR
    A[Event Generator] --> B[Kafka Topic]
    B --> C[Stream Processor]
    C --> D[Analytical Store\nlive_* tables]
    D --> E[API\n/api/realtime/*]
    E --> F[Live Dashboard\nReal-Time Monitoring page]
```

## Notes on substitutions made in this build

| Required (assignment) | Used in this build | Why |
|---|---|---|
| Apache Kafka | `streaming/kafka_sim.py` (SQLite-backed broker with topics, producer/consumer API, offset commits, consumer groups) | No Kafka cluster available in the build sandbox. Real Kafka + Zookeeper are included in `docker/docker-compose.yml` under the `kafka` profile — swap `kafka_sim.py` for `kafka-python`/`confluent-kafka` pointed at `kafka:9092`; the rest of the pipeline (event schemas, consumer logic) does not change. |
| BigQuery / Snowflake | SQLite (`data/opspulse.db`) for the app; DuckDB (`data/opspulse_dbt.duckdb`) for the dbt project | Zero-setup, file-based, fully SQL-compatible. dbt models are portable — change `profiles.yml` to a `snowflake`/`bigquery` target and the SQL runs unmodified in production. |
| Airflow (running scheduler) | DAG file written and syntax-validated (`airflow/dags/opspulse_pipeline_dag.py`); Airflow service included in `docker-compose.yml` under the `airflow` profile | No standalone Airflow metadata DB/scheduler in the build sandbox. The DAG calls the exact scripts that were run and tested directly. |
| GCS / S3 | Local `data/` directory (raw CSVs = bronze landing zone) | Same "immutable raw storage" role; swapping to a bucket is a path change in `bronze/load_bronze.py`. |
