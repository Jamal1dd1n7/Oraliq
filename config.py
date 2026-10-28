import os
from dotenv import load_dotenv
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent

# .env faylini yuklaymiz
load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("TOKEN", "")


ADMIN_TELEGRAM_ID = 5700003882

DB_CONFIG = {
    "dbname": "oraliq_imtihon",
    "user": "postgres",
    "password": "just_mm08",
    "host": "localhost",
    "port": "5432"
}