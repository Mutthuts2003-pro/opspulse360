@echo off
cd /d "%~dp0"
python -m venv venv-dbt
call venv-dbt\Scripts\activate.bat
pip install -r requirements-dbt.txt
echo dbt env ready. Use: venv-dbt\Scripts\activate then cd dbt_project ^& dbt run --profiles-dir %%USERPROFILE%%\.dbt
pause
