@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run run-windows.bat first to create the virtual environment.
    pause
    exit /b 1
)
echo [Mobius] Installing voice, media and packaging dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements-extended.txt -r requirements-voice.txt -r requirements-media.txt pyinstaller
if errorlevel 1 (
    echo Could not install build requirements.
    pause
    exit /b 1
)
set "PDF_FLAGS="
".venv\Scripts\python.exe" -c "import pdf2docx" >nul 2>nul
if not errorlevel 1 set "PDF_FLAGS=--collect-all pdf2docx"
echo [Mobius] Building standalone Windows EXE...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name Mobius --icon "assets\mobius.ico" --add-data "assets\mobius.ico;assets" %PDF_FLAGS% --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtPdfWidgets --collect-all pymupdf --collect-all faster_whisper --collect-all ctranslate2 --hidden-import sounddevice --hidden-import win32com.client --hidden-import winrt.windows.media.control app.py
if errorlevel 1 (
    echo Build failed. See the error above; the source app is not affected.
    pause
    exit /b 1
)
echo.
echo Complete: dist\Mobius.exe
echo AI and Whisper model downloads remain external; models are NOT embedded.
pause
