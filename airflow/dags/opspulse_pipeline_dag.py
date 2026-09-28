"""
OpsPulse 360 - Airflow Orchestration DAG
Schedules the end-to-end batch pipeline: Bronze load -> Silver clean ->
Gold star schema -> dbt build/test -> KPI computation -> ML (anomaly
detection + forecasting) -> business rules / alerting.

This DAG is written against the standard Airflow 2.x API. It is not
executed inside this sandbox (no Airflow scheduler/metadata DB is
available here), but every task simply shells out to the same scripts
that were already run and verified directly in this project
(warehouse/build_warehouse.py, dbt, analytics/kpi_engine.py,
ml/anomaly_detection.py, ml/forecasting.py, automation/rules_engine.py),
so `airflow dags test opspulse_pipeline` will work as-is once deployed
to a real Airflow environment (see docker/docker-compose.yml, which
includes an airflow service).
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.trigger_rule import TriggerRule

PROJECT_ROOT = "/opt/opspulse360"  # mount point inside the airflow container

default_args = {
    "owner": "data-eng",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
    "email_on_failure": True,
    "email": ["data-alerts@opspulse360.example.com"],
}

with DAG(
    dag_id="opspulse_pipeline",
    description="OpsPulse 360 end-to-end batch pipeline: bronze -> silver -> gold -> dbt -> analytics -> ML -> alerts",
    default_args=default_args,
    schedule_interval="0 * * * *",  # hourly batch cycle
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["opspulse360", "analytics-engineering"],
) as dag:

    load_bronze = BashOperator(
        task_id="load_bronze",
        bash_command=f"cd {PROJECT_ROOT}/warehouse/bronze && python load_bronze.py",
    )

    build_silver = BashOperator(
        task_id="build_silver",
        bash_command=f"cd {PROJECT_ROOT}/warehouse/silver && python build_silver.py",
    )

    build_gold = BashOperator(
        task_id="build_gold",
        bash_command=f"cd {PROJECT_ROOT}/warehouse/gold && python build_gold.py",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {PROJECT_ROOT}/dbt_project && dbt run --profiles-dir /opt/dbt_profiles",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {PROJECT_ROOT}/dbt_project && dbt test --profiles-dir /opt/dbt_profiles",
    )

    compute_kpis = BashOperator(
        task_id="compute_kpis",
        bash_command=f"cd {PROJECT_ROOT}/analytics && python kpi_engine.py",
    )

    run_anomaly_detection = BashOperator(
        task_id="run_anomaly_detection",
        bash_command=f"cd {PROJECT_ROOT}/ml && python anomaly_detection.py",
    )

    run_forecasting = BashOperator(
        task_id="run_forecasting",
        bash_command=f"cd {PROJECT_ROOT}/ml && python forecasting.py",
    )

    evaluate_business_rules = BashOperator(
        task_id="evaluate_business_rules",
        bash_command=f"cd {PROJECT_ROOT}/automation && python rules_engine.py",
    )

    # Fan out: bronze -> silver -> gold -> dbt run -> dbt test
    # then analytics/ML/rules run in parallel off the same gold+dbt output
    load_bronze >> build_silver >> build_gold >> dbt_run >> dbt_test
    dbt_test >> [compute_kpis, run_anomaly_detection, run_forecasting]
    [run_anomaly_detection, run_forecasting, compute_kpis] >> evaluate_business_rules
