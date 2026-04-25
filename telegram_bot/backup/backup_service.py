"""
Telegram Bot backup handlers.

/db va /backup_now faqat TELEGRAM_BACKUP_CHAT_ID ichida va adminlardan ishlaydi.
"""

import logging
import os
import sys
from pathlib import Path

from aiogram import Router, types
from aiogram.filters import Command

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    from django.apps import apps as _dapps
    import django as _django
    if not _dapps.ready:
        _django.setup()
except Exception as _setup_err:
    logging.getLogger(__name__).error(
        "Django setup xatosi backup_service.py: %s", _setup_err
    )

from core.services.db_backup_service import (  # noqa: E402
    is_authorized_telegram_backup_request,
    run_backup_async,
    setup_backup_scheduler,
)

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("db", "backup_now"))
async def manual_backup_command(message: types.Message) -> None:
    """
    /db – shu zahoti backup yaratadi va ruxsat berilgan Telegram guruhga yuboradi.
    """
    chat_id = getattr(getattr(message, "chat", None), "id", None)
    user_id = getattr(getattr(message, "from_user", None), "id", None)
    allowed, reason = is_authorized_telegram_backup_request(chat_id, user_id)
    if not allowed:
        await message.answer(f"⛔ {reason}")
        logger.warning("Unauthorized /db command: chat_id=%s user_id=%s reason=%s", chat_id, user_id, reason)
        return

    await message.answer("⏳ Database backup tayyorlanmoqda...")
    try:
        summary = await run_backup_async(notify_start=False, notify_finish=False, notify_error=False)
        if summary.get("failed"):
            error_text = summary.get("fatal_error") or "Backup jarayonida xatolik bor"
            await message.answer(f"❌ Backup yuborilmadi: {error_text}")
            return

        failed_text = (
            f"\n❌ Xato bo'lgan markazlar: {', '.join(summary['failed_centers'])}"
            if summary.get("failed_centers")
            else ""
        )
        fatal_text = (
            f"\n🧭 Sabab: {summary['fatal_error']}"
            if summary.get("fatal_error")
            else ""
        )
        await message.answer(
            "✅ Database backup yuborildi.\n\n"
            f"📊 Jami markazlar: {summary['total']}\n"
            f"📦 Yaratildi: {summary['backed_up']}\n"
            f"📤 Yuborildi: {summary['sent']}\n"
            f"🗄️ Global backup: {'✅' if summary.get('full_sent') else '❌'}\n"
            f"⚠️ O'tkazib yuborildi: {summary['skipped']}\n"
            f"❌ Xatolar: {summary['failed']}"
            + failed_text
            + fatal_text
        )
    except Exception as exc:
        logger.exception("manual_backup_command xatosi")
        await message.answer(f"❌ Backup xatosi:\n{exc}")
