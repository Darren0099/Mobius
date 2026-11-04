@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Run run-windows.bat first.
 pause
 exit /b 1
)
echo Installing optional Windows Media Control integration...
".venv\Scripts\python.exe" -m pip install -r requirements-media.txt
if errorlevel 1 (
 echo Media setup failed. File Studio and voice assistant still work without it.
 pause
 exit /b 1
)
echo Windows media support installed.
pause
