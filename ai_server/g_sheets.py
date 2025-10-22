# ai_server/g_sheets.py

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from config import GOOGLE_SHEETS_ID # Use ID instead of Name for reliability

# Path to the key file, assuming it's in the project root
KEY_FILE_PATH = 'service_account.json'
SCOPE = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']

def _get_sheet(worksheet_index=0):
    """Helper function to authorize and get a specific worksheet."""
    creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE_PATH, SCOPE)
    client = gspread.authorize(creds)
    workbook = client.open_by_key(GOOGLE_SHEETS_ID)
    return workbook.get_worksheet(worksheet_index)

def get_all_records():
    """
    Reads all records from the FIRST worksheet for the AI knowledge base.
    It expects columns 'Вопрос'/'Question' and 'Ответ'/'Answer' (case-insensitive).
    """
    try:
        sheet = _get_sheet(0)
        if not sheet:
            print("Ошибка: Первый лист (worksheet) не найден в Google Sheet.")
            return []

        records = sheet.get_all_records()

        normalized_records = []
        for r in records:
            record_lower = {k.lower(): v for k, v in r.items()}

            question = record_lower.get('вопрос') or record_lower.get('question')
            answer = record_lower.get('ответ') or record_lower.get('answer')

            if question and answer:
                normalized_records.append({'Вопрос': question, 'Ответ': answer})

        if not normalized_records:
            print("Предупреждение: На первом листе не найдено записей с подходящими столбцами ('Вопрос'/'Question' и 'Ответ'/'Answer').")

        return normalized_records

    except gspread.exceptions.SpreadsheetNotFound:
        print(f"Ошибка: Таблица с ID '{GOOGLE_SHEETS_ID}' не найдена.")
        print("Убедитесь, что ID в config.py верный и вы поделились таблицей с сервисным аккаунтом.")
        return []
    except FileNotFoundError:
        print(f"Ошибка: Файл ключа '{KEY_FILE_PATH}' не найден.")
        print("Убедитесь, что файл service_account.json находится в корневой папке проекта.")
        return []
    except Exception as e:
        print(f"Ошибка при чтении Google Sheets: {e}")
        return []

def get_user_records():
    """
    Reads user data from the SECOND worksheet.
    It expects columns 'name', 'phone', 'email' (case-insensitive).
    """
    try:
        # User data is assumed to be on the second sheet (index 1)
        sheet = _get_sheet(1)
        if not sheet:
            print("Предупреждение: Второй лист для данных пользователей не найден.")
            return []

        records = sheet.get_all_records()

        # Normalize keys for consistent access in the bot
        normalized_records = []
        for r in records:
            record_lower = {k.lower(): v for k, v in r.items()}
            if 'name' in record_lower and 'phone' in record_lower and 'email' in record_lower:
                normalized_records.append({
                    'name': record_lower['name'],
                    'phone': record_lower['phone'],
                    'email': record_lower['email']
                })
        return normalized_records
    except Exception as e:
        print(f"Ошибка при чтении записей пользователей: {e}")
        return []

def add_record(name: str, phone: str, email: str):
    """
    Adds a new record to the SECOND worksheet.
    """
    try:
        sheet = _get_sheet(1)
        if not sheet:
            print("Ошибка: Второй лист для данных пользователей не найден. Не могу добавить запись.")
            return False

        sheet.append_row([name, phone, email], value_input_option='USER_ENTERED')
        print(f"Запись добавлена: {name}, {phone}, {email}")
        return True
    except Exception as e:
        print(f"Ошибка при добавлении записи в Google Sheets: {e}")
        return False