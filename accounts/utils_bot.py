import logging
import threading
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Login path must never wait on Telegram. Keep hard timeout short.
# Telegramga TO'G'RIDAN yuboramiz (bot internal API'ga emas) — bot alohida servisda
# yoki o'chik bo'lsa ham OTP/security-alert ishlaydi. Bog'liqlik faqat internetga.
_TELEGRAM_HTTP_TIMEOUT = float(getattr(settings, "TELEGRAM_SEND_TIMEOUT", 5.0) or 5.0)
_TELEGRAM_API_BASE = "https://api.telegram.org"


def send_telegram_message(telegram_id, text, reply_markup=None) -> bool:
    """
    Asosiy bot tokeni bilan Telegram Bot API'ga TO'G'RIDAN sendMessage yuboradi (sync).

    Returns True only when Telegram accepted the message.
    Soft-fails (False) on chat_not_found / bot blocked / network — never raises.
    """
    if not telegram_id or not text:
        return False

    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN yo'q — xabar yuborilmadi chat_id=%s", telegram_id)
        return False

    url = f"{_TELEGRAM_API_BASE}/bot{token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": telegram_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(url, json=payload, timeout=_TELEGRAM_HTTP_TIMEOUT)
    except requests.exceptions.Timeout:
        logger.warning("Telegram timeout (%ss) chat_id=%s", _TELEGRAM_HTTP_TIMEOUT, telegram_id)
        return False
    except requests.exceptions.RequestException as exc:
        logger.warning("Telegram connection failed chat_id=%s: %s", telegram_id, exc)
        return False
    except Exception as exc:
        logger.warning("Telegram unexpected error chat_id=%s: %s", telegram_id, exc)
        return False

    try:
        body = response.json()
    except ValueError:
        body = {}

    if response.status_code == 200 and body.get("ok") is True:
        return True

    # Kutilgan xatolar (chat topilmadi / bloklangan) — yumshoq, ERROR flood qilmaymiz.
    desc = str(body.get("description") or (response.text or ""))[:200]
    low = desc.lower()
    if "chat not found" in low or "chat_id is empty" in low:
        logger.info("Telegram chat not found chat_id=%s", telegram_id)
        _maybe_unlink_dead_chat(telegram_id, "chat_not_found")
        return False
    if (
        "bot was blocked" in low
        or "user is deactivated" in low
        or "forbidden" in low
        or "bot can't initiate" in low
    ):
        logger.info("Telegram bloklangan chat_id=%s: %s", telegram_id, desc)
        _maybe_unlink_dead_chat(telegram_id, "bot_blocked")
        return False

    logger.warning(
        "Telegram error status=%s chat_id=%s body=%s",
        response.status_code,
        telegram_id,
        desc,
    )
    return False


def send_telegram_message_async(telegram_id, text, reply_markup=None) -> None:
    """Fire-and-forget Telegram send — never blocks the HTTP request path."""
    if not telegram_id or not text:
        return

    def _run():
        try:
            send_telegram_message(telegram_id, text, reply_markup=reply_markup)
        except Exception as exc:
            logger.warning("async telegram send failed: %s", exc)

    threading.Thread(target=_run, name="tg-send", daemon=True).start()


def _maybe_unlink_dead_chat(telegram_id, reason: str) -> None:
    """
    If Telegram says the chat is gone, clear link flags so we stop retrying.
    Best-effort; never raise.
    """
    if reason not in {"chat_not_found", "bot_blocked", "forbidden"}:
        return
    try:
        from accounts.models import User

        updated = User.objects.filter(telegram_id=str(telegram_id), is_telegram_linked=True).update(
            is_telegram_linked=False,
        )
        if updated:
            logger.info(
                "Cleared is_telegram_linked for telegram_id=%s reason=%s count=%s",
                telegram_id,
                reason,
                updated,
            )
    except Exception as exc:
        logger.warning("unlink dead chat failed: %s", exc)
