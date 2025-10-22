#!/bin/bash
# Bash script to start the Telegram bot and AI server

# Create logs directory if it doesn't exist
if [ ! -d "logs" ]; then
    mkdir logs
fi

# Check for configuration files
if [ ! -f "config.py" ]; then
    echo "Error: config.py not found. Please create it from config.example.py."
    exit 1
fi
if [ ! -f "service_account.json" ]; then
    echo "Error: service_account.json not found. Please create it from service_account.example.json."
    exit 1
fi

# Activate virtual environment
if [ ! -f ".venv/bin/activate" ]; then
    echo "Virtual environment not found. Please run setup.sh first."
    exit 1
fi
source .venv/bin/activate

# Set PYTHONPATH to the project root
export PYTHONPATH=$(pwd)

# Start AI server in the background
echo "Starting AI server..."
python -m uvicorn ai_server.main:app --host 127.0.0.1 --port 8000 &
AI_SERVER_PID=$!

# Start the Telegram bot
echo "Starting Telegram bot..."
python bot/bot_main.py

# Graceful shutdown
kill $AI_SERVER_PID

deactivate
