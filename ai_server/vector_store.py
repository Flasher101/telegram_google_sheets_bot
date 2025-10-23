# ai_server/vector_store.py

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import os
from config import FAISS_INDEX_PATH

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
    """
    global index, answer_storage
    if index is None or not answer_storage:
        return "Индекс еще не создан или пуст. Пожалуйста, подождите."
    
    # 1. Создаем эмбеддинг для запроса
    query_embedding = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
    query_embedding = query_embedding.astype('float32')
    
    # 2. Ищем k=1 (1 ближайший)
    # D = Расстояния (scores), I = Индексы (ID)
    D, I = index.search(query_embedding, k=1) 
    
    best_score = D[0][0]
    best_idx = I[0][0]
    
    print(f"Поиск: '{query[:20]}...' | Лучший Score={best_score:.4f} | Индекс={best_idx}")

    # 3. Порог релевантности (подберите под свои данные)
    # 0.60 - довольно строгий. 0.5 - более мягкий.
    if best_score < 0.55: 
        return "Извините, я не нашел точного ответа. Попробуйте переформулировать вопрос или свяжитесь с КЦ."
    
    # Возвращаем ответ по найденному индексу
    return answer_storage[best_idx]