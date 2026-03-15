@echo off
title Pi Ops — Installer Onboarding (localhost:3000)
cd /d "%~dp0"

echo.
echo  =========================================
echo   Pi Ops  -  Installer Onboarding
echo   Web App  ^|  http://localhost:3000
echo  =========================================
echo.
echo  Starting Flask server...
echo  Browser will open automatically.
echo.
echo  To stop: close this window or press Ctrl+C
echo.

python app.py

echo.
echo  Server stopped.
pause
