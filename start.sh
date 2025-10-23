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
    if [ -n "$BOT_PID" ]; then
        kill "$BOT_PID" 2>/dev/null
        echo "Telegram bot stopped."
    fi
    deactivate
    echo "Shutdown complete."
}

# Trap signals to ensure cleanup is called
trap cleanup SIGINT SIGTERM EXIT

# --- Service Launch ---
# Start AI server in the background
echo "Starting AI server... Log: logs/ai_server.log"
python -m uvicorn ai_server.main:app --host 127.0.0.1 --port 8000 > logs/ai_server.log 2>&1 &
AI_SERVER_PID=$!

# Start the Telegram bot in the background
echo "Starting Telegram bot... Log: logs/bot.log"
python bot/bot_main.py > logs/bot.log 2>&1 &
BOT_PID=$!

echo "Both services started. AI Server PID: $AI_SERVER_PID, Bot PID: $BOT_PID"
echo "Press Ctrl+C to stop both services."

# Wait for either process to exit
wait -n $AI_SERVER_PID $BOT_PID

# If one process exits, the script will continue and the cleanup function will be called
# This ensures that if one service crashes, the other is also stopped.
exit 0
