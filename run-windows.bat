@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo [Mobius] Preparing local environment; first setup requires internet...
    where py >nul 2>nul
    if errorlevel 1 (
        echo Python 3.11 or 3.12 is required. Download from python.org
        pause
        exit /b 1
    )
    py -3.12 -m venv .venv 2>nul
    if errorlevel 1 py -3.11 -m venv .venv
    if errorlevel 1 (
        echo Could not create a virtual environment.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install -r requirements-extended.txt
    if errorlevel 1 (
        echo Full dependencies failed; installing base dependencies...
        ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    )
    if errorlevel 1 (
        echo Setup failed. Check internet connectivity and retry.
        pause
        exit /b 1
    )
)
start "" ".venv\Scripts\pythonw.exe" app.py
