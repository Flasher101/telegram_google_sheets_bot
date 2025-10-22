# ai_server/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
# Используем относительные импорты, т.к. файлы в одном 'модуле'
from .g_sheets import get_all_records 
from .vector_store import build_or_load_index, search_index
import threading
import time
import uvicorn

app = FastAPI(title="AI Server (Google Sheets + FAISS)")

class Query(BaseModel):
    question: str

def update_index_periodically():
    """Фоновая задача для обновления индекса раз в час"""
    while True:
        # Ждем 1 час (3600 секунд) ПЕРЕД обновлением
        time.sleep(3600) 
        print("Фоновое обновление: Загрузка данных из Google Sheets...")
        records = get_all_records()
        if records:
            build_or_load_index(records)
            print(f"Фоновое обновление: Индекс обновлен ({len(records)} записей).")
        else:
            print("Фоновое обновление: Не удалось загрузить записи, индекс не обновлен.")

@app.on_event("startup")
def startup_event():
    """
    При запуске сервера:
    1. Сразу загружаем данные и строим индекс.
    2. Запускаем фоновую задачу для периодических обновлений.
    """
    print("Сервер запускается... Первоначальное создание индекса.")
    records = get_all_records()
    if records:
        build_or_load_index(records)
        print(f"Индекс успешно создан при запуске ({len(records)} записей).")
    else:
        print("Не удалось загрузить данные при старте. Повторная попытка через 1 час.")
    
    # Запускаем фоновую задачу в отдельном потоке
    thread = threading.Thread(target=update_index_periodically, daemon=True)
    thread.start()

@app.post("/ask")
def ask_question(query: Query):
    """
    Основной эндпоинт, куда обращается бот.
    """
    if not query.question:
        raise HTTPException(status_code=400, detail="Вопрос не может быть пустым")
        
    answer = search_index(query.question)
    return {"answer": answer}

@app.get("/health")
def health_check():
    """Простой эндпоинт для проверки, что сервер жив."""
    return {"status": "ok"}

if __name__ == "__main__":
    # Позволяет запускать файл напрямую: python ai_server/main.py
    print("Запуск FastAPI сервера на http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)