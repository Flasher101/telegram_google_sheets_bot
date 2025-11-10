# ai_server/vector_store.py

import faiss
import numpy as np
from openai import OpenAI
import os
from config import FAISS_INDEX_PATH, OPENAI_API_KEY
import langid
from deep_translator import GoogleTranslator

# Initialize the OpenAI client after importing the key
client = OpenAI(api_key=OPENAI_API_KEY)

# --- OpenAI Configuration ---
# Используем новую модель эмбеддингов от OpenAI
MODEL_NAME = 'text-embedding-3-small'
# Размер эмбеддинга для этой модели
EMBEDDING_DIM = 1536

# --- FAISS Configuration ---
INDEX_PATH = FAISS_INDEX_PATH

# --- Global Storage ---
index = None
answer_storage = []  # Список для хранения ответов

def get_openai_embedding(text: str) -> np.ndarray:
    """
    Получает эмбеддинг для текста с использованием OpenAI API.
    """
    try:
        response = client.embeddings.create(input=[text], model=MODEL_NAME)
        embedding = response.data[0].embedding
        return np.array(embedding)
    except Exception as e:
        print(f"Ошибка при получении эмбеддинга от OpenAI: {e}")
        return np.zeros(EMBEDDING_DIM)

def build_or_load_index(records: list):
    """
    Создает или перезаписывает индекс FAISS на основе записей, используя эмбеддинги OpenAI.
    """
    global index, answer_storage

    # Получаем директорию из пути к файлу индекса
    index_dir = os.path.dirname(INDEX_PATH)

    # Создаем директорию, только если путь к ней не пустой
    if index_dir:
        os.makedirs(index_dir, exist_ok=True)

    if not records:
        print("Нет записей для индексации.")
        return

    questions = [record['Вопрос'] for record in records]
    answer_storage = [record['Ответ'] for record in records]

    print(f"Генерация эмбеддингов для {len(questions)} вопросов через OpenAI...")

    # Получаем эмбеддинги для всех вопросов
    embeddings = [get_openai_embedding(q) for q in questions]

    # Преобразуем в numpy массив и нормализуем
    embeddings_np = np.array(embeddings).astype('float32')
    faiss.normalize_L2(embeddings_np)

    # Создаем индекс FAISS
    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    index.add(embeddings_np)

    print(f"Индекс создан. Запись в {INDEX_PATH}...")
    faiss.write_index(index, INDEX_PATH)

def search_index(query: str):
    """
    Ищет наиболее релевантный ответ, используя эмбеддинги OpenAI.
    """
    global index, answer_storage
    if index is None or not answer_storage:
        return "Индекс еще не создан или пуст. Пожалуйста, подождите."

    try:
        lang, _ = langid.classify(query)
    except Exception:
        lang = "en"

    search_query = query
    if lang != 'ru':
        try:
            search_query = GoogleTranslator(source=lang, target='ru').translate(query)
        except Exception as e:
            print(f"Ошибка перевода запроса: {e}")

    # 1. Создаем эмбеддинг для запроса
    query_embedding = get_openai_embedding(search_query).reshape(1, -1)
    query_embedding = query_embedding.astype('float32')
    faiss.normalize_L2(query_embedding)

    # 2. Ищем k=1 (1 ближайший)
    D, I = index.search(query_embedding, k=1)

    best_score = D[0][0]
    best_idx = I[0][0]

    print(f"Поиск (оригинал): '{query[:20]}...' | Язык: {lang} | Лучший Score={best_score:.4f}")

    # 3. Порог релевантности (для косинусного сходства, чем ближе к 1, тем лучше)
    if best_score < 0.5:
        not_found_message = "Извините, я не нашел точного ответа. Попробуйте переформулировать вопрос или свяжитесь с КЦ."
        if lang != 'ru':
            try:
                return GoogleTranslator(source='ru', target=lang).translate(not_found_message)
            except Exception:
                return "Sorry, I couldn't find an exact answer."
        return not_found_message

    retrieved_answer = answer_storage[best_idx]

    if lang != 'ru':
        try:
            return GoogleTranslator(source='ru', target=lang).translate(retrieved_answer)
        except Exception as e:
            print(f"Ошибка перевода ответа: {e}")

    return retrieved_answer
