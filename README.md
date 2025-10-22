# Telegram Bot with Google Sheets & FAISS Integration

This project provides a Telegram bot that can answer questions using a FAISS vector search index, and can read and write data to a Google Sheet. The project is composed of two main components: an AI server built with FastAPI, and a Telegram bot built with aiogram.

## Prerequisites

- Python 3.8+
- A Google Cloud Platform account
- A Telegram account

## Installation Steps

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Flasher101/telegram_google_sheets_bot.git
    cd telegram_google_sheets_bot
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv .venv
    ```

3.  **Activate the virtual environment:**
    -   **Windows:**
        ```bash
        .venv\\Scripts\\activate
        ```
    -   **Linux/macOS:**
        ```bash
        source .venv/bin/activate
        ```

4.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration Guide

1.  **Create a `config.py` file:**
    -   In the root directory of the project, create a file named `config.py`.
    -   Copy the contents of `config.example.py` into `config.py`.
    -   Fill in the values for the following variables:
        -   `TELEGRAM_BOT_TOKEN`: Your Telegram bot token, which you can get from [@BotFather](https://t.me/BotFather).
        -   `GOOGLE_SHEETS_ID`: The ID of your Google Sheet. You can find this in the URL of your Google Sheet. For example, if the URL is `https://docs.google.com/spreadsheets/d/1234567890abcdefghijklmnopqrstuvwxyz/edit#gid=0`, the ID is `1234567890abcdefghijklmnopqrstuvwxyz`.

2.  **Create a `service_account.json` file:**
    -   In the root directory of the project, create a file named `service_account.json`.
    -   Copy the contents of `service_account.example.json` into `service_account.json`.
    -   Fill in the values for the fields in this file with your Google Cloud service account credentials. You can get these credentials by following the instructions in the [Google Cloud documentation](https://cloud.google.com/docs/authentication/getting-started).

## Running the Application

-   **Windows:**
    ```bash
    start.bat
    ```
-   **Linux/macOS:**
    ```bash
    ./start.sh
    ```

## Testing the Bot

1.  Open the Telegram app.
2.  Search for your bot by its username.
3.  Send the `/start` command.
4.  You should see a welcome message and a menu of buttons.
5.  Test each of the buttons to ensure they are working correctly.

## Architecture Overview

The project is composed of two main components:

-   **AI Server:** A FastAPI application that provides an API for querying the FAISS vector search index.
-   **Bot:** A Telegram bot built with aiogram that interacts with the user and communicates with the AI server.

The bot and the AI server communicate with each other via HTTP requests. The bot sends a request to the AI server when a user asks a question, and the AI server responds with the answer.

## Troubleshooting

-   **Bot doesn't respond:** Check that you have entered the correct Telegram bot token in `config.py`.
-   **Import errors:** Make sure you have activated the virtual environment and installed the dependencies.
-   **Google Sheets error:** Check that you have correctly configured your `service_account.json` file and that you have given the service account permission to access your Google Sheet.
-   **FAISS not found:** The FAISS index is created automatically when the AI server starts. If you are having issues with the index, you can delete the `faiss_index` file and restart the AI server to recreate it.

## Project Structure

```
.
├── ai_server
│   ├── __init__.py
│   ├── g_sheets.py
│   ├── main.py
│   └── vector_store.py
├── bot
│   ├── __init__.py
│   └── bot_main.py
├── .venv
├── config.example.py
├── requirements.txt
├── service_account.example.json
├── start.bat
└── start.sh
```

## Testing Checklist

- [ ] `start.bat` runs without errors
- [ ] `ai_server` starts on port 8000
- [ ] bot connects to Telegram
- [ ] `/start` command works
- [ ] `/help` command works
- [ ] All inline buttons respond
- [ ] FAISS search returns results
- [ ] Google Sheets read works
- [ ] Google Sheets write works
- [ ] Bot handles errors gracefully
