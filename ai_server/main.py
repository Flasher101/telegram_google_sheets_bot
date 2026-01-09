# ai_server/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ai_server.g_sheets import get_all_records, get_user_records, add_record, log_question, log_feedback, log_call_center_feedback
from ai_server.vector_store import build_or_load_index, search_index
import threading
import time
import uvicorn
import logging
from logging.handlers import RotatingFileHandler

# --- Logging Setup ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_file = 'logs/ai_server.log'
log_handler = RotatingFileHandler(log_file, maxBytes=1024*1024*5, backupCount=5)
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(logging.StreamHandler())

app = FastAPI(title="AI Server (Google Sheets + FAISS)")

class Query(BaseModel):
    question: str
    user_id: str = "unknown" # Add user_id to the query model

class Record(BaseModel):
    name: str
    phone: str
    email: str

class Feedback(BaseModel):
    user_id: str
    feedback: str # "good" or "bad"

class CallCenterRating(BaseModel):
    user_id: str
    rating: int
    comment: str = None
    timestamp: str

def update_index_periodically():
    """Фоновая задача для обновления индекса раз в час"""
    while True:
        time.sleep(3600)
        logger.info("Фоновое обновление: Загрузка данных из Google Sheets...")
        records = get_all_records()
        if records:
            build_or_load_index(records)
            logger.info(f"Фоновое обновление: Индекс обновлен ({len(records)} записей).")
        else:
            logger.warning("Фоновое обновление: Не удалось загрузить записи, индекс не обновлен.")

@app.on_event("startup")
def startup_event():
    """
    При запуске сервера:
    1. Сразу загружаем данные и строим индекс.
    2. Запускаем фоновую задачу для периодических обновлений.
    """
    logger.info("Сервер запускается... Первоначальное создание индекса.")
    records = get_all_records()
    if records:
        build_or_load_index(records)
        logger.info(f"Индекс успешно создан при запуске ({len(records)} записей).")
    else:
        logger.warning("Не удалось загрузить данные при старте. Повторная попытка через 1 час.")

    thread = threading.Thread(target=update_index_periodically, daemon=True)
    thread.start()

@app.post("/ask")
def ask_question(query: Query):
    """
    Основной эндпоинт, куда обращается бот.
    Теперь он также логирует данные для аналитики.
    """
    start_time = time.time()
    logger.info(f"Получен вопрос от user_id={query.user_id}: {query.question}")

    if not query.question:
        logger.error("Получен пустой вопрос.")
        raise HTTPException(status_code=400, detail="Вопрос не может быть пустым")

    response_data = search_index(query.question)

    end_time = time.time()
    response_time = end_time - start_time

    # Log the content of the response, whether it's an answer or clarification
    log_content = response_data.get("content", "")

    # Запускаем логирование в фоновом потоке, чтобы не задерживать ответ боту
    log_thread = threading.Thread(
        target=log_question,
        args=(query.user_id, query.question, log_content, response_time)
    )
    log_thread.start()

    logger.info(f"Response: {response_data} (response time: {response_time:.2f}s)")
    return response_data

@app.get("/records")
def get_records():
    """Endpoint to get all user records."""
    logger.info("Received request to get all user records.")
    records = get_user_records()
    return records

@app.post("/records")
def create_record(record: Record):
    """Endpoint to add a new user record."""
    logger.info(f"Received request to add a new record: {record}")
    success = add_record(name=record.name, phone=record.phone, email=record.email)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add record to Google Sheet.")
    return {"status": "success", "record": record}

@app.post("/feedback")
def receive_feedback(feedback: Feedback):
    """Endpoint to receive and log user feedback."""
    logger.info(f"Received feedback from user_id={feedback.user_id}: {feedback.feedback}")
    try:
        log_feedback(user_id=feedback.user_id, feedback=feedback.feedback)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to log feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to log feedback.")

@app.post("/rating")
def receive_call_center_rating(rating_data: CallCenterRating):
    """Endpoint to receive and log call center rating."""
    logger.info(f"Received call center rating from user_id={rating_data.user_id}: {rating_data.rating} stars")
    try:
        # Run in a separate thread to avoid blocking
        log_thread = threading.Thread(
            target=log_call_center_feedback,
            args=(rating_data.user_id, rating_data.rating, rating_data.comment, rating_data.timestamp)
        )
        log_thread.start()
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to log call center rating: {e}")
        raise HTTPException(status_code=500, detail="Failed to log call center rating.")

@app.get("/health")
def health_check():
    """Простой эндпоинт для проверки, что сервер жив."""
    return {"status": "ok"}

if __name__ == "__main__":
    logger.info("Запуск FastAPI сервера на http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)