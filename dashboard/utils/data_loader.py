import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import os

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def get_credentials_path():
    """Получить путь к credentials.json"""
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(root_dir, 'service_account.json') # Corrected to service_account.json

def load_sheets_data():
    """Загрузить данные из Google Sheets"""
    try:
        creds = Credentials.from_service_account_file(
            get_credentials_path(),
            scopes=SCOPES
        )
        client = gspread.authorize(creds)

        from config import GOOGLE_SHEETS_ID
        # Open the sheet by its unique ID for reliability
        spreadsheet = client.open_by_key(GOOGLE_SHEETS_ID)
        sheet = spreadsheet.sheet1

        # Получить все данные
        data = sheet.get_all_records()
        df = pd.DataFrame(data)

        # Преобразование временных меток
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        return df

    except Exception as e:
        raise Exception(f"Ошибка загрузки данных: {e}")

def get_stats(df, date_from, date_to):
    """Рассчитать статистику"""
    # Фильтрация по датам
    if 'timestamp' in df.columns:
        df_filtered = df[
            (df['timestamp'].dt.date >= date_from) &
            (df['timestamp'].dt.date <= date_to)
        ]
    else:
        df_filtered = df

    stats = {
        'total_questions': len(df_filtered),
        'successful_answers': len(df_filtered[df_filtered['status'] == 'success']) if 'status' in df_filtered.columns else len(df_filtered),
        'avg_response_time': df_filtered['response_time'].mean() if 'response_time' in df_filtered.columns else 0,
        'active_users': df_filtered['user_id'].nunique() if 'user_id' in df_filtered.columns else 0,
    }

    return stats
