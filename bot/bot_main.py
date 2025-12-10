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
import os

# --- Logging Setup ---
# Build absolute path for the log file to ensure it works regardless of script launch location
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
log_dir = os.path.join(project_root, 'logs')
os.makedirs(log_dir, exist_ok=True) # Create logs directory if it doesn't exist

log_file = os.path.join(log_dir, 'bot.log')
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
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
    # Main AI consultation states
    ai_consultation = State()
    awaiting_clarification = State()

    # States for new menu navigation
    product_group_selection = State()
    mandatory_marking_selection = State()
    pilot_group_selection = State()

    # Legacy states (can be reviewed for removal if unused)
    question = State()
    name = State()
    phone = State()
    email = State()

# --- Keyboards ---
def main_menu_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🤖 Консультация AI", callback_data="ai_consultation_menu")],
        [InlineKeyboardButton(text="📞 Номер КЦ", callback_data="call_center")],
        [InlineKeyboardButton(text="📚 Инструкции", callback_data="instructions")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def ai_consultation_menu_keyboard():
    """Creates the initial AI consultation menu."""
    buttons = [
        [InlineKeyboardButton(text="ТГ по обязательной маркировке", callback_data="mandatory_marking")],
        [InlineKeyboardButton(text="ТГ по пилотным группам", callback_data="pilot_groups")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def mandatory_marking_keyboard():
    """Keyboard for mandatory marking product groups."""
    buttons = [
        [InlineKeyboardButton(text="Лекарственные средства", callback_data="product_group_Лекарственные средства")],
        [InlineKeyboardButton(text="Табачная продукция", callback_data="product_group_Табачная продукция")],
        [InlineKeyboardButton(text="Обувные товары", callback_data="product_group_Обувные товары")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="ai_consultation_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def pilot_groups_keyboard():
    """Keyboard for pilot product groups."""
    buttons = [
        [InlineKeyboardButton(text="Моторные масла", callback_data="product_group_Моторные масла")],
        [InlineKeyboardButton(text="Пиво", callback_data="product_group_Пиво")],
        [InlineKeyboardButton(text="Ювелирные изделия", callback_data="product_group_Ювелирные изделия")],
        [InlineKeyboardButton(text="БАДы", callback_data="product_group_БАДы")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="ai_consultation_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def call_center_keyboard():
    """Creates the keyboard for the 'Call Center' submenu."""
    # These will be read from config
    from config import CALL_CENTER_WHATSAPP_NUMBER, CALL_CENTER_TELEGRAM_USERNAME
    buttons = [
        [InlineKeyboardButton(text="💬 WhatsApp", url=f"https://wa.me/{CALL_CENTER_WHATSAPP_NUMBER}")],
        [InlineKeyboardButton(text="✈️ Telegram", url=f"https://t.me/+{CALL_CENTER_TELEGRAM_USERNAME}")],
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
        [InlineKeyboardButton(text="Архив с документами", callback_data="instruction_archive")],
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

# --- New Handlers for AI Consultation Menu ---

# Handler for the "AI Consultation" button from the main menu -> Shows product group categories
@dp.callback_query(F.data == "ai_consultation_menu")
async def show_ai_consultation_menu(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.product_group_selection)
    await callback_query.message.edit_text(
        "Выберите категорию товарной группы:",
        reply_markup=ai_consultation_menu_keyboard()
    )
    await callback_query.answer()

# Handler to show the Mandatory Marking product groups
@dp.callback_query(F.data == "mandatory_marking", Form.product_group_selection)
async def show_mandatory_marking_menu(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.mandatory_marking_selection)
    await callback_query.message.edit_text(
        "Выберите товарную группу (Обязательная маркировка):",
        reply_markup=mandatory_marking_keyboard()
    )
    await callback_query.answer()

# Handler to show the Pilot Product groups
@dp.callback_query(F.data == "pilot_groups", Form.product_group_selection)
async def show_pilot_groups_menu(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.pilot_group_selection)
    await callback_query.message.edit_text(
        "Выберите товарную группу (Пилотные группы):",
        reply_markup=pilot_groups_keyboard()
    )
    await callback_query.answer()

# Handler for when a user selects a specific product group
@dp.callback_query(F.data.startswith("product_group_"))
async def select_product_group(callback_query: types.CallbackQuery, state: FSMContext):
    product_group = callback_query.data.split("product_group_")[1]
    await state.update_data(product_group=product_group)
    await state.set_state(Form.ai_consultation)

    user_id = callback_query.from_user.id
    logger.info(f"User {user_id} selected product group '{product_group}' and started AI consultation.")

    # Cancel any existing feedback timer
    if user_id in feedback_timers:
        feedback_timers[user_id].cancel()
        del feedback_timers[user_id]
        logger.info(f"Cancelled pending feedback request for user_id={user_id}")

    await callback_query.message.edit_text(
        f"Вы выбрали: <b>{product_group}</b>.\n"
        "Теперь вы можете задавать вопросы по этой теме.\n\n"
        "Чтобы выйти, нажмите кнопку ниже.",
        parse_mode="HTML",
    )
    # Also send a new message with the reply keyboard for exiting
    await callback_query.message.answer("↓", reply_markup=consultation_keyboard())
    await callback_query.answer()

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

# This handler catches any message when the user is in consultation mode
@dp.message(Form.ai_consultation, F.text)
async def process_ai_question(msg: types.Message, state: FSMContext):
    user_question = msg.text
    user_data = await state.get_data()
    product_group = user_data.get("product_group", "Не указана") # Default fallback

    # Prepend the context to the user's question
    question_with_context = f"Товарная группа: {product_group}. Вопрос: {user_question}"

    logger.info(f"User {msg.from_user.id} asked (with context): {question_with_context}")

    await bot.send_chat_action(msg.chat.id, 'typing')

    try:
        payload = {
            "question": question_with_context,
            "user_id": str(msg.from_user.id)
        }
        response = requests.post(f"{AI_SERVER_URL}/ask", json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        response_type = data.get("type")
        content = data.get("content")

        if response_type == "clarification":
            # Store the original question with its context
            await state.update_data(original_question=question_with_context)
            await state.set_state(Form.awaiting_clarification)
            await msg.answer(content)
            logger.info(f"Sent clarification request to user {msg.from_user.id}. New state: awaiting_clarification.")
        elif response_type == "answer":
            await msg.answer(content)
        else:
            await msg.answer("Получен неожиданный ответ от сервера. Попробуйте позже.")

    except requests.exceptions.Timeout:
        logger.error(f"API Error: Timeout when requesting {AI_SERVER_URL}")
        await msg.answer("Сервер слишком долго не отвечает. Попробуйте еще раз позже.")
    except requests.exceptions.ConnectionError:
        logger.error(f"API Error: Could not connect to {AI_SERVER_URL}")
        await msg.answer("Ошибка: AI-сервер недоступен. Свяжитесь с администратором.")
    except requests.exceptions.RequestException as e:
        logger.error(f"API Error: {e}")
        await msg.answer("Произошла ошибка при обработке вашего запроса. Попробуйте позже.")


# Handler for when the bot is waiting for the user to clarify their ambiguous question
@dp.message(Form.awaiting_clarification, F.text)
async def process_clarification(msg: types.Message, state: FSMContext):
    clarification_text = msg.text
    user_data = await state.get_data()
    original_question = user_data.get('original_question')

    if not original_question:
        await msg.answer("Произошла ошибка: не удалось найти ваш исходный вопрос. Пожалуйста, задайте его снова.")
        await state.set_state(Form.ai_consultation)
        return

    # Combine the original question with the user's clarification
    enriched_question = f"{original_question} (уточнение: {clarification_text})"

    logger.info(f"User {msg.from_user.id} provided clarification. New enriched query: {enriched_question}")

    await bot.send_chat_action(msg.chat.id, 'typing')

    # Return to the main consultation state to process the new query
    await state.set_state(Form.ai_consultation)

    try:
        payload = {
            "question": enriched_question,
            "user_id": str(msg.from_user.id)
        }
        response = requests.post(f"{AI_SERVER_URL}/ask", json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        # By now, the answer should be direct and not a clarification
        await msg.answer(data.get("content", "Не удалось получить окончательный ответ от сервера."))

    except requests.exceptions.Timeout:
        logger.error(f"API Error: Timeout when requesting enriched answer from {AI_SERVER_URL}")
        await msg.answer("Сервер не ответил вовремя. Попробуйте задать вопрос еще раз.")
    except requests.exceptions.RequestException as e:
        logger.error(f"API Error on enriched query: {e}")
        await msg.answer("Произошла ошибка при обработке вашего уточненного запроса.")


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
        "instruction_archive": ("documents/archive.rar", "Вот архив с документами."),
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