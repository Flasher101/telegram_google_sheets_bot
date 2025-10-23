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

class Form(StatesGroup):
    question = State()
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
async def ask_ai(msg: types.Message, state: FSMContext):
    logger.info(f"User {msg.from_user.id} wants to ask a question.")
    await state.set_state(Form.question)
    await msg.answer("Пожалуйста, задайте ваш вопрос:")

@dp.message(Form.question)
async def process_question(msg: types.Message, state: FSMContext):
    question_text = msg.text
    await state.clear()

    logger.info(f"User {msg.from_user.id} asked: {question_text}")
    await msg.answer("⏳ Ищу ответ... Пожалуйста, подождите.")

    try:
        response = requests.post(f"{AI_SERVER_URL}/ask", json={"question": question_text}, timeout=30)
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

    await msg.answer("Могу помочь чем-то еще?", reply_markup=main_menu_keyboard())

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