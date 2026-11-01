@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Belum ada virtual environment. Jalankan run-windows.bat dahulu.
 pause
 exit /b 1
)
echo [Mobius] Debug: exception Python ditampilkan di terminal ini.
".venv\Scripts\python.exe" app.py
if errorlevel 1 echo Mobius berhenti dengan kode %errorlevel%.
echo Crash log: %USERPROFILE%\Documents\Mobius\mobius-error.log
pause
