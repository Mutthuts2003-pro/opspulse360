"""
OpsPulse 360 - Warehouse Build Orchestrator
Runs Bronze -> Silver -> Gold in sequence. This is the local equivalent
of what the Airflow DAG (airflow/dags/opspulse_pipeline_dag.py) triggers
on a schedule.
"""
import subprocess
import sys
import os

STEPS = [
    ("Bronze", os.path.join("bronze", "load_bronze.py")),
    ("Silver", os.path.join("silver", "build_silver.py")),
    ("Gold", os.path.join("gold", "build_gold.py")),
]


def main():
    base = os.path.dirname(__file__)
    for name, script in STEPS:
        print(f"\n=== {name} layer ===")
        result = subprocess.run([sys.executable, script], cwd=base)
        if result.returncode != 0:
            print(f"[FAILED] {name} layer exited with code {result.returncode}")
            sys.exit(result.returncode)
    print("\nWarehouse build complete: Bronze -> Silver -> Gold.")


if __name__ == "__main__":
    main()
