@echo off
echo ===================================================
echo   Starting Smart Medicine Reminder System (Local)
echo ===================================================
cd /d %~dp0backend
echo Checking Python environment...
python -m pip install -r requirements.txt
echo.
echo Launching Flask Backend & Frontend Server...
echo Access the Application at: http://localhost:5000
echo.
python app.py
pause
