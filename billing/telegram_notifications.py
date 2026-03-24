from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_bot_token() -> str:
    return str(getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()


def _get_group_chat_id() -> str:
    return str(getattr(settings, "TELEGRAM_GROUP_ID", "") or "").strip()


async def _send_message_async(token: str, chat_id: str, text: str) -> None:
    bot = Bot(token=token)
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    finally:
        await bot.session.close()


def _send_message(token: str, chat_id: str, text: str, *, log_label: str) -> bool:
    try:
        asyncio.run(_send_message_async(token=token, chat_id=chat_id, text=text))
        logger.info("Telegram %s sent: chat_id=%s", log_label, chat_id)
        return True
    except RuntimeError:
        # Fallback for environments where a loop is already running.
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_send_message_async(token=token, chat_id=chat_id, text=text))
            logger.info("Telegram %s sent in fallback loop: chat_id=%s", log_label, chat_id)
            return True
        except Exception:
            logger.exception("Telegram %s failed in fallback loop: chat_id=%s", log_label, chat_id)
            return False
        finally:
            loop.close()
    except Exception:
        logger.exception("Telegram %s failed: chat_id=%s", log_label, chat_id)
        return False


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

    return _send_message(token=token, chat_id=chat_id, text=text, log_label="user payment notification")


def send_payment_group_receipt_notification(
    *,
    center_name: str,
    plan_name: str,
    duration_months: int,
    paid_amount: int,
    end_date,
    click_trans_id: str = "",
    merchant_trans_id: str = "",
    request_id: int | None = None,
) -> bool:
    """
    Send payment receipt summary to the configured Telegram group/channel.
    """
    token = _get_bot_token()
    chat_id = _get_group_chat_id()

    if not token:
        logger.info("Telegram group receipt skipped: TELEGRAM_BOT_TOKEN missing")
        return False
    if not chat_id:
        logger.info("Telegram group receipt skipped: TELEGRAM_GROUP_ID missing")
        return False

    if hasattr(end_date, "strftime"):
        formatted_end_date = end_date.strftime("%d.%m.%Y")
    else:
        formatted_end_date = timezone.localdate().strftime("%d.%m.%Y")

    safe_center_name = (center_name or "Noma'lum markaz").strip() or "Noma'lum markaz"
    safe_plan_name = (plan_name or "Noma'lum tarif").strip() or "Noma'lum tarif"
    try:
        safe_months = int(duration_months or 1)
    except (TypeError, ValueError):
        safe_months = 1
    if safe_months <= 0:
        safe_months = 1

    amount_text = _format_amount(paid_amount)
    service_id = str(getattr(settings, "CLICK_SERVICE_ID", "") or "").strip() or "-"
    merchant_id = str(getattr(settings, "CLICK_MERCHANT_ID", "") or "").strip() or "-"

    text = (
        "Click to'lovi qabul qilindi\n"
        f"Markaz: {safe_center_name}\n"
        f"Tarif: {safe_plan_name}\n"
        f"Muddat: {safe_months} oy\n"
        f"Summa: {amount_text} so'm\n"
        f"Order ID: {request_id or '-'}\n"
        f"Click trans ID: {click_trans_id or '-'}\n"
        f"Merchant trans ID: {merchant_trans_id or '-'}\n"
        f"Service/Merchant: {service_id}/{merchant_id}\n"
        f"Amal qilish muddati: {formatted_end_date}\n"
        "Holat: muvaffaqiyatli"
    )

    return _send_message(token=token, chat_id=chat_id, text=text, log_label="group payment receipt")
