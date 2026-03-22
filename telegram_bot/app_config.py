import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
INTERNAL_BACKEND_URL = "http://127.0.0.1:8000"
BOT_API_PORT = 8080
API_SECRET = os.getenv("API_SECRET")
DB_URL = os.getenv("DB_URL")
