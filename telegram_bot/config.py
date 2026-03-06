import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
# In Render, Django runs on $PORT (usually 10000).
# We use 127.0.0.1:10000 for internal communication between Bot and Django.
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:10000")
API_SECRET = os.getenv("API_SECRET") # Shared secret
DB_URL = os.getenv("DB_URL") # PostgreSQL URL if shared
