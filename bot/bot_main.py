# bot/bot_main.py

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
import sys
import os
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
    from ai_server.g_sheets import get_all_records, add_record
except ImportError:
    logger.critical("Ошибка: Не найден файл config.py или ошибка импорта.")
    logger.critical("Убедитесь, что вы создали config.py в корневой папке проекта.")
    sys.exit(1)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class Form(StatesGroup):
    question = State()
    name = State()
    phone = State()
    email = State()

# --- Кнопки ---
def main_menu_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("🤖 Консультация AI")
    keyboard.add("📄 Просмотр данных", "✍️ Добавить запись")
    keyboard.add("⚙️ Настройки")
    return keyboard

# --- Обработчики ---
@dp.message_handler(commands=["start"])
async def cmd_start(msg: types.Message):
    logger.info(f"User {msg.from_user.id} started the bot.")
    await msg.answer(
        "Здравствуйте! Я ваш AI-ассистент. Выберите действие:",
        reply_markup=main_menu_keyboard()
    )

@dp.message_handler(commands=["help"])
async def cmd_help(msg: types.Message):
    logger.info(f"User {msg.from_user.id} requested help.")
    await msg.answer(
        "Доступные команды:\n"
        "/start - начать работу\n"
        "/help - показать это сообщение\n"
    )

@dp.message_handler(Text(equals="🤖 Консультация AI"))
async def ask_ai(msg: types.Message):
    logger.info(f"User {msg.from_user.id} wants to ask a question.")
    await msg.answer("Пожалуйста, задайте ваш вопрос:")
    await Form.question.set()

@dp.message_handler(state=Form.question)
async def process_question(msg: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['question'] = msg.text
    await state.finish()

    logger.info(f"User {msg.from_user.id} asked: {data['question']}")
    await msg.answer("⏳ Ищу ответ... Пожалуйста, подождите.")

    try:
        response = requests.post(AI_SERVER_URL, json={"question": data['question']})
        response.raise_for_status()

        data = response.json()
        await msg.answer(data['answer'])

    except requests.exceptions.ConnectionError:
        logger.error(f"Ошибка API: Не удалось подключиться к {AI_SERVER_URL}")
        await msg.answer("Ошибка: AI-сервер недоступен. Свяжитесь с администратором.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка API: {e}")
        await msg.answer("Произошла ошибка при обработке вашего запроса. Попробуйте позже.")

    await msg.answer("Могу помочь чем-то еще?", reply_markup=main_menu_keyboard())

@dp.message_handler(Text(equals="📄 Просмотр данных"))
async def view_data(msg: types.Message):
    logger.info(f"User {msg.from_user.id} requested to view data.")
    records = get_all_records()
    if records:
        response = ""
        for record in records:
            response += f"Имя: {record['name']}, Телефон: {record['phone']}, Email: {record['email']}\\n"
        await msg.answer(response)
    else:
        await msg.answer("В таблице пока нет записей.")

@dp.message_handler(Text(equals="✍️ Добавить запись"))
async def add_record_start(msg: types.Message):
    logger.info(f"User {msg.from_user.id} wants to add a record.")
    await Form.name.set()
    await msg.answer("Введите имя:")

@dp.message_handler(state=Form.name)
async def process_name(msg: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['name'] = msg.text
    await Form.next()
    await msg.answer("Введите телефон:")

@dp.message_handler(state=Form.phone)
async def process_phone(msg: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['phone'] = msg.text
    await Form.next()
    await msg.answer("Введите email:")

@dp.message_handler(state=Form.email)
async def process_email(msg: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['email'] = msg.text

    logger.info(f"User {msg.from_user.id} added a record: {data}")
    add_record(data['name'], data['phone'], data['email'])
    await msg.answer("Запись успешно добавлена!", reply_markup=main_menu_keyboard())
    await state.finish()

@dp.message_handler(Text(equals="⚙️ Настройки"))
async def settings(msg: types.Message):
    logger.info(f"User {msg.from_user.id} accessed settings.")
    await msg.answer("Раздел настроек находится в разработке.")

if __name__ == "__main__":
    logger.info("Бот запускается...")
    executor.start_polling(dp, skip_updates=True)