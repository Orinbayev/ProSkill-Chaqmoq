"""Markazga kirish ruxsatlarini berish / olib tashlash — yagona manba.

Nega alohida modul?

Ilgari `DirectorCenterAccess` yozuvi faqat `branch_requests.tasdiqla()`
ichida, faqat so'rov beruvchi uchun yaratilardi. Natijada:

  • bir direktor yaratgan filial ikkinchi direktorga ko'rinmasdi;
  • o'qituvchi uchun bunday mexanizm umuman yo'q edi.

Endi ruxsat berishning bitta yo'li bor — shu moduldagi funksiyalar.
Filial servisi, superadmin paneli, direktor paneli va Telegram bot
hammasi aynan shuni chaqiradi.

XAVFSIZLIK QOIDASI (multi-tenancy):
Ruxsat faqat **bitta markaz daraxti** ichida beriladi. Ya'ni direktor
yoki o'qituvchi faqat o'z root markazining filiallariga biriktirilishi
mumkin. Boshqa mijozning markaziga ruxsat berish — IDOR, shuning uchun
`same_tree_or_raise()` har bir grant oldidan chaqiriladi.
"""

from __future__ import annotations

import logging

from django.db import transaction

from accounts.models import (
    Center,
    DirectorCenterAccess,
    Roles,
    TeacherCenterAccess,
    User,
)

logger = logging.getLogger(__name__)


class RuxsatXatosi(Exception):
    """Ruxsat berib bo'lmadi (rol mos emas, boshqa markaz daraxti va h.k.)."""


# ══════════════════════════════════════════════════════════════════
#  YORDAMCHILAR
# ══════════════════════════════════════════════════════════════════

def center_tree_ids(root_center: Center) -> set[int]:
    """Root markaz + uning barcha filiallari (rekursiv) ID lari.

    BITTA query bilan ishlaydi: butun daraxt xotirada quriladi, shuning
    uchun har filial uchun alohida so'rov ketmaydi (N+1 yo'q).
    """
    if root_center is None:
        return set()

    root = root_center.get_root_center()

    # Bitta so'rov: shu root'ga tegishli bo'lishi mumkin bo'lgan barcha markazlar.
    # `parent_center_id` xaritasini qurib, keyin xotirada bog'lab chiqamiz.
    juftlar = list(
        Center.objects.filter(is_deleted=False).values_list("id", "parent_center_id")
    )
    bolalar: dict[int | None, list[int]] = {}
    for cid, pid in juftlar:
        bolalar.setdefault(pid, []).append(cid)

    natija = {root.id}
    navbat = [root.id]
    while navbat:
        joriy = navbat.pop()
        for bola in bolalar.get(joriy, ()):
            if bola not in natija:
                natija.add(bola)
                navbat.append(bola)
    return natija


def center_root_map() -> dict[int, int]:
    """`{center_id: root_center_id}` — barcha markazlar uchun, BITTA query.

    Nega kerak? Panelda "bu filialga qaysi direktorlarni biriktirish mumkin?"
    savoliga javob berish uchun har bir markaz uchun `get_root_center()`
    chaqirish rekursiv query zanjirini (N+1) keltirib chiqaradi. Bu xarita
    esa bitta so'rovdan keyin xotirada ishlaydi.
    """
    juftlar = list(
        Center.objects.filter(is_deleted=False).values_list("id", "parent_center_id")
    )
    ota = dict(juftlar)

    xarita: dict[int, int] = {}

    def _root(cid: int) -> int:
        yol = []
        joriy = cid
        # Ehtiyot: ma'lumotda tsikl bo'lsa ham cheksiz aylanmaymiz.
        korilgan = set()
        while True:
            if joriy in xarita:
                ildiz = xarita[joriy]
                break
            if joriy in korilgan:
                ildiz = joriy
                break
            korilgan.add(joriy)
            yol.append(joriy)
            pid = ota.get(joriy)
            if not pid or pid not in ota:
                ildiz = joriy
                break
            joriy = pid
        for node in yol:
            xarita[node] = ildiz
        return ildiz

    for cid in ota:
        _root(cid)
    return xarita


def same_tree_or_raise(user: User, center: Center) -> None:
    """Foydalanuvchi va markaz bitta markaz daraxtida ekanini tekshiradi.

    Bu — cross-tenant ruxsat berishning oldini oluvchi asosiy to'siq.
    Foydalanuvchining o'z markazi (`user.center`) root'i markazning root'i
    bilan bir xil bo'lishi shart.
    """
    if center is None:
        raise RuxsatXatosi("Markaz topilmadi.")

    user_center = getattr(user, "center", None)
    if user_center is None:
        raise RuxsatXatosi(
            f"{user} uchun asosiy markaz belgilanmagan — ruxsat berib bo'lmaydi."
        )

    if user_center.get_root_center().id != center.get_root_center().id:
        raise RuxsatXatosi(
            "Boshqa markaz daraxtidagi filialga ruxsat berib bo'lmaydi."
        )


# ══════════════════════════════════════════════════════════════════
#  DIREKTOR RUXSATI
# ══════════════════════════════════════════════════════════════════

