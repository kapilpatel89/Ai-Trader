@echo off
title CoinDCX AI Institutional Futures Terminal
color 0B
cls

echo ===============================================================================
echo     COINDCX AI INSTITUTIONAL FUTURES TERMINAL
echo     Multi-Factor Quantitative Scanner and Local GPU LLM Reasoning Agent
echo ===============================================================================
echo.

echo [*] Checking Python environment...
python --version
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH. Please install Python 3.10+ and re-run.
    pause
    exit /b 1
)

echo [*] Checking required dependencies...
python -c "import fastapi, uvicorn, aiohttp, websockets, numpy, pydantic" >nul 2>&1
if errorlevel 1 (
    echo [*] Installing missing Python dependencies from requirements.txt...
    pip install -r requirements.txt
)

echo [*] Checking Local GPU LLM Model files...
if not exist "models\llama_bin\llama-server.exe" (
    echo [*] Setting up local llama-server GPU acceleration binary...
    python download_llm.py 1
)

if not exist "models\qwen2.5-0.5b-instruct-q4_k_m.gguf" (
    echo [*] Setting up local Qwen 2.5 AI model for offline trading reasoning...
    python download_llm.py 1
)

echo [*] Reclaiming port 8000 if occupied...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo ===============================================================================
echo [OK] System Ready! Starting CoinDCX AI Terminal on http://127.0.0.1:8000
echo [*] GPU-First Memory Acceleration Active (GT 730 / CUDA / Vulkan)
echo [*] Sub-Second Fast WebSocket Streaming Enabled
echo ===============================================================================
echo.

start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000"

python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

pause
