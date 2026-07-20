import logging
import threading
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Login path must never wait on Telegram. Keep hard timeout short.
_TELEGRAM_HTTP_TIMEOUT = float(getattr(settings, "TELEGRAM_INTERNAL_TIMEOUT", 2.0) or 2.0)


def send_telegram_message(telegram_id, text, reply_markup=None) -> bool:
    """
    Sends a message via the Telegram bot internal API (sync).

    Returns True only when Telegram accepted the message.
    Soft-fails (False) on chat_not_found / bot blocked / network — never raises.
    """
    if not telegram_id or not text:
        return False

    url = f"{settings.BOT_INTERNAL_API_URL.rstrip('/')}/send_message"
    headers = {"X-API-SECRET": settings.API_SECRET}
    payload: dict[str, Any] = {
        "chat_id": telegram_id,
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=_TELEGRAM_HTTP_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        logger.warning("Bot API timeout (%ss) chat_id=%s", _TELEGRAM_HTTP_TIMEOUT, telegram_id)
        return False
    except requests.exceptions.RequestException as exc:
        logger.warning("Bot API connection failed chat_id=%s: %s", telegram_id, exc)
        return False
    except Exception as exc:
        logger.warning("Bot API unexpected error chat_id=%s: %s", telegram_id, exc)
        return False

    if response.status_code == 200:
        try:
            body = response.json()
        except ValueError:
            return True
        reason = str(body.get("reason") or "")
        if body.get("status") == "skipped" or reason in {
            "chat_not_found",
            "bot_blocked",
            "forbidden",
        }:
            logger.info(
                "Telegram skip chat_id=%s reason=%s",
                telegram_id,
                reason or body.get("status"),
            )
            _maybe_unlink_dead_chat(telegram_id, reason)
            return False
        return True

    # Non-200: soft fail (do not flood ERROR for expected TG issues)
    snippet = (response.text or "")[:200]
    if response.status_code >= 500 and "chat not found" in snippet.lower():
        logger.info("Telegram chat not found chat_id=%s", telegram_id)
        _maybe_unlink_dead_chat(telegram_id, "chat_not_found")
        return False
    logger.warning(
        "Bot API error status=%s chat_id=%s body=%s",
        response.status_code,
        telegram_id,
        snippet,
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
