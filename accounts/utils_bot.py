import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def send_telegram_message(telegram_id, text, reply_markup=None):
    """
    Sends a message to a user via the Telegram bot internal API.
    """
    try:
        url = f"{settings.BOT_INTERNAL_API_URL}/send_message"
        headers = {"X-API-SECRET": settings.API_SECRET}
        payload = {
            "chat_id": telegram_id,
            "text": text
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            return True
        else:
            logger.error(f"Bot API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send telegram message: {e}")
        return False