@transaction.atomic
def grant_director_access(
    director: User,
    center: Center,
    *,
    granted_by: User | None = None,
    check_tree: bool = True,
) -> DirectorCenterAccess | None:
    """Direktorga markaz ruxsatini beradi (idempotent).

    Mavjud, lekin `is_active=False` yozuv bo'lsa — qayta yoqiladi.
    Rol direktor bo'lmasa `None` qaytaradi (xato tashlamaydi: filial
    tasdiqlash oqimi buzilmasligi kerak).

    check_tree=False — faqat filial YARATILAYOTGAN paytda ishlatiladi:
    yangi markaz allaqachon root ostida ochilgan, lekin direktorning
    `user.center` i boshqa filial bo'lishi mumkin (bu normal holat).
    """
    if director is None or center is None:
        return None
    if getattr(director, "role", None) != Roles.DIREKTOR:
        logger.info(
            "grant_director_access: %s roli direktor emas (%s) — o'tkazib yuborildi",
            director, getattr(director, "role", None),
        )
        return None

    if check_tree:
        same_tree_or_raise(director, center)

    ruxsat, yaratildi = DirectorCenterAccess.objects.get_or_create(
        director=director,
        center=center,
        defaults={"is_active": True, "granted_by": granted_by},
    )
    if not yaratildi and not ruxsat.is_active:
        ruxsat.is_active = True
        ruxsat.granted_by = granted_by or ruxsat.granted_by
        ruxsat.save(update_fields=["is_active", "granted_by"])

    logger.info(
        "Direktor ruxsati: %s → markaz #%s (%s) [%s]",
        director.email, center.id, center.name,
        "yangi" if yaratildi else "qayta yoqildi/mavjud",
    )
    return ruxsat


@transaction.atomic
def revoke_director_access(director: User, center: Center) -> bool:
    """Direktor ruxsatini o'chiradi (soft: is_active=False). Yozuv tarixda qoladi."""
    updated = DirectorCenterAccess.objects.filter(
        director=director, center=center, is_active=True
    ).update(is_active=False)
    return bool(updated)


# ══════════════════════════════════════════════════════════════════
#  O'QITUVCHI RUXSATI
# ══════════════════════════════════════════════════════════════════

@transaction.atomic
def grant_teacher_access(
    teacher: User,
    center: Center,
    *,
    granted_by: User | None = None,
    note: str = "",
    check_tree: bool = True,
) -> TeacherCenterAccess:
    """O'qituvchiga filialda ishlash ruxsatini beradi (idempotent).

    Shundan keyin o'qituvchi BITTA login/parol bilan kirib, markaz
    almashtirgichda shu filialga o'tishi mumkin bo'ladi.
    """
    if teacher is None:
        raise RuxsatXatosi("O'qituvchi topilmadi.")
    if center is None:
        raise RuxsatXatosi("Markaz topilmadi.")
    if getattr(teacher, "role", None) != Roles.OQITUVCHI:
        raise RuxsatXatosi("Faqat o'qituvchi rolidagi foydalanuvchiga ruxsat beriladi.")

    if check_tree:
        same_tree_or_raise(teacher, center)

    # O'z asosiy markaziga ruxsat yozish shart emas — `user.center` allaqachon beradi.
    if teacher.center_id and int(teacher.center_id) == int(center.id):
        raise RuxsatXatosi(
            "Bu o'qituvchining asosiy markazi — qo'shimcha ruxsat kerak emas."
        )

    ruxsat, yaratildi = TeacherCenterAccess.objects.get_or_create(
        teacher=teacher,
        center=center,
        defaults={"is_active": True, "granted_by": granted_by, "note": note},
    )
    if not yaratildi:
        maydonlar = []
        if not ruxsat.is_active:
            ruxsat.is_active = True
            maydonlar.append("is_active")
        if granted_by is not None and ruxsat.granted_by_id != granted_by.pk:
            ruxsat.granted_by = granted_by
            maydonlar.append("granted_by")
        if note and ruxsat.note != note:
            ruxsat.note = note
            maydonlar.append("note")
        if maydonlar:
            ruxsat.save(update_fields=maydonlar)

    logger.info(
        "O'qituvchi ruxsati: %s → markaz #%s (%s) [%s]",
        teacher.email, center.id, center.name,
        "yangi" if yaratildi else "yangilandi",
    )
    return ruxsat


@transaction.atomic
def revoke_teacher_access(teacher: User, center: Center) -> bool:
    """O'qituvchi ruxsatini o'chiradi (soft: is_active=False).

    Yozuv tarixda qoladi — kim bergan/qachon ma'lumoti yo'qolmaydi.
    """
    updated = TeacherCenterAccess.objects.filter(
        teacher=teacher, center=center, is_active=True
    ).update(is_active=False)
    if updated:
        logger.info(
            "O'qituvchi ruxsati olib tashlandi: %s ← markaz #%s",
            getattr(teacher, "email", teacher), getattr(center, "id", center),
        )
    return bool(updated)


# ══════════════════════════════════════════════════════════════════
#  O'QISH (middleware + view'lar uchun)
# ══════════════════════════════════════════════════════════════════

def accessible_centers(user: User):
    """`User.accessible_centers()` uchun qulay o'ram (bitta query)."""
    return user.accessible_centers().select_related("parent_center")


def has_center_access(user: User, center_id) -> bool:
    """`User.has_center_access()` uchun qulay o'ram."""
    return user.has_center_access(center_id)


def teacher_access_rows(center: Center):
    """Markazdagi (filialdagi) mehmon o'qituvchilar ro'yxati — panel uchun."""
    return (
        TeacherCenterAccess.objects
        .filter(center=center, is_active=True)
        .select_related("teacher", "granted_by")
        .order_by("teacher__familya", "teacher__ism")
    )
