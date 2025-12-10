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
qa_storage = []  # Will store {'question': str, 'answer': str}

# --- Prompts ---
ANALYZER_PROMPT = """
Ты — "AI-анализатор диалога". Твоя задача — помочь пользователю, задавшему неоднозначный вопрос. Ему НЕ НУЖНО отвечать. Ему нужно СФОРМУЛИРОВАТЬ ОДИН уточняющий вопрос, который поможет выбрать один из предложенных вариантов контекста.

ПРАВИЛА:
1. Проанализируй оригинальный вопрос пользователя.
2. Проанализируй несколько вариантов контекста, которые были найдены с низкой уверенностью.
3. Найди ключевое РАЗЛИЧИЕ между вариантами контекста (например, разные товарные группы, разные операции, разные документы).
4. Сформулируй ОДИН вежливый вопрос пользователю, который заставит его выбрать один из этих вариантов.
5. Если все варианты о разном, предложи 2-3 наиболее вероятных темы.
6. НЕ отвечай на оригинальный вопрос.
"""

FINAL_ANSWER_SYSTEM_PROMPT = "Ты — русскоязычный ассистент по системе маркировки товаров в Казахстане. Твоя задача — давать четкие и точные ответы на вопросы пользователей, основываясь на предоставленном контексте. Будь вежлив и профессионален."


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
    Creates or overwrites the FAISS index based on records, using OpenAI embeddings.
    """
    global index, qa_storage

    index_dir = os.path.dirname(INDEX_PATH)
    if index_dir:
        os.makedirs(index_dir, exist_ok=True)

    if not records:
        print("No records to index.")
        return

    # Store both questions and answers
    qa_storage = [{'question': record['Вопрос'], 'answer': record['Ответ']} for record in records]
    questions = [item['question'] for item in qa_storage]

    print(f"Generating embeddings for {len(questions)} questions via OpenAI...")

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
    Searches for the most relevant answer, handling disambiguation if necessary.
    Returns a dictionary with 'type' and 'content'.
    """
    global index, qa_storage
    if index is None or not qa_storage:
        return {"type": "answer", "content": "Индекс еще не создан или пуст."}

    # --- Language Detection and Translation ---
    try:
        lang, _ = langid.classify(query)
    except Exception:
        lang = "en"

    original_lang = lang
    search_query = query
    if original_lang != 'ru':
        try:
            search_query = GoogleTranslator(source=original_lang, target='ru').translate(query)
        except Exception as e:
            print(f"Error translating query to Russian: {e}")
            return {"type": "answer", "content": "Ошибка при переводе вашего запроса."}

    # --- Vector Search ---
    query_embedding = get_openai_embedding(search_query).reshape(1, -1).astype('float32')
    faiss.normalize_L2(query_embedding)

    # Search for top 3 results
    k = 3
    scores, indices = index.search(query_embedding, k=k)
    best_score = scores[0][0]

    print(f"Search (original): '{query[:30]}...' | Lang: {original_lang} | Best Score={best_score:.4f}")

    # --- Disambiguation Logic ---
    if best_score < 0.8:
        print(f"Triggering disambiguation for query: '{search_query}'")

        # Prepare context for the analyzer prompt
        context_options = []
        for i in range(k):
            idx = indices[0][i]
            # Use the original question from the knowledge base as context
            context_options.append(f"Вариант {i+1}: \"{qa_storage[idx]['question']}\"")

        analyzer_user_message = (
            f"Оригинальный вопрос пользователя: \"{search_query}\"\n\n"
            f"Найденные варианты контекста:\n" + "\n".join(context_options)
        )

        try:
            # First LLM call to get the clarifying question
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": ANALYZER_PROMPT},
                    {"role": "user", "content": analyzer_user_message}
                ],
                temperature=0.7,
                max_tokens=150
            )
            clarifying_question = response.choices[0].message.content.strip()

            # Translate back if necessary
            if original_lang != 'ru':
                 clarifying_question = GoogleTranslator(source='ru', target=original_lang).translate(clarifying_question)

            return {"type": "clarification", "content": clarifying_question}

        except Exception as e:
            print(f"Error during analyzer LLM call: {e}")
            return {"type": "answer", "content": "Возникла ошибка при уточнении вашего вопроса."}

    # --- High-Confidence Answer Logic ---
    else:
        best_idx = indices[0][0]
        retrieved_context = qa_storage[best_idx]['answer'] # The full answer is the context

        final_answer_user_prompt = (
            f"Контекст: \"{retrieved_context}\"\n\n"
            f"Вопрос: \"{search_query}\""
        )

        try:
            # Second LLM call to get the final, context-aware answer
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": FINAL_ANSWER_SYSTEM_PROMPT},
                    {"role": "user", "content": final_answer_user_prompt}
                ],
                temperature=0.2,
                max_tokens=1000
            )
            final_answer = response.choices[0].message.content.strip()

            # Translate back if necessary
            if original_lang != 'ru':
                final_answer = GoogleTranslator(source='ru', target=original_lang).translate(final_answer)

            return {"type": "answer", "content": final_answer}

        except Exception as e:
            print(f"Error during final answer LLM call: {e}")
            return {"type": "answer", "content": "Возникла ошибка при генерации ответа."}
