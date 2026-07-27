"""Real duel uchun raqib qidirish (matchmaking).

Oqim:

    1. O'quvchi duel boshlaydi → navbatga tushadi.
    2. Ilova har 2 soniyada navbat holatini so'raydi (polling).
    3. Shu vaqt ichida boshqa o'quvchi ham navbatga kelsa — ikkalasi juftlanadi
       va **bir xil savollar** bilan o'ynaydi.
    4. `NAVBAT_KUTISH_SONIYA` ichida hech kim kelmasa — robot raqib qo'yiladi.

WebSocket ataylab ishlatilmadi: Render'dagi bitta worker bilan uzoq ulanishlarni
ushlab turish qimmat, polling esa arzon va ishonchli.

Halollik uchun ikkala o'yinchi ham:
  • aynan bir xil savollarni,
  • aynan bir xil variantlar tartibida oladi.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .cooldowns import qulfni_yangila
from .models import Duel, DuelQuestion, DuelQueue, GameMode
from .services import (
    NAVBAT_ESKIRISH_SONIYA,
    NAVBAT_KUTISH_SONIYA,
    duel_boshla,
    profil_ol,
)


def _eskirganlarni_tozala() -> None:
    """Ilova yopilib qolgan navbat yozuvlarini bekor qiladi."""
    chegara = timezone.now() - timezone.timedelta(seconds=NAVBAT_ESKIRISH_SONIYA)
    DuelQueue.objects.filter(
        holat=DuelQueue.KUTMOQDA, yaratilgan__lt=chegara
    ).update(holat=DuelQueue.BEKOR)


def _juft_duel_yarat(
    mode: GameMode,
    a_navbat: DuelQueue,
    b_navbat: DuelQueue,
    savollar: list,
) -> tuple[Duel, Duel]:
    """Ikki o'yinchi uchun bir xil savolli juft duel yaratadi."""
    a_profil = profil_ol(a_navbat.user, a_navbat.center)
    b_profil = profil_ol(b_navbat.user, b_navbat.center)

    # Jon va o'yin qulfi aynan shu yerda — duel haqiqatan boshlanganda.
    # Navbatda turishning o'zi jon yemaydi: raqib topilmasa o'quvchi bekorga
    # jon yo'qotmasligi kerak (robotga o'tganda `duel_boshla` o'zi yechadi).
    for profil in (a_profil, b_profil):
        for _ in range(mode.jon_narxi):
            profil.jon_sarfla()
        qulfni_yangila(profil, mode)

    a_duel = Duel.objects.create(
        oyinchi=a_navbat.user,
        center=a_navbat.center,
        mode=mode,
        raqib=b_profil,
        raqib_nomi=b_profil.nomi,
        pvp=True,
    )
    b_duel = Duel.objects.create(
        oyinchi=b_navbat.user,
        center=b_navbat.center,
        mode=mode,
        raqib=a_profil,
        raqib_nomi=a_profil.nomi,
        pvp=True,
    )
    a_duel.juft = b_duel
    b_duel.juft = a_duel
    a_duel.save(update_fields=["juft"])
    b_duel.save(update_fields=["juft"])

    # Variantlar bir marta aralashtiriladi va ikkalasiga bir xil beriladi —
    # aks holda bittasiga "osonroq" tartib tushib qolishi mumkin edi.
    qatorlar = []
    for tartib, savol in enumerate(savollar, start=1):
        variantlar = savol.variantlar()
        for duel in (a_duel, b_duel):
            qatorlar.append(
                DuelQuestion(
                    duel=duel,
                    savol=savol,
                    tartib=tartib,
                    variantlar=variantlar,
                )
            )
    DuelQuestion.objects.bulk_create(qatorlar)

    return a_duel, b_duel


def navbatga_qoy(user, center, mode: GameMode, savollar: list) -> tuple[DuelQueue, Duel | None]:
    """Navbatga qo'yadi. Kutayotgan raqib bo'lsa darhol juftlaydi.

    Qaytaradi: (navbat yozuvi, duel yoki None).
    """
    _eskirganlarni_tozala()

    with transaction.atomic():
        # Eski kutayotgan yozuvlarimni bekor qilamiz — bir vaqtda bitta navbat.
        DuelQueue.objects.filter(user=user, holat=DuelQueue.KUTMOQDA).update(
            holat=DuelQueue.BEKOR
        )

        # Raqib: shu o'yinda kutayotgan boshqa o'quvchi.
        # `select_for_update` — ikki so'rov bir vaqtda bitta raqibni olmasin.
        raqib = (
            DuelQueue.objects.select_for_update(skip_locked=True)
            .filter(holat=DuelQueue.KUTMOQDA, mode=mode)
            .exclude(user=user)
            .order_by("yaratilgan")
            .first()
        )

        menim = DuelQueue.objects.create(user=user, center=center, mode=mode)

        if raqib is None:
            return menim, None

        a_duel, b_duel = _juft_duel_yarat(mode, menim, raqib, savollar)

        menim.holat = DuelQueue.TOPILDI
        menim.duel = a_duel
        menim.save(update_fields=["holat", "duel"])

        raqib.holat = DuelQueue.TOPILDI
        raqib.duel = b_duel
        raqib.save(update_fields=["holat", "duel"])

        return menim, a_duel


def navbat_holati(navbat: DuelQueue) -> tuple[str, Duel | None]:
    """Navbat holatini qaytaradi: ("topildi"|"kutmoqda"|"vaqt_tugadi", duel)."""
    navbat.refresh_from_db()

    if navbat.holat == DuelQueue.TOPILDI and navbat.duel_id:
        return "topildi", navbat.duel

    if navbat.holat == DuelQueue.BEKOR:
        return "vaqt_tugadi", None

    o_tgan = (timezone.now() - navbat.yaratilgan).total_seconds()
    if o_tgan >= NAVBAT_KUTISH_SONIYA:
        return "vaqt_tugadi", None

    return "kutmoqda", None


def robotga_otkaz(navbat: DuelQueue) -> tuple[Duel | None, str]:
    """Raqib topilmadi — robot bilan duel ochadi.

    Jon va o'yin qulfi shu yerda qo'yiladi: navbatga tushishning o'zi jonni
    yemaydi, aks holda raqib topilmasa o'quvchi bekorga jon yo'qotardi.
    """
    navbat.refresh_from_db()
    if navbat.holat == DuelQueue.TOPILDI and navbat.duel_id:
        return navbat.duel, ""

    navbat.holat = DuelQueue.BEKOR
    navbat.save(update_fields=["holat"])

    return duel_boshla(navbat.user, navbat.center, mode=navbat.mode)


def navbatni_bekor_qil(navbat: DuelQueue) -> None:
    if navbat.holat == DuelQueue.KUTMOQDA:
        navbat.holat = DuelQueue.BEKOR
        navbat.save(update_fields=["holat"])
