# ai_server/g_sheets.py

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import csv
from config import GOOGLE_SHEETS_ID
from gspread.exceptions import WorksheetNotFound
from datetime import datetime

# --- Constants ---
KEY_FILE_PATH = 'service_account.json'
SCOPE = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
LOCAL_DATA_PATH = 'local_data.csv'

# Define worksheet titles for clarity and robustness
KB_SHEET_INDEX = 0  # Knowledge base remains the first sheet
USER_RECORDS_SHEET_TITLE = "User Records"
INTERACTION_LOGS_SHEET_TITLE = "Interaction Logs"
FEEDBACK_SHEET_TITLE = "User Feedback"
CALL_CENTER_FEEDBACK_SHEET_TITLE = "Call Center Feedback"

# --- Helper Functions ---

def _get_client():
    """Helper to authorize and get the gspread client."""
    creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE_PATH, SCOPE)
    return gspread.authorize(creds)

def _get_or_create_sheet_by_title(workbook, title, headers=None):
    """Gets a worksheet by title, creating it with headers if it doesn't exist."""
    try:
        return workbook.worksheet(title)
    except WorksheetNotFound:
        print(f"INFO: Worksheet '{title}' not found. Creating it.")
        sheet = workbook.add_worksheet(title=title, rows="100", cols="20")
        if headers:
            sheet.append_row(headers, value_input_option='USER_ENTERED')
            print(f"INFO: Added headers to '{title}': {headers}")
        return sheet

def _read_from_csv():
    """Reads records from local_data.csv."""
    print(f"INFO: Attempting to read data from local file '{LOCAL_DATA_PATH}'...")
    if not os.path.exists(LOCAL_DATA_PATH):
        print(f"WARNING: File '{LOCAL_DATA_PATH}' not found. Local knowledge base is unavailable.")
        return []

    try:
        with open(LOCAL_DATA_PATH, mode='r', encoding='utf-8-sig') as infile:
            reader = csv.DictReader(infile)
            normalized_records = []
            for row in reader:
                row_lower = {k.lower(): v for k, v in row.items()}
                question = row_lower.get('вопрос') or row_lower.get('question')
                answer = row_lower.get('ответ') or row_lower.get('answer')
                if question and answer:
                    normalized_records.append({'Вопрос': question, 'Ответ': answer})

            if normalized_records:
                print(f"INFO: Successfully loaded {len(normalized_records)} records from '{LOCAL_DATA_PATH}'.")
            else:
                print(f"WARNING: No records with required columns ('Вопрос'/'Question', 'Ответ'/'Answer') found in '{LOCAL_DATA_PATH}'.")
            return normalized_records
    except Exception as e:
        print(f"ERROR reading file '{LOCAL_DATA_PATH}': {e}")
        return []

# --- Main Data Functions ---

def get_all_records():
    """
    Reads all records from the FIRST worksheet for the AI knowledge base.
    Falls back to 'local_data.csv' on failure.
    """
    try:
        print("INFO: Attempting to read knowledge base from Google Sheets...")
        client = _get_client()
        workbook = client.open_by_key(GOOGLE_SHEETS_ID)
        sheet = workbook.get_worksheet(KB_SHEET_INDEX)
        if not sheet:
            raise ConnectionError("First worksheet (knowledge base) not found.")

        headers = sheet.row_values(1)
        print(f"INFO: Found headers in Google Sheet knowledge base: {headers}")

        records = sheet.get_all_records()

        normalized_records = []
        for r in records:
            record_lower = {k.strip().lower(): v for k, v in r.items()}
            question = record_lower.get('вопрос') or record_lower.get('question')
            answer = record_lower.get('ответ') or record_lower.get('answer')
            if question and answer:
                normalized_records.append({'Вопрос': question, 'Ответ': answer})

        if not normalized_records:
            print("WARNING: No valid records found on the first worksheet. Attempting local fallback.")
            return _read_from_csv()

        print(f"INFO: Successfully loaded {len(normalized_records)} records from Google Sheets knowledge base.")
        return normalized_records

    except Exception as e:
        print(f"CRITICAL ERROR reading Google Sheets knowledge base: {e}")
        print("INFO: Switching to local knowledge base (local_data.csv).")
        return _read_from_csv()

def get_user_records():
    """Reads user data from the 'User Records' worksheet."""
    try:
        client = _get_client()
        workbook = client.open_by_key(GOOGLE_SHEETS_ID)
        sheet = _get_or_create_sheet_by_title(workbook, USER_RECORDS_SHEET_TITLE, headers=['name', 'phone', 'email'])

        records = sheet.get_all_records()
        return [r for r in records if 'name' in r and 'phone' in r and 'email' in r]
    except Exception as e:
        print(f"ERROR reading user records: {e}")
        return []

def add_record(name: str, phone: str, email: str):
    """Adds a new record to the 'User Records' worksheet."""
    try:
        client = _get_client()
        workbook = client.open_by_key(GOOGLE_SHEETS_ID)
        sheet = _get_or_create_sheet_by_title(workbook, USER_RECORDS_SHEET_TITLE, headers=['name', 'phone', 'email'])

        sheet.append_row([name, phone, email], value_input_option='USER_ENTERED')
        print(f"Record added: {name}, {phone}, {email}")
        return True
    except Exception as e:
        print(f"ERROR adding record to Google Sheets: {e}")
        return False

def log_question(user_id: str, question: str, answer: str, response_time: float):
    """Logs question analytics to the 'Interaction Logs' worksheet."""
    try:
        client = _get_client()
        workbook = client.open_by_key(GOOGLE_SHEETS_ID)
        headers = ['timestamp', 'user_id', 'question', 'answer', 'response_time', 'status']
        sheet = _get_or_create_sheet_by_title(workbook, INTERACTION_LOGS_SHEET_TITLE, headers=headers)

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status = 'success' if answer else 'fail'

        sheet.append_row([timestamp, user_id, question, answer, response_time, status], value_input_option='USER_ENTERED')
        print(f"Question logged: user_id={user_id}, time={response_time:.2f}s")
    except Exception as e:
        print(f"ERROR logging question to Google Sheets: {e}")

