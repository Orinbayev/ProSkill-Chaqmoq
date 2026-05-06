import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.shared_secret import resolve_api_secret

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
# Ikkinchi bot — faqat ota-ona va o'quvchilar uchun (Family bot)
BOT_TOKEN_FAMILY = os.getenv("BOT_TOKEN_FAMILY") or os.getenv("TELEGRAM_BOT_TOKEN_FAMILY")
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
INTERNAL_BACKEND_URL = "http://127.0.0.1:8000"
BOT_API_PORT = int(os.getenv("BOT_API_PORT", "8080"))
API_SECRET = resolve_api_secret()
DB_URL = os.getenv("DB_URL")
