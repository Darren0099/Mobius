@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Start Mobius using run-windows.bat first.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" scripts\voice_diagnostic.py
echo.
echo End of local microphone and English voice test.
pause
