@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Python virtual environment is missing. Run run-windows.bat first.
 pause
 exit /b 1
)
echo [Mobius] Diagnostic launch: temporarily pin/expand island to make it visible.
echo [Mobius] Running Qt setup and startup stages; Ctrl+C will interrupt the process.
set "MOBIUS_DEBUG_VISIBLE=1"
set "MOBIUS_DEBUG_STARTUP=1"
set "PYTHONUNBUFFERED=1"
".venv\Scripts\python.exe" -u app.py
set "MOBIUS_EXIT=%ERRORLEVEL%"
echo.
echo [Mobius] Python exit code: %MOBIUS_EXIT%
echo Startup log: %USERPROFILE%\Documents\Mobius\mobius-startup.log
echo Crash log: %USERPROFILE%\Documents\Mobius\mobius-error.log
echo To test bare Qt without Mobius, run test-qt-windows.bat
pause
exit /b %MOBIUS_EXIT%
