@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Jalankan run-windows.bat terlebih dahulu.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-voice.txt pyinstaller
if errorlevel 1 (pause & exit /b 1)
set "PDF_FLAGS="
".venv\Scripts\python.exe" -c "import pdf2docx" >nul 2>nul
if not errorlevel 1 set "PDF_FLAGS=--collect-all pdf2docx"
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name Mobius --icon "assets\mobius.ico" --add-data "assets\mobius.ico;assets" %PDF_FLAGS% --collect-all fitz --collect-all faster_whisper --collect-all ctranslate2 --hidden-import sounddevice --hidden-import win32com.client app.py
if errorlevel 1 (echo Build gagal. & pause & exit /b 1)
echo.
echo SELESAI: dist\Mobius.exe
pause
