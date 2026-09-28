# OpsPulse 360

An end-to-end, production-style analytics engineering platform for a
multi-warehouse e-commerce/retail business: source data ingestion,
live event streaming, a governed data warehouse, business KPIs,
anomaly detection, demand forecasting, automated business-rule alerts,
and a web application to consume it all.

Built for the OpsPulse 360 Enterprise Analytics Engineering Capstone
Assignment (MastersCampus Academy). See `docs/` for the architecture
diagram, ERD, data dictionary, cloud/cost writeup, and answers to the
mandatory interview questions.

## What's actually running vs. what's substituted

Everything in this repo is real, runnable code — nothing is a stub or
a mockup. A few components use a local substitute for infrastructure
that isn't available in a laptop/CI environment (no Kafka cluster, no
cloud warehouse account); each substitute is a drop-in for the real
thing and documented in `docs/architecture_diagram.md`:

| Required | This build uses | Real thing is a drop-in via |
|---|---|---|
| Apache Kafka | `streaming/kafka_sim.py` (SQLite-backed broker, same producer/consumer API shape) | `docker-compose --profile kafka` (real Kafka+Zookeeper included) |
| Snowflake / BigQuery | SQLite (app) + DuckDB (dbt project) | change `dbt_project`'s `profiles.yml` target |
| Airflow (scheduler running) | DAG file written & validated, not executed here | `docker-compose --profile airflow` |

Everything else — the 7 data generators, the Bronze/Silver/Gold
pipeline, the 19-model/20-test dbt project, the KPI engine, both
anomaly-detection methods, 7-day forecasting, all 4 business rules,
the 27-endpoint FastAPI backend, the role-based frontend, Docker
images, and the CI workflow — has been run and tested directly (see
`tests/`, 70 tests passing).

## Repository layout

```
data_generator/     synthetic seed data for all 7 mandatory datasets
streaming/           simulated Kafka broker, event generator, stream processor
warehouse/           Bronze -> Silver -> Gold pipeline (SQLite)
dbt_project/         staging/intermediate/marts dbt models (DuckDB target)
airflow/dags/        orchestration DAG
analytics/           KPI engine (5 domains)
ml/                  anomaly detection (statistical + Isolation Forest), forecasting
automation/          business rules engine + Slack/email notifier
backend/             FastAPI REST API (27 endpoints, JWT auth)
frontend/            single-file HTML/JS dashboard (all required pages)
docker/              Dockerfiles + docker-compose (backend, pipeline, optional Kafka/Airflow)
.github/workflows/   CI/CD (GitHub Actions)
tests/               70 pytest tests across pipeline, ML, and backend
docs/                architecture diagram, ERD, data dictionary, cloud cost, interview Q&A
data/                generated CSVs + SQLite/DuckDB warehouse files (gitignored in practice)
```

## Run it locally

```bash
# 1. Generate synthetic source data (7 datasets)
cd data_generator && python generate_seed_data.py --out ../data --scale 1.0

# 2. Build the warehouse: Bronze -> Silver -> Gold
cd ../warehouse && python build_warehouse.py

# 3. (Optional) run the real dbt project against DuckDB
cd ../dbt_project && dbt run --profiles-dir ~/.dbt && dbt test --profiles-dir ~/.dbt

# 4. Compute KPIs, run ML, evaluate business rules
cd ../analytics && python kpi_engine.py
cd ../ml && python anomaly_detection.py && python forecasting.py
cd ../automation && python rules_engine.py

# 5. Simulate live streaming (optional, powers the Real-Time page)
cd ../streaming
python event_generator.py --ticks 200 --interval 0.2 &
python stream_processor.py --loop-forever &

# 6. Start the backend
cd ../backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# API docs at http://localhost:8000/docs

# 7. Serve the frontend
cd ../frontend
python -m http.server 8080
# open http://localhost:8080 — login: executive/exec123 or ops/ops123
```

Or via Docker Compose (backend + frontend only, no extra setup):
```bash
cd docker && docker compose up backend frontend
```
Add `--profile kafka` or `--profile airflow` to also run real Kafka or
Airflow instead of the local simulations.

## Run the tests

```bash
pip install pytest httpx
pytest tests/ -v
```

## Business questions this answers

- **Revenue/orders right now** → Real-Time Monitoring page,
  `/api/realtime/metrics`
- **Which products/warehouses are risky** → Inventory Analytics page,
  `/api/inventory/at-risk`
- **Are SLA breaches increasing** → Delivery Analytics page,
  `/api/delivery/sla-trend`
- **Which items will stock out** → Alert Center (Rule 1: inventory vs.
  forecast demand), `/api/alerts`
- **Why did revenue change** → Forecasting & Anomalies page,
  `/api/intelligence/anomalies/explanations`
- **Which campaigns are profitable** → Marketing section of Sales
  Analytics, `/api/marketing/by-channel`
- **What should ops do automatically** → `automation/rules_engine.py`
  + `automation/notifier.py`

## Evaluation rubric cross-reference

| Rubric area | Where to look |
|---|---|
| Business understanding | this README, `docs/architecture_diagram.md` |
| SQL & analytical thinking | `warehouse/*/*.py`, `dbt_project/models/`, `analytics/kpi_engine.py` |
| Data modeling & warehouse | `docs/erd.md`, `warehouse/gold/build_gold.py` |
| Data engineering & pipelines | `warehouse/`, `airflow/dags/` |
| Streaming implementation | `streaming/` |
| Analytics & KPI layer | `analytics/kpi_engine.py`, `/api/dashboard/kpis` |
| Automation & intelligence | `ml/`, `automation/` |
| Backend & frontend | `backend/`, `frontend/` |
| Cloud, Docker & CI/CD | `docker/`, `.github/workflows/ci.yml`, `docs/cloud_architecture_cost.md` |
| Documentation & interview readiness | `docs/` (all files), especially `docs/interview_questions.md` |
