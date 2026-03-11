@echo off
title Pi Energy — Quote Save Server
echo.
echo  Starting Pi Energy Quote Save Server...
echo  Saving quotes to: C:\Users\HP\Desktop\Principle and Innovation\Pi Ops\Customers
echo.
node "%~dp0pi-save-server.js" "C:\Users\HP\Desktop\Principle and Innovation\Pi Ops\Customers"
if errorlevel 1 (
  echo.
  echo  ERROR: Could not start server. Check Node.js is installed (https://nodejs.org)
  pause
)
