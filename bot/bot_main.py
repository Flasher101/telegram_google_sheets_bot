# bot/bot_main.py

import aiohttp
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
call_center_rating_timers = {}
call_center_reminder_timers = {}

class Form(StatesGroup):
    ai_consultation = State()
    awaiting_clarification = State() # State for when the bot is waiting for user to clarify their question
    awaiting_cc_feedback = State()
    question = State()
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
    from config import CALL_CENTER_WHATSAPP_NUMBER, CALL_CENTER_TELEGRAM_NUMBER
    buttons = [
        [InlineKeyboardButton(text="💬 WhatsApp", url=f"https://wa.me/{CALL_CENTER_WHATSAPP_NUMBER}")],
        [InlineKeyboardButton(text="✈️ Telegram", url=f"https://t.me/+{CALL_CENTER_TELEGRAM_NUMBER}")],
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

def call_center_rating_keyboard():
    """Keyboard for rating call center service (1-5 stars)"""
    buttons = [
        [
            InlineKeyboardButton(text="⭐ 1", callback_data="cc_rating_1"),
            InlineKeyboardButton(text="⭐⭐ 2", callback_data="cc_rating_2"),
            InlineKeyboardButton(text="⭐⭐⭐ 3", callback_data="cc_rating_3"),
            InlineKeyboardButton(text="⭐⭐⭐⭐ 4", callback_data="cc_rating_4"),
            InlineKeyboardButton(text="⭐⭐⭐⭐⭐ 5", callback_data="cc_rating_5")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def skip_feedback_keyboard():
    """Keyboard to skip providing feedback comment"""
    buttons = [
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_cc_feedback")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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

async def schedule_call_center_reminder(user_id: int, chat_id: int):
    """Schedules a reminder for call center rating after 24 hours."""
    try:
        await asyncio.sleep(86400) # 24 hours
        if user_id in call_center_reminder_timers:
            logger.info(f"Sending call center rating REMINDER to chat_id={chat_id}")
            await bot.send_message(
                chat_id,
                "Здравствуйте! Напоминаем вам о возможности оценить ваше недавнее обращение в наш контакт-центр.\n"
                "Ваше мнение очень важно для нас:",
                reply_markup=call_center_rating_keyboard()
            )
            del call_center_reminder_timers[user_id]
    except asyncio.CancelledError:
        logger.info(f"Call center rating reminder cancelled for user_id={user_id}")


async def schedule_call_center_rating(user_id: int, chat_id: int):
    """Schedules a call center rating request to be sent after 3 hours and schedules a reminder."""
    try:
        await asyncio.sleep(10800)  # 3 hours
        if user_id in call_center_rating_timers:
            logger.info(f"Sending call center rating request to chat_id={chat_id}")
            await bot.send_message(
                chat_id,
                "Здравствуйте! Вы недавно обращались в наш контакт-центр.\n"
                "Пожалуйста, оцените качество обслуживания:",
                reply_markup=call_center_rating_keyboard()
            )
            # Once the initial request is sent, schedule the reminder
            del call_center_rating_timers[user_id]
            reminder_task = asyncio.create_task(schedule_call_center_reminder(user_id, chat_id))
            call_center_reminder_timers[user_id] = reminder_task
            logger.info(f"Scheduled call center rating REMINDER for user_id={user_id} in 24 hours")

    except asyncio.CancelledError:
        logger.info(f"Call center rating timer cancelled for user_id={user_id}")

async def send_rating_to_server(user_id: int, rating: int, comment: str, timestamp):
    """Sends rating data to the AI server"""
    try:
        payload = {
            "user_id": str(user_id),
            "rating": rating,
            "comment": comment,
            "timestamp": str(timestamp)
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{AI_SERVER_URL}/rating",
                json=payload,
                timeout=15
            ) as response:
                response.raise_for_status()
                logger.info(
                    f"Call center rating sent to server for user_id={user_id} "
                    f"(rating={rating}, has_comment={comment is not None})"
                )
                return True
    except aiohttp.ClientError as e:
        logger.error(f"Failed to send rating to server for user_id={user_id}: {e}")
        return False
    except Exception as e:
        logger.critical(f"Unexpected error in send_rating_to_server: {e}", exc_info=True)
        return False

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

# This handler catches any message when the user is in consultation mode
@dp.message(Form.ai_consultation, F.text)
async def process_ai_question(msg: types.Message, state: FSMContext):
    question_text = msg.text
    logger.info(f"User {msg.from_user.id} (in consultation mode) asked: {question_text}")

    await bot.send_chat_action(msg.chat.id, 'typing')

    try:
        payload = {
            "question": question_text,
            "user_id": str(msg.from_user.id)
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{AI_SERVER_URL}/ask", json=payload, timeout=60) as response:
                response.raise_for_status()
                data = await response.json()

                response_type = data.get("type")
                content = data.get("content")

                if response_type == "clarification":
                    await state.update_data(original_question=question_text)
                    await state.set_state(Form.awaiting_clarification)
                    await msg.answer(content)
                    logger.info(f"Sent clarification request to user {msg.from_user.id}. New state: awaiting_clarification.")
                elif response_type == "answer":
                    await msg.answer(content)
                else:
                    await msg.answer("Получен неожиданный ответ от сервера. Попробуйте позже.")

    except aiohttp.ClientError as e:
        logger.error(f"API Error: {e}")
        await msg.answer("Произошла ошибка при обработке вашего запроса. Попробуйте позже.")
    except asyncio.TimeoutError:
        logger.error(f"API Error: Timeout when requesting {AI_SERVER_URL}")
        await msg.answer("Сервер слишком долго не отвечает. Попробуйте еще раз позже.")


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
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{AI_SERVER_URL}/ask", json=payload, timeout=60) as response:
                response.raise_for_status()
                data = await response.json()
                await msg.answer(data.get("content", "Не удалось получить окончательный ответ от сервера."))

    except aiohttp.ClientError as e:
        logger.error(f"API Error on enriched query: {e}")
        await msg.answer("Произошла ошибка при обработке вашего уточненного запроса.")
    except asyncio.TimeoutError:
        logger.error(f"API Error: Timeout when requesting enriched answer from {AI_SERVER_URL}")
        await msg.answer("Сервер не ответил вовремя. Попробуйте задать вопрос еще раз.")


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
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{AI_SERVER_URL}/feedback", json=payload, timeout=15) as response:
                response.raise_for_status()
                logger.info(f"Feedback successfully sent to AI server for user_id={user_id}")
    except aiohttp.ClientError as e:
        logger.error(f"Failed to send feedback to AI server for user_id={user_id}: {e}")

    # Thank the user and remove the inline keyboard
    await callback_query.message.edit_text("Спасибо за ваш отзыв!")
    await callback_query.answer()


# --- New Callback Handlers for Submenus ---

@dp.callback_query(F.data == "call_center")
async def show_call_center_menu(callback_query: types.CallbackQuery):
    """Shows the call center contact submenu and schedules rating request."""
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id

    # Cancel any previously scheduled initial request
    if user_id in call_center_rating_timers:
        if not call_center_rating_timers[user_id].done():
            call_center_rating_timers[user_id].cancel()
        del call_center_rating_timers[user_id]
        logger.info(f"Cancelled pending initial call center rating for user_id={user_id}")

    # Cancel any previously scheduled reminder
    if user_id in call_center_reminder_timers:
        if not call_center_reminder_timers[user_id].done():
            call_center_reminder_timers[user_id].cancel()
        del call_center_reminder_timers[user_id]
        logger.info(f"Cancelled pending call center rating reminder for user_id={user_id}")

    # Schedule a new initial request
    task = asyncio.create_task(schedule_call_center_rating(user_id, chat_id))
    call_center_rating_timers[user_id] = task
    logger.info(f"Scheduled initial call center rating for user_id={user_id} in 3 hours")

    await callback_query.message.edit_text(
        "Выберите способ связи:",
        reply_markup=call_center_keyboard()
    )
    await callback_query.answer()

@dp.callback_query(F.data.startswith("cc_rating_"))
async def process_call_center_rating(callback_query: types.CallbackQuery, state: FSMContext):
    """Processes call center rating feedback"""
    rating = callback_query.data.split("_")[-1]
    user_id = callback_query.from_user.id
    logger.info(f"Received call center rating '{rating}' from user_id={user_id}")

    # Cancel a pending reminder task if it exists
    if user_id in call_center_reminder_timers:
        if not call_center_reminder_timers[user_id].done():
            call_center_reminder_timers[user_id].cancel()
        del call_center_reminder_timers[user_id]
        logger.info(f"User {user_id} responded to feedback, reminder cancelled.")

    await state.update_data(cc_rating=int(rating))

    if int(rating) <= 2:
        await state.set_state(Form.awaiting_cc_feedback)
        await callback_query.message.edit_text(
            f"Спасибо за вашу оценку ({rating} ⭐).\n\n"
            "Нам очень важно понять, что пошло не так.\n"
            "Пожалуйста, опишите подробнее, что вам не понравилось в обслуживании:",
            reply_markup=skip_feedback_keyboard()
        )
        await callback_query.answer()
        logger.info(f"User {user_id} gave low rating, waiting for feedback comment")
        return

    await send_rating_to_server(user_id, int(rating), None, callback_query.message.date)

    if int(rating) >= 4:
        thank_you_message = f"Спасибо за высокую оценку! ⭐ {rating}\nМы рады, что смогли вам помочь!"
    else:
        thank_you_message = f"Спасибо за вашу оценку! ⭐ {rating}\nМы работаем над улучшением нашего сервиса."

    await callback_query.message.edit_text(thank_you_message)
    await callback_query.answer()
    await state.clear()

@dp.message(Form.awaiting_cc_feedback, F.text)
async def process_cc_feedback_comment(msg: types.Message, state: FSMContext):
    """Processes the feedback comment from user after low rating"""
    user_id = msg.from_user.id
    # Cancel a pending reminder task if it exists
    if user_id in call_center_reminder_timers:
        if not call_center_reminder_timers[user_id].done():
            call_center_reminder_timers[user_id].cancel()
        del call_center_reminder_timers[user_id]
        logger.info(f"User {user_id} provided comment, reminder cancelled.")

    user_data = await state.get_data()
    rating = user_data.get('cc_rating')
    comment = msg.text

    logger.info(f"User {msg.from_user.id} provided feedback comment for rating {rating}")

    await send_rating_to_server(msg.from_user.id, rating, comment, msg.date)

    await msg.answer(
        "Спасибо за ваш отзыв! 🙏\n\n"
        "Мы обязательно учтём ваши замечания и постараемся улучшить качество обслуживания.\n"
        "Ваше мнение очень важно для нас!",
        reply_markup=types.ReplyKeyboardRemove()
    )

    await state.clear()

@dp.callback_query(F.data == "skip_cc_feedback", Form.awaiting_cc_feedback)
async def skip_cc_feedback_comment(callback_query: types.CallbackQuery, state: FSMContext):
    """Handles when user skips providing feedback comment"""
    user_data = await state.get_data()
    rating = user_data.get('cc_rating')
    user_id = callback_query.from_user.id

    # Cancel a pending reminder task if it exists
    if user_id in call_center_reminder_timers:
        if not call_center_reminder_timers[user_id].done():
            call_center_reminder_timers[user_id].cancel()
        del call_center_reminder_timers[user_id]
        logger.info(f"User {user_id} skipped comment, reminder cancelled.")

    logger.info(f"User {user_id} skipped feedback comment for rating {rating}")

    await send_rating_to_server(user_id, rating, None, callback_query.message.date)

    await callback_query.message.edit_text(
        "Спасибо за вашу оценку! 🙏\n\n"
        "Мы постараемся улучшить качество нашего обслуживания."
    )
    await callback_query.answer()
    await state.clear()

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
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        logger.info("Shutting down bot...")

        for chat_id, task in feedback_timers.items():
            if not task.done():
                task.cancel()

        for user_id, task in call_center_rating_timers.items():
            if not task.done():
                task.cancel()

        for user_id, task in call_center_reminder_timers.items():
            if not task.done():
                task.cancel()

        await bot.session.close()
        logger.info("Bot shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")