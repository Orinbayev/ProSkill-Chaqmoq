import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
# 🚨 IMPORTANT: In Render, Django and Bot are in the SAME container.
# We MUST use 127.0.0.1 for internal calls (Django <-> Bot).
# The bot's internal API should be bound to 127.0.0.1:8080.
# For external bot replies, we use the global domain.
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000") # Default to localhost for internal Render traffic
INTERNAL_BACKEND_URL = "http://127.0.0.1:8000" # Explicitly use localhost for internal calls
BOT_API_PORT = 8080 # Strictly bind the bot API to 127.0.0.1:8080
API_SECRET = os.getenv("API_SECRET")
DB_URL = os.getenv("DB_URL")
