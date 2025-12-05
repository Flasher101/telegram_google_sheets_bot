#!/bin/bash
# Bash script to start the Telegram bot and AI server

# --- Setup ---
set -e # Exit immediately if a command exits with a non-zero status.
BASEDIR=$(dirname "$0")
cd "$BASEDIR"

# --- Pre-flight Checks ---
# Create logs directory if it doesn't exist
if [ ! -d "logs" ]; then
    echo "Creating logs directory..."
    mkdir logs
fi

# Check for configuration files
if [ ! -f "config.py" ]; then
    echo "ERROR: config.py not found. Please create it from config.example.py." >&2
    exit 1
fi
if [ ! -f "service_account.json" ]; then
    echo "ERROR: service_account.json not found. Please create it from service_account.example.json." >&2
    exit 1
fi

# Activate virtual environment
if [ ! -f ".venv/bin/activate" ]; then
    echo "ERROR: Virtual environment not found. Please create it first." >&2
    exit 1
fi
source .venv/bin/activate

export PYTHONPATH=$(pwd)

# --- Process Management ---
# Function to clean up background processes on exit
cleanup() {
    echo "Shutting down services..."
    if [ -n "$AI_SERVER_PID" ]; then
        kill "$AI_SERVER_PID" 2>/dev/null
        echo "AI server stopped."
    fi
    if [ -n "$TELEGRAM_BOT_PID" ]; then
        kill "$TELEGRAM_BOT_PID" 2>/dev/null
        echo "Telegram bot stopped."
    fi
    if [ -n "$WHATSAPP_BOT_PID" ]; then
        kill "$WHATSAPP_BOT_PID" 2>/dev/null
        echo "WhatsApp bot stopped."
    fi
    deactivate
    echo "Shutdown complete."
}

# Trap signals to ensure cleanup is called
trap cleanup SIGINT SIGTERM EXIT

# --- Service Launch ---
# Start AI server in the background
echo "Starting AI server... Log: logs/ai_server.log"
python -m uvicorn ai_server.main:app --host 0.0.0.0 --port 8000 > logs/ai_server.log 2>&1 &
AI_SERVER_PID=$!

# Start the Telegram bot in the background
echo "Starting Telegram bot... Log: logs/telegram_bot.log"
python bot_telegram/bot_main.py > logs/telegram_bot.log 2>&1 &
TELEGRAM_BOT_PID=$!

# Start the WhatsApp bot in the background
echo "Starting WhatsApp bot... Log: logs/whatsapp_bot.log"
python -m uvicorn bot_whatsapp.main:app --host 0.0.0.0 --port 8001 > logs/whatsapp_bot.log 2>&1 &
WHATSAPP_BOT_PID=$!

echo "All services started."
echo "  - AI Server PID: $AI_SERVER_PID"
echo "  - Telegram Bot PID: $TELEGRAM_BOT_PID"
echo "  - WhatsApp Bot PID: $WHATSAPP_BOT_PID"
echo "Press Ctrl+C to stop all services."

# Wait for any process to exit
wait -n $AI_SERVER_PID $TELEGRAM_BOT_PID $WHATSAPP_BOT_PID

# If one process exits, the script will continue and the cleanup function will be called
# This ensures that if one service crashes, the other is also stopped.
exit 0
