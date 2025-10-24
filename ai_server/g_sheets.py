# ai_server/g_sheets.py

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import csv
from config import GOOGLE_SHEETS_ID # Use ID instead of Name for reliability

# Path to the key file, assuming it's in the project root
KEY_FILE_PATH = 'service_account.json'
SCOPE = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
LOCAL_DATA_PATH = 'local_data.csv' # Path to the local CSV fallback

def _get_sheet(worksheet_index=0):
    """Helper function to authorize and get a specific worksheet."""
    creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE_PATH, SCOPE)
    client = gspread.authorize(creds)
    workbook = client.open_by_key(GOOGLE_SHEETS_ID)
    return workbook.get_worksheet(worksheet_index)

def _read_from_csv():
    """Reads records from local_data.csv."""
    print(f"INFO: Попытка чтения данных из локального файла '{LOCAL_DATA_PATH}'...")
    if not os.path.exists(LOCAL_DATA_PATH):
        print(f"Предупреждение: Файл '{LOCAL_DATA_PATH}' не найден. Локальная база знаний недоступна.")
        return []

    try:
        with open(LOCAL_DATA_PATH, mode='r', encoding='utf-8') as infile:
            # Handle potential BOM (Byte Order Mark) for UTF-8 files from Excel
            infile.seek(0)
            if infile.read(1) != '\ufeff':
                infile.seek(0)

            reader = csv.DictReader(infile)
            normalized_records = []
            for row in reader:
                # Normalize keys to lower case for consistent matching
                row_lower = {k.lower(): v for k, v in row.items()}

                question = row_lower.get('вопрос') or row_lower.get('question')
                answer = row_lower.get('ответ') or row_lower.get('answer')

                if question and answer:
                    normalized_records.append({'Вопрос': question, 'Ответ': answer})

            if normalized_records:
                print(f"INFO: Успешно загружено {len(normalized_records)} записей из '{LOCAL_DATA_PATH}'.")
            else:
                print(f"Предупреждение: В файле '{LOCAL_DATA_PATH}' не найдено записей с нужными столбцами ('Вопрос'/'Question', 'Ответ'/'Answer').")

            return normalized_records
    except Exception as e:
        print(f"Ошибка при чтении файла '{LOCAL_DATA_PATH}': {e}")
        return []

def get_all_records():
    """
    Reads all records from the FIRST worksheet for the AI knowledge base.
    If it fails, it falls back to reading from 'local_data.csv'.
    It expects columns 'Вопрос'/'Question' and 'Ответ'/'Answer' (case-insensitive).
    """
    try:
        print("INFO: Попытка чтения данных из Google Sheets...")
        sheet = _get_sheet(0)
        if not sheet:
            print("Ошибка: Первый лист (worksheet) не найден в Google Sheet.")
            raise ConnectionError("Worksheet not found") # Raise error to trigger fallback

        headers = sheet.row_values(1)
        print(f"INFO: Найдены заголовки в Google Sheet: {headers}")

        records = sheet.get_all_records()

        normalized_records = []
        for r in records:
            # Strip whitespace from keys and convert to lower case for robust matching
            record_lower = {k.strip().lower(): v for k, v in r.items()}

            question = record_lower.get('вопрос') or record_lower.get('question')
            answer = record_lower.get('ответ') or record_lower.get('answer')

            if question and answer:
                normalized_records.append({'Вопрос': question, 'Ответ': answer})

        if not normalized_records:
            print("Предупреждение: На первом листе не найдено записей с подходящими столбцами.")
            print("Ожидались столбцы 'Вопрос'/'Question' и 'Ответ'/'Answer'.")
            print("INFO: Попытка загрузки из локального файла local_data.csv...")
            return _read_from_csv()

        print(f"INFO: Успешно загружено {len(normalized_records)} записей из Google Sheets.")
        return normalized_records

    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА при чтении Google Sheets: {e}")
        print("INFO: Переключаюсь на локальную базу знаний (local_data.csv).")
        return _read_from_csv()

def get_user_records():
    """
    Reads user data from the SECOND worksheet.
    It expects columns 'name', 'phone', 'email' (case-insensitive).
    """
    try:
        sheet = _get_sheet(1)
        if not sheet:
            print("Предупреждение: Второй лист для данных пользователей не найден.")
            return []

        records = sheet.get_all_records()

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

def log_question(user_id: str, question: str, answer: str, response_time: float):
    """
    Logs a question and its analytics data to the FIRST worksheet.
    """
    try:
        sheet = _get_sheet(0)
        if not sheet:
            print("Ошибка: Первый лист для логов не найден. Не могу записать данные аналитики.")
            return

        # Prepare the row with a timestamp and status
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status = 'success' if answer else 'fail'

        # This assumes your sheet has the columns in this order.
        # It's important to match the order in your Google Sheet.
        sheet.append_row([
            timestamp,
            user_id,
            question,
            answer,
            response_time,
            status
        ], value_input_option='USER_ENTERED')
        print(f"Вопрос залогирован: user_id={user_id}, time={response_time:.2f}s")

    except Exception as e:
        print(f"Ошибка при логировании вопроса в Google Sheets: {e}")


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