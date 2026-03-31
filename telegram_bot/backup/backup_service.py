"""
Telegram Bot – Backup Handler
/backup_now buyrug’i: qo’lda backup ishga tushirish.
Bot scheduler: setup_backup_scheduler() (BackgroundScheduler, sync) ishlatadi.
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
    run_backup_async,
    setup_backup_scheduler,
)

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("backup_now"))
async def manual_backup_command(message: types.Message) -> None:
    """
    /backup_now – qo’lda backup ishga tushiradi (admin/texnik test uchun).
    """
    await message.answer("🔄 Backup boshlandi, iltimos kuting...")
    try:
        summary = await run_backup_async()
        failed_text = (
            f"\n❌ Xato bo’lgan markazlar: {‘, ‘.join(summary[‘failed_centers’])}"
            if summary.get("failed_centers")
            else ""
        )
        await message.answer(
            "✅ Backup yakunlandi!\n\n"
            f"📊 Jami markazlar: {summary[‘total’]}\n"
            f"📦 Yaratildi: {summary[‘backed_up’]}\n"
            f"📤 Yuborildi: {summary[‘sent’]}\n"
            f"🗄️ To’liq backup: {‘✅’ if summary.get(‘full_sent’) else ‘❌’}\n"
            f"⚠️ O’tkazib yuborildi: {summary[‘skipped’]}\n"
            f"❌ Xatolar: {summary[‘failed’]}"
            + failed_text
        )
    except Exception as exc:
        logger.exception("manual_backup_command xatosi")
        await message.answer(f"❌ Backup xatosi:\n{exc}")
