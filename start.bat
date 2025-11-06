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

REM Start AI server in the background
echo Starting AI server...
start "AI Server" python -m uvicorn ai_server.main:app --host 127.0.0.1 --port 8000

REM Start the Telegram bot
echo Starting Telegram bot...
python bot/bot_main.py

REM Graceful shutdown
taskkill /F /FI "WINDOWTITLE eq AI Server" /T > nul

deactivate
