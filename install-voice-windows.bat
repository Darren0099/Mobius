@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Jalankan run-windows.bat dahulu untuk menginstal Mobius.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-voice.txt
if errorlevel 1 (pause & exit /b 1)
".venv\Scripts\python.exe" scripts\download_voice.py
if errorlevel 1 (pause & exit /b 1)
echo Model Bahasa Indonesia siap untuk penggunaan offline.
pause
