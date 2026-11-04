@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo No .venv found. Run run-windows.bat to set up dependencies.
  pause
  exit /b 1
)
echo [Mobius] Minimal Qt diagnosis. This does NOT launch Mobius or record audio.
set "PYTHONUNBUFFERED=1"
".venv\Scripts\python.exe" -u scripts\qt_doctor.py
echo Exit code: %ERRORLEVEL%
pause
