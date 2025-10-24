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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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
        [types.KeyboardButton(text="🤖 Консультация AI")],
        [types.KeyboardButton(text="📄 Просмотр данных"), types.KeyboardButton(text="✍️ Добавить запись")],
        [types.KeyboardButton(text="⚙️ Настройки")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
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

@dp.message(F.text == "🤖 Консультация AI")
async def start_ai_consultation(msg: types.Message, state: FSMContext):
    user_id = msg.from_user.id
    logger.info(f"User {user_id} started AI consultation mode.")

    # Cancel any existing feedback timer for this user
    if user_id in feedback_timers:
        feedback_timers[user_id].cancel()
        del feedback_timers[user_id]
        logger.info(f"Cancelled pending feedback request for user_id={user_id}")

    await state.set_state(Form.ai_consultation)
    await msg.answer(
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


@dp.message(F.text == "📄 Просмотр данных")
async def view_data(msg: types.Message):
    logger.info(f"User {msg.from_user.id} requested to view data.")
    try:
        response = requests.get(f"{AI_SERVER_URL}/records", timeout=15)
        response.raise_for_status()
        records = response.json()
        if records:
            response_text = ""
            for record in records:
                response_text += f"Имя: {record.get('name', 'N/A')}, Телефон: {record.get('phone', 'N/A')}, Email: {record.get('email', 'N/A')}\n"
            await msg.answer(response_text)
        else:
            await msg.answer("В таблице пока нет записей.")
    except requests.exceptions.Timeout:
        logger.error(f"Ошибка API: Таймаут при запросе к {AI_SERVER_URL}")
        await msg.answer("Сервер слишком долго не отвечает. Попробуйте еще раз позже.")
    except requests.exceptions.ConnectionError:
        logger.error(f"Ошибка API: Не удалось подключиться к {AI_SERVER_URL}")
        await msg.answer("Ошибка: AI-сервер недоступен. Свяжитесь с администратором.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка API: {e}")
        await msg.answer("Произошла ошибка при обработке вашего запроса. Попробуйте позже.")

@dp.message(F.text == "✍️ Добавить запись")
async def add_record_start(msg: types.Message, state: FSMContext):
    logger.info(f"User {msg.from_user.id} wants to add a record.")
    await state.set_state(Form.name)
    await msg.answer("Введите имя:")

@dp.message(Form.name)
async def process_name(msg: types.Message, state: FSMContext):
    await state.update_data(name=msg.text)
    await state.set_state(Form.phone)
    await msg.answer("Введите телефон:")

@dp.message(Form.phone)
async def process_phone(msg: types.Message, state: FSMContext):
    await state.update_data(phone=msg.text)
    await state.set_state(Form.email)
    await msg.answer("Введите email:")

@dp.message(Form.email)
async def process_email(msg: types.Message, state: FSMContext):
    await state.update_data(email=msg.text)
    user_data = await state.get_data()
    await state.clear()

    logger.info(f"User {msg.from_user.id} added a record: {user_data}")
    try:
        response = requests.post(f"{AI_SERVER_URL}/records", json=user_data, timeout=15)
        response.raise_for_status()
        await msg.answer("Запись успешно добавлена!", reply_markup=main_menu_keyboard())
    except requests.exceptions.Timeout:
        logger.error(f"Ошибка API: Таймаут при запросе к {AI_SERVER_URL}")
        await msg.answer("Сервер слишком долго не отвечает. Попробуйте еще раз позже.")
    except requests.exceptions.ConnectionError:
        logger.error(f"Ошибка API: Не удалось подключиться к {AI_SERVER_URL}")
        await msg.answer("Ошибка: AI-сервер недоступен. Свяжитесь с администратором.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка API: {e}")
        await msg.answer("Произошла ошибка при добавлении записи. Попробуйте позже.")

@dp.message(F.text == "⚙️ Настройки")
async def settings(msg: types.Message):
    logger.info(f"User {msg.from_user.id} accessed settings.")
    await msg.answer("Раздел настроек находится в разработке.")

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