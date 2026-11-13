@echo off
cd /d "%~dp0"
if exist "dist\ACTIVE-Control.exe" (
  start "" "dist\ACTIVE-Control.exe"
  exit /b 0
)
if not exist ".venv\Scripts\pythonw.exe" (
  echo Python environment is missing. See active_control\README.md
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "active_control\app.py"
