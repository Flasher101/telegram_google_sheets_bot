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

# --- Call Center Contact Information (for new buttons) ---
# WhatsApp number in international format without '+' or spaces (e.g., 77001234567)
CALL_CENTER_WHATSAPP_NUMBER = "77001234567"
# Telegram username (without the '@')
CALL_CENTER_TELEGRAM_USERNAME = "YourTelegramUsername"


# --- WhatsApp Bot Configuration ---
# Get these from the Meta Developer Portal (App Dashboard -> WhatsApp -> API Setup)
WHATSAPP_ACCESS_TOKEN = "YOUR_WHATSAPP_ACCESS_TOKEN"
WHATSAPP_PHONE_NUMBER_ID = "YOUR_WHATSAPP_PHONE_NUMBER_ID"

# A secret string you create. This is used to verify the webhook.
WHATSAPP_VERIFY_TOKEN = "YOUR_CUSTOM_VERIFY_TOKEN"

# Base URL of the WhatsApp bot server (for webhook)
WHATSAPP_BOT_URL = "http://localhost:8001"
