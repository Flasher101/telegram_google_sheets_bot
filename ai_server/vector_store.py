# ai_server/vector_store.py

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import os
from config import FAISS_INDEX_PATH
import langid
from deep_translator import GoogleTranslator

# Используем ту же модель, что и обсуждали
MODEL_NAME = 'all-MiniLM-L6-v2'
# Размер эмбеддинга для этой модели
EMBEDDING_DIM = 384
# Используем путь из конфига, чтобы избежать проблем с кириллицей и пробелами
INDEX_PATH = FAISS_INDEX_PATH

# 1. Инициализация модели (загружается 1 раз)
print("Загрузка embedding-модели...")
model = SentenceTransformer(MODEL_NAME)
print("Модель загружена.")

# 2. Индекс и хранилище ответов
index = None
answer_storage = [] # Список для хранения ответов. Индекс в FAISS == индекс в этом списке.

def build_or_load_index(records: list):
    """
    Создает или перезаписывает индекс FAISS на основе записей из Google Sheets.
    """
    global index, answer_storage
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)

    if not records:
        print("Нет записей для индексации.")
        return

    questions = [record['Вопрос'] for record in records]
    # Обновляем наше хранилище ответов
    answer_storage = [record['Ответ'] for record in records]

    print(f"Генерация эмбеддингов для {len(questions)} вопросов...")
    embeddings = model.encode(questions, convert_to_numpy=True, normalize_embeddings=True)
    # FAISS требует float32
    embeddings = embeddings.astype('float32')

    # Создаем индекс FAISS. IndexFlatIP = поиск по внутреннему произведению (эффективен для норм. векторов)
    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    index.add(embeddings)

    print(f"Индекс создан. Запись в {INDEX_PATH}...")
    faiss.write_index(index, INDEX_PATH)

def search_index(query: str):
    """
    Ищет наиболее релевантный ответ в индексе FAISS.
    Сначала переводит запрос на русский, чтобы найти ответ в русскоязычной базе,
    затем переводит найденный ответ обратно на язык запроса.
    """
    global index, answer_storage
    if index is None or not answer_storage:
        return "Индекс еще не создан или пуст. Пожалуйста, подождите."

    try:
        # langid.classify() возвращает кортеж (язык, уверенность)
        lang, _ = langid.classify(query)
    except Exception as e:
        print(f"Ошибка определения языка: {e}")
        lang = "en"  # Default to English if detection fails

    # 1. Если язык не русский, переводим запрос на русский для поиска
    search_query = query
    if lang != 'ru':
        try:
            print(f"Перевод запроса с '{lang}' на 'ru'...")
            search_query = GoogleTranslator(source=lang, target='ru').translate(query)
            print(f"Переведенный запрос: '{search_query[:30]}...'")
        except Exception as e:
            print(f"Ошибка перевода запроса: {e}")
            # Если перевод не удался, ищем по оригиналу, но результат может быть плохим
            search_query = query

    # 2. Создаем эмбеддинг для запроса (теперь для search_query)
    query_embedding = model.encode([search_query], convert_to_numpy=True, normalize_embeddings=True)
    query_embedding = query_embedding.astype('float32')

    # 3. Ищем k=1 (1 ближайший)
    # D = Расстояния (scores), I = Индексы (ID)
    D, I = index.search(query_embedding, k=1)

    best_score = D[0][0]
    best_idx = I[0][0]

    # Логгируем с оригинальным запросом для ясности
    print(f"Поиск (оригинал): '{query[:20]}...' | Язык: {lang} | Лучший Score={best_score:.4f} | Индекс={best_idx}")

    # 4. Порог релевантности
    if best_score < 0.55:
        if lang == "ru":
            return "Извините, я не нашел точного ответа. Попробуйте переформулировать вопрос или свяжитесь с КЦ."
        else:
            # Переводим сообщение "не найдено" на язык пользователя
            try:
                translated_not_found = GoogleTranslator(source='ru', target=lang).translate("Извините, я не нашел точного ответа. Попробуйте переформулировать вопрос или свяжитесь с КЦ.")
                return translated_not_found
            except Exception as e:
                print(f"Ошибка перевода 'не найдено': {e}")
                return "Sorry, I couldn't find an exact answer. Please try rephrasing the question or contact the call center."

    # 5. Получаем русскоязычный ответ
    retrieved_answer = answer_storage[best_idx]

    # 6. Переводим ответ обратно, если язык запроса был не русский
    if lang != 'ru':
        try:
            print(f"Перевод ответа на '{lang}'...")
            translated_answer = GoogleTranslator(source='ru', target=lang).translate(retrieved_answer)
            return translated_answer
        except Exception as e:
            print(f"Ошибка перевода ответа: {e}")
            # Если перевод не удался, возвращаем оригинал
            return retrieved_answer

    # Если язык русский, просто возвращаем ответ
    return retrieved_answer
