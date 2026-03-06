import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_SECRET = os.getenv("API_SECRET") # Shared secret for backend communication
DB_URL = os.getenv("DB_URL") # PostgreSQL URL if shared
