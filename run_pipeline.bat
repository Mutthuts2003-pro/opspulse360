@echo off
REM Rebuilds everything: data -> warehouse -> KPIs -> ML -> alerts
cd /d "%~dp0"
call venv\Scripts\activate.bat
cd data_generator && python generate_seed_data.py --out ../data && cd ..
cd warehouse && python build_warehouse.py && cd ..
cd analytics && python kpi_engine.py && cd ..
cd ml && python anomaly_detection.py && python forecasting.py && cd ..
cd automation && python rules_engine.py && cd ..
echo Pipeline complete.
pause
