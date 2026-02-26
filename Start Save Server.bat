@echo off
title Pi Energy — Quote Save Server
echo.
echo  Starting Pi Energy Quote Save Server...
echo.
node "%~dp0pi-save-server.js"
if errorlevel 1 (
  echo.
  echo  ERROR: Node.js not found. Please install from https://nodejs.org
  pause
)
