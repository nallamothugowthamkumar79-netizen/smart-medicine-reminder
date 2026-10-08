@echo off
cd /d "%~dp0"
echo ========================================================
echo    Pushing Smart Medicine Reminder to GitHub
echo    Target: https://github.com/nallamothugowthamkumar79-netizen/smart-medicine-reminder
echo ========================================================
echo.
"C:\Users\nalla\.gemini\antigravity\scratch\mingit\cmd\git.exe" push -u origin main
echo.
pause
