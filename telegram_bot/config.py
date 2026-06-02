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
# 🚨 IMPORTANT: In Render, Django and Bot are in the SAME container.
# We MUST use 127.0.0.1 for internal calls (Django <-> Bot).
# The bot's internal API should be bound to 127.0.0.1:8080.
# For external bot replies, we use the global domain.
BACKEND_URL = os.getenv("BACKEND_URL", f"http://127.0.0.1:{os.getenv('PORT', '8000')}") # Default to localhost for internal Render traffic
INTERNAL_BACKEND_URL = f"http://127.0.0.1:{os.getenv('PORT', '8000')}" # Explicitly use localhost for internal calls
BOT_API_PORT = int(os.getenv("BOT_API_PORT", "8080")) # Strictly bind the bot API to 127.0.0.1:8080
API_SECRET = resolve_api_secret()
DB_URL = os.getenv("DB_URL")
