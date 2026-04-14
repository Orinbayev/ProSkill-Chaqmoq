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

from django.db import transaction  # noqa: E402
from django.utils import timezone  # noqa: E402
from django.utils.text import slugify  # noqa: E402

from accounts.models import BotAdmin, BranchRequest, Center, DirectorCenterAccess  # noqa: E402
from billing.services import ensure_center_subscription  # noqa: E402

router = Router()
logger = logging.getLogger(__name__)


@sync_to_async
def _is_bot_admin(telegram_id: int | str) -> bool:
    return BotAdmin.objects.filter(telegram_id=str(telegram_id)).exists()


@sync_to_async
def _approve_branch_request(req_id: int):
    with transaction.atomic():
        try:
            branch_request = BranchRequest.objects.select_related(
                "requester",
                "parent_center",
            ).get(pk=req_id, status=BranchRequest.Status.PENDING)
        except BranchRequest.DoesNotExist:
            return False, "So'rov topilmadi yoki allaqachon ko'rib chiqilgan"

        base_slug = slugify(branch_request.name)[:70] or f"markaz-{req_id}"
        slug = base_slug
        index = 2
        while Center.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{index}"
            index += 1

        new_center = Center.objects.create(
            name=branch_request.name,
            address=branch_request.address,
            phone=branch_request.phone,
            slug=slug,
            plan=Center.Plan.FREE,
            status=Center.STATUS_ACTIVE,
        )

        try:
            ensure_center_subscription(new_center)
        except Exception:
            logger.exception("ensure_center_subscription failed for center_id=%s", new_center.id)

        if getattr(branch_request.requester, "role", None) == "director":
            access, created = DirectorCenterAccess.objects.get_or_create(
                director=branch_request.requester,
                center=new_center,
                defaults={
                    "is_active": True,
                    "granted_by": None,
                },
            )
            if not created and not access.is_active:
                access.is_active = True
                access.save(update_fields=["is_active"])

        branch_request.status = BranchRequest.Status.APPROVED
        branch_request.reviewed_at = timezone.now()
        branch_request.created_center = new_center
        branch_request.reject_reason = ""
        branch_request.save(
            update_fields=["status", "reviewed_at", "created_center", "reject_reason"]
        )

        return True, new_center.name


@sync_to_async
def _reject_branch_request(req_id: int):
    try:
        branch_request = BranchRequest.objects.get(
            pk=req_id,
            status=BranchRequest.Status.PENDING,
        )
    except BranchRequest.DoesNotExist:
        return False

    branch_request.status = BranchRequest.Status.REJECTED
    branch_request.reviewed_at = timezone.now()
    branch_request.save(update_fields=["status", "reviewed_at"])
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
