# bot/bot_main.py

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import sys
import os

# Добавляем корневую папку в sys.path, чтобы импортировать config.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from config import TELEGRAM_TOKEN, AI_API_URL
except ImportError:
    print("Ошибка: Не найден файл config.py.")
    print("Убедитесь, что вы создали config.py в корневой папке проекта.")
    sys.exit(1)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# Используем простой словарь для FSM (Finite State Machine)
# Храним состояние пользователя, например, "ждет_вопроса"
user_states = {}

# --- Кнопки ---
def main_menu_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("🤖 Консультация AI")
    keyboard.add("☎️ Связь с КЦ", "📄 Типовой договор")
    return keyboard

# --- Обработчики ---
@dp.message_handler(commands=["start"])
async def cmd_start(msg: types.Message):
    user_states[msg.from_user.id] = None # Сброс состояния
    await msg.answer(
        "Здравствуйте! Я ваш AI-ассистент по маркировке. Выберите действие:",
        reply_markup=main_menu_keyboard()
    )

@dp.message_handler(lambda msg: msg.text == "🤖 Консультация AI")
async def ask_ai(msg: types.Message):
    # Устанавливаем состояние "ждем вопроса"
    user_states[msg.from_user.id] = "awaiting_question"
    await msg.answer("Пожалуйста, задайте ваш вопрос:")

@dp.message_handler(lambda msg: msg.text == "☎️ Связь с КЦ")
async def contact_support(msg: types.Message):
    user_states[msg.from_user.id] = None
    await msg.answer("Контакты КЦ: +7 (XXX) XXX-XX-XX, support@example.kz")
    
@dp.message_handler(lambda msg: msg.text == "📄 Типовой договор")
async def send_contract(msg: types.Message):
    user_states[msg.from_user.id] = None
    # Файл должен лежать в папке /bot/
    contract_path = os.path.join(os.path.dirname(__file__), 'contract.pdf')
    try:
        with open(contract_path, "rb") as doc:
            await msg.answer_document(doc, caption="Типовой договор")
    except FileNotFoundError:
        await msg.answer("Файл договора ('contract.pdf') не найден на сервере.")

# --- Обработка вопроса к AI ---
@dp.message_handler(lambda msg: user_states.get(msg.from_user.id) == "awaiting_question")
async def handle_ai_question(msg: types.Message):
    user_states[msg.from_user.id] = None # Сброс состояния
    question = msg.text
    
    await msg.answer("⏳ Ищу ответ... Пожалуйста, подождите.")
    
    try:
        # Запрос к нашему FastAPI серверу
        response = requests.post(AI_API_URL, json={"question": question})
        response.raise_for_status() # Проверка на http ошибки (4xx, 5xx)
        
        data = response.json()
        await msg.answer(data['answer'])
    
    except requests.exceptions.ConnectionError:
        print(f"Ошибка API: Не удалось подключиться к {AI_API_URL}")
        await msg.answer("Ошибка: AI-сервер недоступен. Свяжитесь с администратором.")
    except requests.exceptions.RequestException as e:
        print(f"Ошибка API: {e}")
        await msg.answer("Произошла ошибка при обработке вашего запроса. Попробуйте позже.")
    
    await msg.answer("Могу помочь чем-то еще?", reply_markup=main_menu_keyboard())

# --- Обработка любого другого текста ---
@dp.message_handler()
async def other_text(msg: types.Message):
    await msg.answer("Пожалуйста, используйте кнопки меню или задайте вопрос в режиме 'Консультация AI'.", 
                     reply_markup=main_menu_keyboard())

if __name__ == "__main__":
    print("Бот запускается...")
    executor.start_polling(dp, skip_updates=True)