import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def notify_telegram_new_lead(lead):
    """
    Telegram token yoki chat id yo'q bo'lsa funksiyani jim o'tkazamiz.
    Prod'da lead submit oqimi hech qachon yiqilmaydi.
    """
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(settings, "TELEGRAM_GROUP_ID", "")
    if not token or not chat_id:
        return False

    text = (
        "Yangi demo so'rovi!\n\n"
        f"Ism: {lead.full_name}\n"
        f"Markaz: {lead.center_name}\n"
        f"Telefon: {lead.phone}\n"
        f"Viloyat: {lead.get_region_display_uz()}"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    try:
        response = requests.post(url, data=payload, timeout=8)
        response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("Telegram lead notification yuborilmadi: %s", exc)
        return False
