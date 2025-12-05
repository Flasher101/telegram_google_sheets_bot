@echo off
REM Batch script to start the Telegram bot and AI server

REM Create logs directory if it doesn't exist
IF NOT EXIST logs (
    mkdir logs
)

REM Check for configuration files
IF NOT EXIST config.py (
    echo Error: config.py not found. Please create it from config.example.py.
    pause
    exit /b
)
IF NOT EXIST service_account.json (
    echo Error: service_account.json not found. Please create it from service_account.example.json.
    pause
    exit /b
)

REM Activate virtual environment
IF NOT EXIST .venv\\Scripts\\activate (
    echo Virtual environment not found. Please run setup.bat first.
    pause
    exit /b
)
call .venv\\Scripts\\activate

REM Set PYTHONPATH to the project root
set PYTHONPATH=%CD%

REM Start AI server in a new window
echo Starting AI server... Log: logs\ai_server.log
start "AI Server" cmd /c "python -m uvicorn ai_server.main:app --host 127.0.0.1 --port 8000 > logs\ai_server.log 2>&1"

REM Start WhatsApp bot in a new window
echo Starting WhatsApp bot... Log: logs\whatsapp_bot.log
start "WhatsApp Bot" cmd /c "python -m uvicorn bot_whatsapp.main:app --host 127.0.0.1 --port 8001 > logs\whatsapp_bot.log 2>&1"

REM Start the Telegram bot in the current window (this will block)
echo Starting Telegram bot... Log: logs\telegram_bot.log
python bot_telegram/bot_main.py > logs\telegram_bot.log 2>&1

REM --- Graceful Shutdown ---
echo Shutting down services...
taskkill /F /FI "WINDOWTITLE eq AI Server" /T > nul
taskkill /F /FI "WINDOWTITLE eq WhatsApp Bot" /T > nul

deactivate
