# bot/bot_main.py

import requests
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import sys
import logging
from logging.handlers import RotatingFileHandler
import asyncio
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

# --- Logging Setup ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_file = 'logs/bot.log'
log_handler = RotatingFileHandler(log_file, maxBytes=1024*1024*5, backupCount=5)
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(logging.StreamHandler())

try:
    from config import TELEGRAM_BOT_TOKEN, AI_SERVER_URL
except ImportError:
    logger.critical("Ошибка: Не найден файл config.py или ошибка импорта.")
    logger.critical("Убедитесь, что вы создали config.py в корневой папке проекта.")
    sys.exit(1)

# --- Bot and Dispatcher Setup ---
storage = MemoryStorage()
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=storage)

# Dictionary to keep track of feedback timers for each user
feedback_timers = {}

class Form(StatesGroup):
    ai_consultation = State() # Новый стейт для режима консультации
    question = State() # Этот стейт больше не будет использоваться для AI, но оставим для обратной совместимости или других целей
    name = State()
    phone = State()
    email = State()

# --- Keyboards ---
def main_menu_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🤖 Консультация AI", callback_data="ai_consultation")],
        [InlineKeyboardButton(text="📞 Номер КЦ", callback_data="call_center")],
        [InlineKeyboardButton(text="📚 Инструкции", callback_data="instructions")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def call_center_keyboard():
    """Creates the keyboard for the 'Call Center' submenu."""
    # These will be read from config
    from config import CALL_CENTER_WHATSAPP_NUMBER, CALL_CENTER_TELEGRAM_USERNAME
    buttons = [
        [InlineKeyboardButton(text="💬 WhatsApp", url=f"https://wa.me/{CALL_CENTER_WHATSAPP_NUMBER}")],
        [InlineKeyboardButton(text="✈️ Telegram", url=f"https://t.me/{CALL_CENTER_TELEGRAM_USERNAME}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def instructions_keyboard():
    """Creates the keyboard for the 'Instructions' submenu."""
    video_url = "https://www.youtube.com/watch?v=yMadR9ITo9I&list=PL3JrZkZtKh8DhCWvpsrHUdI9tZWkoqr9Z"
    buttons = [
        [InlineKeyboardButton(text="Видеоинструкции", url=video_url)],
        [InlineKeyboardButton(text="Техническая документация", callback_data="instruction_tech")],
        [InlineKeyboardButton(text="Инструкции пользователей", callback_data="instruction_user")],
        [InlineKeyboardButton(text="Регистрация в системе", callback_data="instruction_reg")],
        [InlineKeyboardButton(text="Алгоритм для не резидентов", callback_data="instruction_non_resident")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def consultation_keyboard():
    buttons = [
        [types.KeyboardButton(text="⬅️ Вернуться в главное меню")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard

def feedback_keyboard():
    buttons = [
        [
            InlineKeyboardButton(text="👍 Помогло", callback_data="feedback_good"),
            InlineKeyboardButton(text="👎 Не помогло", callback_data="feedback_bad")
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

async def schedule_feedback(chat_id: int):
    """Schedules a feedback message to be sent after a delay."""
    await asyncio.sleep(600)  # 10 minutes
    if chat_id in feedback_timers:
        logger.info(f"Sending feedback request to chat_id={chat_id}")
        await bot.send_message(
            chat_id,
            "Пожалуйста, оцените последний ответ AI:",
            reply_markup=feedback_keyboard()
        )
        # Remove the timer once the message is sent
        del feedback_timers[chat_id]

# --- Handlers ---
@dp.message(Command("start"))
async def cmd_start(msg: types.Message, state: FSMContext):
    logger.info(f"User {msg.from_user.id} started the bot.")
    await state.clear()
    # Now we send the message with an inline keyboard
    await msg.answer(
        "Здравствуйте! Я ваш AI-ассистент. Выберите действие:",
        reply_markup=main_menu_keyboard()
    )

@dp.message(Command("help"))
async def cmd_help(msg: types.Message):
    logger.info(f"User {msg.from_user.id} requested help.")
    await msg.answer(
        "Доступные команды:\n"
        "/start - начать работу\n"
        "/help - показать это сообщение\n"
    )

# Handler for the "AI Consultation" button from the main menu
@dp.callback_query(F.data == "ai_consultation")
async def start_ai_consultation(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    logger.info(f"User {user_id} started AI consultation mode via inline button.")
    await callback_query.answer() # Acknowledge the button press

    # Cancel any existing feedback timer for this user
    if user_id in feedback_timers:
        feedback_timers[user_id].cancel()
        del feedback_timers[user_id]
        logger.info(f"Cancelled pending feedback request for user_id={user_id}")

    await state.set_state(Form.ai_consultation)
    # Use callback_query.message.answer to reply
    await callback_query.message.answer(
        "Вы вошли в режим консультации с AI.\n"
        "Теперь вы можете задавать вопросы без остановки.\n\n"
        "Чтобы выйти, нажмите кнопку ниже.",
        reply_markup=consultation_keyboard()
    )

# Handler for the "Return to main menu" button
@dp.message(F.text == "⬅️ Вернуться в главное меню", Form.ai_consultation)
async def stop_consultation(msg: types.Message, state: FSMContext):
    user_id = msg.from_user.id
    logger.info(f"User {user_id} stopped AI consultation mode via button.")
    await state.clear()

    # Schedule the feedback message
    task = asyncio.create_task(schedule_feedback(user_id))
    feedback_timers[user_id] = task
    logger.info(f"Scheduled feedback request for user_id={user_id}")

    await msg.answer(
        "Вы вышли из режима консультации.\n"
        "Чем могу помочь?",
        reply_markup=main_menu_keyboard()
    )

# Этот хендлер теперь будет ловить любые сообщения, пока пользователь в режиме консультации
@dp.message(Form.ai_consultation, F.text)
async def process_ai_question(msg: types.Message, state: FSMContext):
    question_text = msg.text
    logger.info(f"User {msg.from_user.id} (in consultation mode) asked: {question_text}")

    # Показываем индикатор "печатает..."
    await bot.send_chat_action(msg.chat.id, 'typing')

    try:
        # Теперь отправляем и user_id для аналитики
        payload = {
            "question": question_text,
            "user_id": str(msg.from_user.id) # Убедимся, что ID это строка
        }
        response = requests.post(f"{AI_SERVER_URL}/ask", json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        await msg.answer(data.get('answer', 'Не удалось получить ответ от сервера.'))

    except requests.exceptions.Timeout:
        logger.error(f"Ошибка API: Таймаут при запросе к {AI_SERVER_URL}")
        await msg.answer("Сервер слишком долго не отвечает. Попробуйте еще раз позже.")
    except requests.exceptions.ConnectionError:
        logger.error(f"Ошибка API: Не удалось подключиться к {AI_SERVER_URL}")
        await msg.answer("Ошибка: AI-сервер недоступен. Свяжитесь с администратором.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка API: {e}")
        await msg.answer("Произошла ошибка при обработке вашего запроса. Попробуйте позже.")

    # Стейт не сбрасываем, пользователь может продолжать задавать вопросы


# Старый обработчик вопроса (больше не используется, можно удалить)
# @dp.message(Form.question)
# async def process_question(msg: types.Message, state: FSMContext):
# ... (код старого обработчика)


@dp.callback_query(F.data.startswith("feedback_"))
async def process_feedback(callback_query: types.CallbackQuery):
    feedback_type = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id
    logger.info(f"Received feedback '{feedback_type}' from user_id={user_id}")

    # Send feedback to the AI server
    try:
        payload = {"user_id": str(user_id), "feedback": feedback_type}
        response = requests.post(f"{AI_SERVER_URL}/feedback", json=payload, timeout=15)
        response.raise_for_status()
        logger.info(f"Feedback successfully sent to AI server for user_id={user_id}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send feedback to AI server for user_id={user_id}: {e}")

    # Thank the user and remove the inline keyboard
    await callback_query.message.edit_text("Спасибо за ваш отзыв!")
    await callback_query.answer()


# --- New Callback Handlers for Submenus ---

@dp.callback_query(F.data == "call_center")
async def show_call_center_menu(callback_query: types.CallbackQuery):
    """Shows the call center contact submenu."""
    await callback_query.message.edit_text(
        "Выберите способ связи:",
        reply_markup=call_center_keyboard()
    )
    await callback_query.answer()

@dp.callback_query(F.data == "instructions")
async def show_instructions_menu(callback_query: types.CallbackQuery):
    """Shows the instructions submenu."""
    await callback_query.message.edit_text(
        "Выберите раздел инструкций:",
        reply_markup=instructions_keyboard()
    )
    await callback_query.answer()

@dp.callback_query(F.data == "main_menu")
async def return_to_main_menu(callback_query: types.CallbackQuery):
    """Returns the user to the main menu."""
    await callback_query.message.edit_text(
        "Здравствуйте! Я ваш AI-ассистент. Выберите действие:",
        reply_markup=main_menu_keyboard()
    )
    await callback_query.answer()

# --- Handlers for Instructions ---

@dp.callback_query(F.data.startswith("instruction_"))
async def send_instruction_document(callback_query: types.CallbackQuery):
    """Handles all instruction buttons and sends the corresponding document."""
    file_map = {
        "instruction_tech": ("documents/contract.pdf", "Вот техническая документация."),
        "instruction_user": ("documents/instruction_user.pdf", "Вот инструкции для пользователей."),
        "instruction_reg": ("documents/instruction_reg.pdf", "Вот инструкция по регистрации в системе."),
        "instruction_non_resident": ("documents/instruction_non_resident.pdf", "Вот алгоритм для нерезидентов."),
    }

    file_info = file_map.get(callback_query.data)

    if not file_info:
        await callback_query.answer("Неизвестная команда.", show_alert=True)
        return

    file_path, caption = file_info

    try:
        await bot.send_chat_action(callback_query.message.chat.id, 'upload_document')
        document = FSInputFile(file_path, filename=file_path.split('/')[-1])
        await callback_query.message.answer_document(
            document,
            caption=caption
        )
        await callback_query.answer()
    except FileNotFoundError:
        logger.error(f"File not found at path: {file_path} for instruction {callback_query.data}")
        await callback_query.answer(
            "Файл с документацией не найден. Обратитесь к администратору.",
            show_alert=True
        )
    except Exception as e:
        logger.error(f"Error sending document for instruction {callback_query.data}: {e}")
        await callback_query.answer(
            "Произошла ошибка при отправке файла.",
            show_alert=True
        )

async def main():
    logger.info("Бот запускается...")
    # This will skip updates which were sent when the bot was offline
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")