# config.example.py

# Telegram Bot Token from @BotFather
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

# OpenAI API Key for future AI model integrations
# Get your key from: https://platform.openai.com/account/api-keys
OPENAI_API_KEY = "sk-YOUR_OPENAI_API_KEY"

# Google Sheets ID from the URL of your Google Sheet
# Example: https://docs.google.com/spreadsheets/d/1234567890abcdefghijklmnopqrstuvwxyz/edit#gid=0
# GOOGLE_SHEETS_ID is "1234567890abcdefghijklmnopqrstuvwxyz"
GOOGLE_SHEETS_ID = "YOUR_GOOGLE_SHEETS_ID"

# Path to the FAISS index file (e.g., inside a directory)
# The directory will be created automatically.
FAISS_INDEX_PATH = "faiss_index/index.faiss"

# Base URL of the AI server
AI_SERVER_URL = "http://localhost:8000"
