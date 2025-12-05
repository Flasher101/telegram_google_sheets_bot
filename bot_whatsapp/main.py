# bot_whatsapp/main.py
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request, HTTPException, Response
import uvicorn
import aiohttp
import asyncio

# --- Logging Setup ---
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
log_dir = os.path.join(project_root, 'logs')
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, 'whatsapp_bot.log')
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_handler = RotatingFileHandler(log_file, maxBytes=1024*1024*5, backupCount=5)
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(logging.StreamHandler())

# --- Configuration Import ---
try:
    from config import (
        WHATSAPP_VERIFY_TOKEN,
        WHATSAPP_ACCESS_TOKEN,
        WHATSAPP_PHONE_NUMBER_ID,
        AI_SERVER_URL,
        CALL_CENTER_WHATSAPP_NUMBER,
        CALL_CENTER_TELEGRAM_USERNAME
    )
except ImportError:
    logger.critical("Error: config.py not found or missing required variables.")
    sys.exit(1)

# --- FastAPI App ---
app = FastAPI()

# In-memory storage for user states and data
user_states = {}

# --- WhatsApp API Communication ---
WHATSAPP_API_URL = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

async def send_whatsapp_message(to: str, message_data: dict):
    """Sends a message using the WhatsApp Business API."""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        **message_data
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(WHATSAPP_API_URL, json=payload, headers=headers) as response:
                response.raise_for_status()
                logger.info(f"Message sent to {to}. Status: {response.status}")
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Error sending WhatsApp message to {to}: {e}")
            return None

async def send_text_message(to: str, text: str):
    """Helper to send a simple text message."""
    data = {"type": "text", "text": {"body": text}}
    return await send_whatsapp_message(to, data)

async def send_main_menu(to: str):
    """Sends the main menu with interactive buttons."""
    message = "Здравствуйте! Я ваш AI-ассистент. Выберите действие:"
    buttons = {
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": message},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "ai_consultation", "title": "🤖 Консультация AI"}},
                    {"type": "reply", "reply": {"id": "call_center", "title": "📞 Номер КЦ"}},
                    {"type": "reply", "reply": {"id": "instructions", "title": "📚 Инструкции"}},
                ]
            }
        }
    }
    return await send_whatsapp_message(to, buttons)

async def send_instructions_menu(to: str):
    """Sends the instructions menu with interactive buttons."""
    message = "Выберите раздел инструкций:"
    buttons = {
        "type": "interactive",
        "interactive": {
            "type": "list", # Using a list for a better UX with multiple options
            "body": {"text": message},
            "action": {
                "button": "Выбрать",
                "sections": [
                    {
                        "title": "Доступные документы",
                        "rows": [
                            {"id": "instruction_tech", "title": "Тех. документация"},
                            {"id": "instruction_user", "title": "Инструкции"},
                            {"id": "instruction_reg", "title": "Регистрация"},
                            {"id": "instruction_non_resident", "title": "Для не резидентов"},
                            {"id": "instruction_archive", "title": "Архив"},
                        ]
                    }
                ]
            }
        }
    }
    footer = {"type": "interactive",
              "interactive":{
                  "type":"button",
                  "body":{"text":"Назад"},
                  "action":{
                      "buttons":[
                          {"type":"reply", "reply":{"id":"main_menu", "title":"⬅️ Назад"}}
                      ]
                  }
              }}
    await send_whatsapp_message(to, buttons)
    return await send_whatsapp_message(to, footer)


# --- Webhook Handlers ---
@app.get("/webhook")
async def verify_webhook(request: Request):
    """Handles webhook verification for the Meta platform."""
    verify_token = request.query_params.get("hub.verify_token")
    if verify_token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully.")
        return Response(content=request.query_params.get("hub.challenge"), status_code=200)
    logger.warning(f"Webhook verification failed. Invalid token received: {verify_token}")
    raise HTTPException(status_code=403, detail="Invalid verification token")

@app.post("/webhook")
async def handle_webhook(request: Request):
    """Handles incoming messages from WhatsApp."""
    data = await request.json()
    logger.info(f"Received webhook payload: {data}")
    # We are interested in message entries
    if data.get("object") == "whatsapp_business_account":
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") == "messages":
                    for message in change.get("value", {}).get("messages", []):
                        if message.get("type") == "text":
                            await process_text_message(message)
                        elif message.get("type") == "interactive":
                            await process_interactive_message(message)
    return Response(status_code=200)

