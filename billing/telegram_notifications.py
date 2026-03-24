from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_bot_token() -> str:
    return str(getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()


async def _send_message_async(token: str, chat_id: str, text: str) -> None:
    bot = Bot(token=token)
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    finally:
        await bot.session.close()


def _format_amount(amount) -> str:
    try:
        value = int(amount)
    except (TypeError, ValueError):
        return "0"
    return f"{value:,}".replace(",", " ")


def send_payment_success_notification(
    user,
    plan_name: str,
    end_date,
    *,
    center_name: str | None = None,
    duration_months: int | None = None,
    paid_amount: int | None = None,
) -> bool:
    """
    Send payment confirmation to linked Telegram account.
    Uses official Telegram API via aiogram.
    """
    token = _get_bot_token()
    chat_id = str(getattr(user, "telegram_id", "") or "").strip()

    if not token:
        logger.info("Telegram notify skipped: TELEGRAM_BOT_TOKEN missing")
        return False
    if not chat_id:
        logger.info("Telegram notify skipped: user_id=%s has no telegram_id", getattr(user, "id", None))
        return False

    if hasattr(end_date, "strftime"):
        formatted_end_date = end_date.strftime("%d.%m.%Y")
    else:
        formatted_end_date = timezone.localdate().strftime("%d.%m.%Y")

    safe_center_name = (center_name or "Noma'lum markaz").strip() or "Noma'lum markaz"
    try:
        safe_months = int(duration_months or 1)
    except (TypeError, ValueError):
        safe_months = 1
    if safe_months <= 0:
        safe_months = 1

    amount_text = _format_amount(paid_amount)

    text = (
        "To'lov qabul qilindi ✅\n"
        f"Markaz: {safe_center_name}\n"
        f"Tarif: {plan_name}\n"
        f"Muddat: {safe_months} oy\n"
        f"To'langan summa: {amount_text} so'm\n"
        f"Amal qilish muddati: {formatted_end_date}"
    )

    try:
        asyncio.run(_send_message_async(token=token, chat_id=chat_id, text=text))
        logger.info("Telegram payment notification sent: user_id=%s chat_id=%s", getattr(user, "id", None), chat_id)
        return True
    except RuntimeError:
        # Fallback for environments where a loop is already running.
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_send_message_async(token=token, chat_id=chat_id, text=text))
            logger.info("Telegram payment notification sent in fallback loop: user_id=%s", getattr(user, "id", None))
            return True
        except Exception:
            logger.exception("Telegram notify failed in fallback loop: user_id=%s", getattr(user, "id", None))
            return False
        finally:
            loop.close()
    except Exception:
        logger.exception("Telegram notify failed: user_id=%s", getattr(user, "id", None))
        return False
