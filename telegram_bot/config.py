import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
# In Render, Django and Bot are in the same container.
# We MUST use 127.0.0.1 for internal calls.
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:10000")
API_SECRET = os.getenv("API_SECRET")
DB_URL = os.getenv("DB_URL")
