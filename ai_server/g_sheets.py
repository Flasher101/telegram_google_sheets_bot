# ai_server/g_sheets.py

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from config import GOOGLE_SHEET_NAME

# Путь к файлу ключа
KEY_FILE_PATH = os.path.join(os.path.dirname(__file__), 'service_account.json')
SCOPE = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']

def get_all_records():
    """
    Считывает все записи из Google Sheet.
    Ожидает столбцы 'Вопрос' и 'Ответ'.
    """
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE_PATH, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open(GOOGLE_SHEET_NAME).sheet1
        
        # get_all_records() считывает все, кроме первой (заголовочной) строки
        records = sheet.get_all_records() 
        
        # Фильтруем пустые строки, если они есть
        valid_records = [r for r in records if r.get('Вопрос') and r.get('Ответ')]
        
        if not valid_records:
            print("Предупреждение: В Google Sheet не найдено записей с 'Вопрос' и 'Ответ'.")
            
        return valid_records
    
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"Ошибка: Таблица с именем '{GOOGLE_SHEET_NAME}' не найдена.")
        print("Убедитесь, что имя в config.py верное и вы поделились таблицей с сервисным аккаунтом.")
        return []
    except Exception as e:
        print(f"Ошибка при чтении Google Sheets: {e}")
        return []