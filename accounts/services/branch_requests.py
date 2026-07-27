"""Filial so'rovlarini tasdiqlash / rad etish — yagona manba.

Nega alohida modul?

Ilgari tasdiqlash mantig'i faqat Telegram bot handleri ichida edi
(`telegram_bot/handlers/branch_approval.py`). Natijada Django admin'da
`status` maydonini qo'lda "approved" qilib qo'yish **hech narsa yaratmasdi**:
markaz ochilmasdi, direktorga ruxsat berilmasdi — filial ro'yxatda
ko'rinmasdi. Ya'ni tasdiqlangandek ko'rinardi, aslida esa yo'q.

Endi tasdiqlashning bitta yo'li bor — shu yerdagi `tasdiqla()`. Telegram
bot ham, Django admin ham, superadmin paneli ham aynan shuni chaqiradi.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import BranchRequest, Center, DirectorCenterAccess

logger = logging.getLogger(__name__)


class FilialXatosi(Exception):
    """So'rovni ko'rib chiqib bo'lmadi (holati mos emas va h.k.)."""


def _bosh_slug(nom: str, req_id: int) -> str:
    """Band bo'lmagan slug tanlaydi.

    O'chirilgan markazlar ham hisobga olinadi: `Center.slug` unique, va
    soft-delete qilingan qator bazada qoladi — shuning uchun `all_objects`
    bo'yicha tekshiramiz, aks holda IntegrityError chiqadi.
    """
    baza = slugify(nom)[:70] or f"markaz-{req_id}"
    manager = getattr(Center, "all_objects", Center.objects)

    slug = baza
    raqam = 2
    while manager.filter(slug=slug).exists():
        slug = f"{baza}-{raqam}"
        raqam += 1
    return slug


@transaction.atomic
def tasdiqla(branch_request: BranchRequest, *, reviewer=None) -> Center:
    """So'rovni tasdiqlaydi va yangi filial-markazni yaratadi.

    Qaytaradi: yaratilgan (yoki avval yaratilgan) `Center`.

    Idempotent: allaqachon tasdiqlangan va markazi bor so'rov qayta
    chaqirilsa, yangi markaz ochilmaydi — mavjudi qaytariladi. Bu muhim,
    chunki Telegram tugmasi ikki marta bosilishi mumkin.
    """
    # Poyga holatidan himoya: bir vaqtda bot ham, panel ham bosilishi mumkin.
    so_rov = (
        BranchRequest.objects
        .select_for_update()
        .select_related("requester", "parent_center")
        .get(pk=branch_request.pk)
    )

    if so_rov.status == BranchRequest.Status.APPROVED and so_rov.created_center_id:
        return so_rov.created_center

    if so_rov.status == BranchRequest.Status.REJECTED:
        raise FilialXatosi("Bu so'rov rad etilgan — qaytadan tasdiqlab bo'lmaydi.")

    if so_rov.parent_center is None:
        raise FilialXatosi("So'rovning asosiy markazi topilmadi.")

    # Subscription doim eng yuqori markazdan olinadi, filialga alohida kerak emas.
    root_center = so_rov.parent_center.get_root_center()

    yangi_markaz = Center.objects.create(
        name=so_rov.name,
        address=so_rov.address,
        phone=so_rov.phone,
        slug=_bosh_slug(so_rov.name, so_rov.pk),
        plan=root_center.plan,
        status=Center.STATUS_ACTIVE,
        parent_center=root_center,
    )

    # Signal yoki boshqa joy avtomatik obuna yaratgan bo'lsa — o'chiramiz.
    # Import shu yerda: billing → accounts aylanma importini oldini oladi.
    from billing.models import CenterSubscription

    CenterSubscription.objects.filter(center=yangi_markaz).delete()

    # ASOSIY: direktor filialni ko'rishi uchun shu ruxsat kerak.
    # Markaz almashtirgich (`director_centers`) aynan shu jadvaldan o'qiydi —
    # busiz filial yaratilsa ham ro'yxatda ko'rinmaydi.
    if getattr(so_rov.requester, "role", None) == "director":
        ruxsat, yaratildi = DirectorCenterAccess.objects.get_or_create(
            director=so_rov.requester,
            center=yangi_markaz,
            defaults={"is_active": True, "granted_by": reviewer},
        )
        if not yaratildi and not ruxsat.is_active:
            ruxsat.is_active = True
            ruxsat.save(update_fields=["is_active"])

    so_rov.status = BranchRequest.Status.APPROVED
    so_rov.reviewed_at = timezone.now()
    so_rov.created_center = yangi_markaz
    so_rov.reject_reason = ""
    so_rov.save(
        update_fields=["status", "reviewed_at", "created_center", "reject_reason"]
    )

    logger.info(
        "Filial so'rovi #%s tasdiqlandi → markaz #%s (%s), direktor: %s",
        so_rov.pk, yangi_markaz.pk, yangi_markaz.name, so_rov.requester_id,
    )
    return yangi_markaz


@transaction.atomic
def rad_et(branch_request: BranchRequest, *, sabab: str = "", reviewer=None) -> None:
    """So'rovni rad etadi. Tasdiqlangan so'rovga tegmaydi."""
    so_rov = (
        BranchRequest.objects
        .select_for_update()
        .get(pk=branch_request.pk)
    )

    if so_rov.status == BranchRequest.Status.APPROVED:
        raise FilialXatosi(
            "Bu so'rov allaqachon tasdiqlangan — markaz yaratilgan. "
            "Rad etish o'rniga markazni bloklang."
        )

    if so_rov.status == BranchRequest.Status.REJECTED:
        return

    so_rov.status = BranchRequest.Status.REJECTED
    so_rov.reviewed_at = timezone.now()
    so_rov.reject_reason = (sabab or "").strip()
    so_rov.save(update_fields=["status", "reviewed_at", "reject_reason"])

    logger.info("Filial so'rovi #%s rad etildi (%s)", so_rov.pk, so_rov.reject_reason)
