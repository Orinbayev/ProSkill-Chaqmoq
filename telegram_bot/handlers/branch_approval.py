"""
SuperAdmin Telegram botda filial so'rovlarini tasdiqlash/rad etish handleri.
"""

import logging
import os
import sys
from pathlib import Path

from aiogram import F, Router, html
from aiogram.types import CallbackQuery
from asgiref.sync import sync_to_async

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    from django.apps import apps as django_apps
    import django

    if not django_apps.ready:
        django.setup()
except Exception as setup_error:
    logging.getLogger(__name__).error("Django setup xatosi branch_approval.py: %s", setup_error)

from accounts.models import BotAdmin, BranchRequest  # noqa: E402
from accounts.services import branch_requests as branch_service  # noqa: E402

router = Router()
logger = logging.getLogger(__name__)


@sync_to_async
def _is_bot_admin(telegram_id: int | str) -> bool:
    tid = str(telegram_id)
    # 1. BotAdmin jadvalida bormi?
    if BotAdmin.objects.filter(telegram_id=tid).exists():
        return True
    # 2. Django superuser bo'lib telegram_id to'g'ri kelsa ham ruxsat ber
    from accounts.models import User as DjangoUser
    if DjangoUser.objects.filter(is_superuser=True, telegram_id=tid).exists():
        return True
    # 3. Agar BotAdmin jadvali bo'sh bo'lsa (hali sozlanmagan) — har qanday admin o'ta olsin
    if not BotAdmin.objects.exists():
        logger.warning(
            "BotAdmin jadvali bo'sh — telegram_id=%s ga vaqtincha ruxsat berildi. "
            "Django admin panelida BotAdmin qo'shib qo'ying!",
            tid,
        )
        return True
    return False


@sync_to_async
def _approve_branch_request(req_id: int):
    """Tasdiqlash. Mantiq `accounts.services.branch_requests` da — u yagona manba,
    shu bilan Django admin va superadmin paneli ham bir xil ish qiladi."""
    try:
        branch_request = BranchRequest.objects.get(pk=req_id)
    except BranchRequest.DoesNotExist:
        return False, "So'rov topilmadi"

    try:
        markaz = branch_service.tasdiqla(branch_request)
    except branch_service.FilialXatosi as xato:
        return False, str(xato)

    return True, markaz.name


@sync_to_async
def _reject_branch_request(req_id: int):
    try:
        branch_request = BranchRequest.objects.get(pk=req_id)
    except BranchRequest.DoesNotExist:
        return False

    try:
        branch_service.rad_et(branch_request)
    except branch_service.FilialXatosi:
        return False
    return True


@router.callback_query(F.data.startswith("branch_approve:"))
async def handle_branch_approve(callback: CallbackQuery):
    if not await _is_bot_admin(callback.from_user.id):
        await callback.answer("⚠️ Ruxsat yo'q", show_alert=True)
        return

    req_id = int(callback.data.split(":", 1)[1])
    success, info = await _approve_branch_request(req_id)

    if success:
        original_text = callback.message.html_text or callback.message.text or ""
        await callback.message.edit_text(
            original_text + f"\n\n✅ <b>TASDIQLANDI</b> — {html.quote(info)} markazi yaratildi!",
            parse_mode="HTML",
            reply_markup=None,
        )
        await callback.answer("✅ Tasdiqlandi!")
    else:
        await callback.answer(f"⚠️ {info}", show_alert=True)


@router.callback_query(F.data.startswith("branch_reject:"))
async def handle_branch_reject(callback: CallbackQuery):
    if not await _is_bot_admin(callback.from_user.id):
        await callback.answer("⚠️ Ruxsat yo'q", show_alert=True)
        return

    req_id = int(callback.data.split(":", 1)[1])
    ok = await _reject_branch_request(req_id)

    if ok:
        original_text = callback.message.html_text or callback.message.text or ""
        await callback.message.edit_text(
            original_text + "\n\n❌ <b>RAD ETILDI</b>",
            parse_mode="HTML",
            reply_markup=None,
        )
        await callback.answer("❌ Rad etildi")
    else:
        await callback.answer("⚠️ So'rov topilmadi", show_alert=True)