# --- Message Processing Logic ---
async def process_text_message(message: dict):
    """Processes an incoming text message."""
    from_number = message["from"]
    text = message["text"]["body"]
    user_id = from_number

    logger.info(f"Processing text message from {user_id}: '{text}'")

    if text.lower() in ["привет", "здравствуйте", "start", "/start"]:
        await send_main_menu(from_number)
        return

    # Check user state
    current_state = user_states.get(user_id, {}).get("state")
    if current_state == "ai_consultation":
        await handle_ai_question(user_id, text)
    else:
        # Default behavior if not in a specific state
        await send_main_menu(from_number)

async def send_document(to: str, file_path: str, caption: str):
    """Sends a document using a public URL."""
    file_name = os.path.basename(file_path)
    # Construct the public URL. Assumes the AI server is accessible.
    # The URL will be http://<ai_server_host>:<port>/public/documents/<file_name>
    document_url = f"{AI_SERVER_URL}/public/documents/{file_name}"

    logger.info(f"Sending document to {to} from URL: {document_url}")

    message_data = {
        "type": "document",
        "document": {
            "link": document_url,
            "caption": caption,
            "filename": file_name
        }
    }
    return await send_whatsapp_message(to, message_data)


async def process_interactive_message(message: dict):
    """Processes an incoming interactive message (button press or list reply)."""
    from_number = message["from"]
    user_id = from_number

    interactive_type = message["interactive"]["type"]
    if interactive_type == "button_reply":
        button_id = message["interactive"]["button_reply"]["id"]
        logger.info(f"Processing button press from {user_id}: '{button_id}'")
    elif interactive_type == "list_reply":
        button_id = message["interactive"]["list_reply"]["id"]
        logger.info(f"Processing list selection from {user_id}: '{button_id}'")
    else:
        logger.warning(f"Unknown interactive type: {interactive_type}")
        return

    if button_id == "ai_consultation":
        user_states[user_id] = {"state": "ai_consultation"}
        await send_text_message(from_number, "Вы вошли в режим консультации с AI.\nЗадайте свой вопрос. Для выхода отправьте 'стоп' или 'stop'.")
    elif button_id == "call_center":
        contact_message = (
            "📞 Связаться с колл-центром:\n\n"
            f"💬 WhatsApp: https://wa.me/{CALL_CENTER_WHATSAPP_NUMBER}\n"
            f"✈️ Telegram: https://t.me/{CALL_CENTER_TELEGRAM_USERNAME}"
        )
        await send_text_message(from_number, contact_message)
        await asyncio.sleep(1) # Small delay
        await send_main_menu(from_number)
    elif button_id == "instructions":
        await send_instructions_menu(from_number)
    elif button_id.startswith("instruction_"):
        file_map = {
            "instruction_tech": ("contract.pdf", "Вот техническая документация."),
            "instruction_user": ("instruction_user.pdf", "Вот инструкции для пользователей."),
            "instruction_reg": ("instruction_reg.pdf", "Вот инструкция по регистрации в системе."),
            "instruction_non_resident": ("instruction_non_resident.pdf", "Вот алгоритм для нерезидентов."),
            "instruction_archive": ("archive.rar", "Вот архив с документами."),
        }
        file_info = file_map.get(button_id)
        if file_info:
            file_name, caption = file_info
            await send_document(from_number, file_name, caption)
            await asyncio.sleep(1) # Small delay
            await send_main_menu(from_number) # Return to main menu after
        else:
            await send_text_message(from_number, "Не удалось найти запрошенный документ.")
            await send_main_menu(from_number)
    elif button_id == "main_menu":
        if user_id in user_states:
            del user_states[user_id] # Clear state when returning to menu
        await send_main_menu(from_number)
    else:
        await send_main_menu(from_number) # Default fallback

async def handle_ai_question(user_id: str, question: str):
    """Handles a question directed to the AI server."""
    if question.lower() in ["стоп", "stop", "выход", "exit"]:
        if user_id in user_states:
            del user_states[user_id]
        await send_main_menu(user_id)
        return

    logger.info(f"Sending question from {user_id} to AI server: '{question}'")
    try:
        payload = {"question": question, "user_id": user_id}
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{AI_SERVER_URL}/ask", json=payload, timeout=60) as response:
                response.raise_for_status()
                data = await response.json()
                answer = data.get("content", "Не удалось получить ответ от AI.")
                await send_text_message(user_id, answer)
    except aiohttp.ClientError as e:
        logger.error(f"API Error when contacting AI server: {e}")
        await send_text_message(user_id, "Ошибка: AI-сервер недоступен. Попробуйте позже.")


# --- Main Execution ---
if __name__ == "__main__":
    logger.info("Starting WhatsApp bot server...")
    uvicorn.run(app, host="0.0.0.0", port=8001)