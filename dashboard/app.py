import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import sys
import os

# Добавляем корневую директорию проекта в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.utils.data_loader import load_sheets_data, get_stats, load_feedback_data
from dashboard.utils.charts import create_activity_chart, create_response_time_chart
from config import GOOGLE_SHEETS_ID # Import GOOGLE_SHEETS_ID
import plotly.express as px

# Настройка страницы
st.set_page_config(
    page_title="Telegram Bot Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Заголовок
st.title("🤖 Telegram Bot Dashboard")
st.markdown("---")

# Боковая панель с фильтрами
with st.sidebar:
    st.header("⚙️ Фильтры")

    # Быстрый выбор периода
    period = st.selectbox(
        "Период",
        ["Сегодня", "Вчера", "Последние 7 дней", "Последние 30 дней", "Настроить"]
    )

    if period == "Сегодня":
        date_from = date_to = date.today()
    elif period == "Вчера":
        date_from = date_to = date.today() - timedelta(days=1)
    elif period == "Последние 7 дней":
        date_from = date.today() - timedelta(days=7)
        date_to = date.today()
    elif period == "Последние 30 дней":
        date_from = date.today() - timedelta(days=30)
        date_to = date.today()
    else:
        date_from = st.date_input("От", value=date.today() - timedelta(days=7))
        date_to = st.date_input("До", value=date.today())

    st.divider()

    # Дополнительные фильтры
    auto_refresh = st.checkbox("Авто-обновление", value=False)
    if auto_refresh:
        refresh_interval = st.slider("Интервал (сек)", 10, 300, 60)
        st.info(f"Обновление каждые {refresh_interval} сек")

# Загрузка данных
with st.spinner("Загрузка данных..."):
    try:
        data = load_sheets_data()
        stats = get_stats(data, date_from, date_to)
    except Exception as e:
        st.error(f"Ошибка загрузки данных: {e}")
        st.stop()

# Метрики
st.subheader("📊 Основные показатели")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Всего вопросов",
        stats['total_questions'],
        delta=stats.get('questions_delta')
    )

with col2:
    st.metric(
        "Успешных ответов",
        stats['successful_answers'],
        delta=stats.get('success_delta')
    )

with col3:
    st.metric(
        "Среднее время ответа",
        f"{stats['avg_response_time']:.2f}s",
        delta=stats.get('time_delta')
    )

with col4:
    st.metric(
        "Активных пользователей",
        stats['active_users']
    )

st.markdown("---")

# Графики
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Активность по дням")
    chart_data = create_activity_chart(data, date_from, date_to)
    st.line_chart(chart_data)

with col2:
    st.subheader("⏱️ Время ответа")
    response_chart = create_response_time_chart(data, date_from, date_to)
    st.bar_chart(response_chart)

st.markdown("---")

# Таблица последних вопросов
st.subheader("📝 Последние вопросы")

# Фильтры для таблицы
col1, col2 = st.columns([3, 1])
with col1:
    search = st.text_input("🔍 Поиск", placeholder="Введите текст для поиска...")
with col2:
    limit = st.number_input("Показать строк", min_value=5, max_value=100, value=20)

# Handle both Russian and English column names
question_col = 'question' if 'question' in data.columns else 'Вопрос'
answer_col = 'answer' if 'answer' in data.columns else 'Ответ'

# Фильтрация данных
filtered_data = data
if search:
    if question_col in filtered_data.columns:
        filtered_data = filtered_data[
            filtered_data[question_col].str.contains(search, case=False, na=False)
        ]

# Отображение таблицы
st.dataframe(
    filtered_data.tail(limit),
    use_container_width=True,
    column_config={
        "timestamp": st.column_config.DatetimeColumn("Время", format="DD.MM.YYYY HH:mm"),
        question_col: st.column_config.TextColumn("Вопрос", width="large"),
        answer_col: st.column_config.TextColumn("Ответ", width="large"),
    }
)

# Кнопка экспорта
if st.button("📥 Экспортировать в CSV"):
    csv = filtered_data.to_csv(index=False)
    st.download_button(
        label="Скачать CSV",
        data=csv,
        file_name=f"bot_data_{date.today()}.csv",
        mime="text/csv"
    )

# Авто-обновление
if auto_refresh:
    import time
    time.sleep(refresh_interval)
    st.rerun()

st.markdown("---")

# --- Feedback Analytics ---
st.subheader("👍👎 Оценка пользователей")
feedback_data = load_feedback_data()

if not feedback_data.empty:
    feedback_counts = feedback_data['feedback'].value_counts().reset_index()
    feedback_counts.columns = ['feedback', 'count']

    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("Всего оценок", feedback_counts['count'].sum())
        st.dataframe(feedback_counts)

    with col2:
        fig = px.pie(
            feedback_counts,
            values='count',
            names='feedback',
            title='Распределение оценок',
            color_discrete_map={'good': 'green', 'bad': 'red'}
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Пока нет данных об оценках.")
