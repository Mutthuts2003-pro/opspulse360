@echo off
REM One-time setup: creates venv and installs everything
cd /d "%~dp0"
python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Setup complete. Now run start_backend.bat and start_frontend.bat
pause
