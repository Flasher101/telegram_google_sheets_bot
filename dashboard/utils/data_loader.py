import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import os
from gspread.exceptions import WorksheetNotFound

# --- Constants ---
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
INTERACTION_LOGS_SHEET_TITLE = "Interaction Logs"
FEEDBACK_SHEET_TITLE = "User Feedback"

# --- Helper Functions ---

def get_credentials_path():
    """Gets the absolute path to the service_account.json file."""
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root_dir, 'service_account.json')

def _get_client():
    """Helper to authenticate and get the gspread client."""
    creds = Credentials.from_service_account_file(get_credentials_path(), scopes=SCOPES)
    return gspread.authorize(creds)

def _create_empty_log_df():
    """Creates an empty DataFrame with correctly typed columns for interaction logs."""
    return pd.DataFrame({
        'timestamp': pd.Series(dtype='datetime64[ns]'),
        'user_id': pd.Series(dtype='str'),
        'question': pd.Series(dtype='str'),
        'answer': pd.Series(dtype='str'),
        'response_time': pd.Series(dtype='float'),
        'status': pd.Series(dtype='str')
    })

# --- Main Data Loading Functions ---

def load_sheets_data():
    """
    Loads user interaction data from the 'Interaction Logs' worksheet in Google Sheets.
    Returns a correctly typed DataFrame, even if the sheet is empty or does not exist.
    """
    try:
        client = _get_client()
        from config import GOOGLE_SHEETS_ID
        spreadsheet = client.open_by_key(GOOGLE_SHEETS_ID)

        try:
            sheet = spreadsheet.worksheet(INTERACTION_LOGS_SHEET_TITLE)
        except WorksheetNotFound:
            print(f"WARNING: Worksheet '{INTERACTION_LOGS_SHEET_TITLE}' not found. Returning empty DataFrame.")
            return _create_empty_log_df()

        data = sheet.get_all_records()
        if not data:
            print(f"INFO: Worksheet '{INTERACTION_LOGS_SHEET_TITLE}' is empty. Returning empty DataFrame.")
            return _create_empty_log_df()

        df = pd.DataFrame(data)

        # Ensure columns are correctly typed after loading
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        if 'response_time' in df.columns:
            df['response_time'] = pd.to_numeric(df['response_time'], errors='coerce')

        return df

    except Exception as e:
        print(f"ERROR loading interaction data from Google Sheets: {e}")
        return _create_empty_log_df()

def get_stats(df, date_from, date_to):
    """Calculates statistics for the dashboard metrics."""
    if df.empty:
        return {'total_questions': 0, 'successful_answers': 0, 'avg_response_time': 0, 'active_users': 0}

    # Filter by the selected date range
    df_filtered = df[
        (df['timestamp'].dt.date >= date_from) &
        (df['timestamp'].dt.date <= date_to)
    ]

    stats = {
        'total_questions': len(df_filtered),
        'successful_answers': len(df_filtered[df_filtered['status'] == 'success']) if 'status' in df_filtered.columns else 0,
        'avg_response_time': df_filtered['response_time'].astype(float).mean() if 'response_time' in df_filtered.columns and not df_filtered.empty else 0,
        'active_users': df_filtered['user_id'].nunique() if 'user_id' in df_filtered.columns else 0,
    }

    return stats

def load_feedback_data():
    """
    Loads user feedback from the 'User Feedback' worksheet.
    """
    try:
        client = _get_client()
        from config import GOOGLE_SHEETS_ID
        spreadsheet = client.open_by_key(GOOGLE_SHEETS_ID)

        try:
            sheet = spreadsheet.worksheet(FEEDBACK_SHEET_TITLE)
        except WorksheetNotFound:
            print(f"WARNING: Worksheet '{FEEDBACK_SHEET_TITLE}' not found. Returning empty DataFrame.")
            return pd.DataFrame()

        data = sheet.get_all_records()
        df = pd.DataFrame(data)

        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        return df

    except Exception as e:
        print(f"WARNING: Could not load feedback data. {e}")
        return pd.DataFrame() # Return empty on error
