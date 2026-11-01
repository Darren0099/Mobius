@echo off
setlocal
cd /d "%~dp0"
where ollama >nul 2>nul
if errorlevel 1 (
 echo Instal Ollama dari https://ollama.com/download/windows kemudian jalankan kembali.
 pause
 exit /b 1
)
ollama pull qwen2.5:3b
if errorlevel 1 (pause & exit /b 1)
echo Model AI siap secara lokal.
pause
