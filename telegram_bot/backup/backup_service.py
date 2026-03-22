import asyncio
import logging
import os
import sys
from pathlib import Path

from aiogram import Router, types
from aiogram.filters import Command
from django.apps import apps

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

if not apps.ready:
    django.setup()

from core.services.db_backup_service import backup_and_send_all_centers, setup_backup_scheduler

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("backup_now"))
async def manual_backup_command(message: types.Message):
    await message.answer("🔄 Backup boshlandi...")
    summary = await asyncio.to_thread(backup_and_send_all_centers)
    await message.answer(
        "✅ Backup tugadi.\n"
        f"Jami: {summary['total']}\n"
        f"Yaratildi: {summary['backed_up']}\n"
        f"Yuborildi: {summary['sent']}\n"
        f"Umumiy arxiv: {summary.get('combined_sent', 0)}\n"
        f"O‘tkazib yuborildi: {summary['skipped']}\n"
        f"Xatolar: {summary['failed']}"
    )
