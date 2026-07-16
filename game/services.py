"""Chaqmoq Game — duel mantiqi.

Raqib — **robot**. Har robotning o'z mahorati bor (`maxorat`, 0.5–0.9), ya'ni
10 ta savoldan o'rtacha shuncha ulushiga to'g'ri javob beradi. Javob vaqti ham
tasodifiy — shuning uchun robot jonli odamdek tuyuladi va har duel har xil
kechadi. Serverda WebSocket ham, matchmaking navbati ham kerak emas.
"""

from __future__ import annotations

import random
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from .models import (
    SAVOL_SONIYA,
    SAVOLLAR_SONI,
    Duel,
    DuelQuestion,
    GameProfile,
    Question,
    chaqmoq_mukofoti,
)

# Ball: har to'g'ri javob uchun aniq 1 ball. Duel hisobi = to'g'ri javoblar soni.
BALL = 1

# XP — reyting uchun (chaqmoqdan alohida).
XP_GALABA = 45
XP_MAGLUBIYAT = 10
XP_DURRANG = 25

# Robot javob vaqti (ms) — odamnikiga o'xshash tarqalish.
ROBOT_MIN_MS = 1800
ROBOT_MAX_MS = 9000


def profil_ol(user, center=None) -> GameProfile:
    """O'yinchi profilini oladi, bo'lmasa yaratadi.

    Har chaqiruvda oxirgi faollikni yangilaydi — onlayn holatni aniqlash uchun.
    """
    profile, _ = GameProfile.objects.get_or_create(
        user=user,
        defaults={"center": center or getattr(user, "center", None)},
    )
    profile.oxirgi_faol = timezone.now()
    profile.save(update_fields=["oxirgi_faol"])
    return profile


def ball_hisobla(togri: bool, sarflangan_ms: int = 0) -> int:
    """Har to'g'ri javob = 1 ball. Sarflangan vaqt statistika uchun saqlanadi,
    lekin ballga ta'sir qilmaydi."""
    return BALL if togri else 0


def _savollar_tanla(center, soni: int = SAVOLLAR_SONI) -> list[Question]:
    """Markazga tegishli + umumiy savollardan tasodifiy tanlaydi."""
    qs = Question.objects.filter(faol=True, kategoriya__faol=True).filter(
        Q(center__isnull=True) | Q(center=center)
    )
    return list(qs.order_by("?")[:soni])


def _robot_tanla(center) -> GameProfile | None:
    """Duel uchun robot raqib tanlaydi.

    Avval shu markazdagi robotlar, bo'lmasa umumiy robotlar (center=None).
    """
    qs = GameProfile.objects.filter(robot=True).filter(
        Q(center__isnull=True) | Q(center=center)
    )
    return qs.order_by("?").first()


def _robot_javoblari(robot: GameProfile, soni: int) -> list[tuple[bool, int]]:
    """Robotning butun duel bo'yicha javoblari: [(to'g'rimi, necha ms), ...].

    Nechta to'g'ri javob berishini oldindan mahoratiga qarab belgilaymiz
    (masalan 0.7 → 10 tadan 6–8 tasi), keyin ularni tasodifiy joylarga sochamiz.
    Shunday qilinsa robotning "kuchi" har duelda barqaror, lekin bir xil emas.
    """
    o_rtacha = robot.maxorat * soni
    togri_soni = round(random.gauss(o_rtacha, 1.0))
    togri_soni = max(0, min(soni, togri_soni))

    javoblar = [True] * togri_soni + [False] * (soni - togri_soni)
    random.shuffle(javoblar)

    return [
        (togri, random.randint(ROBOT_MIN_MS, ROBOT_MAX_MS))
        for togri in javoblar
    ]


def duel_boshla(user, center, raqib_id: int | None = None) -> tuple[Duel | None, str]:
    """Yangi duel yaratadi. Xatolik bo'lsa (None, sabab) qaytaradi.

    `raqib_id` berilsa — o'sha robot bilan revansh (duel tarixidan "Qayta o'ynash").
    Berilmasa — tasodifiy robot tanlanadi.
    """
    profile = profil_ol(user, center)

    if profile.joriy_jon <= 0:
        profile.save(update_fields=["jon", "jon_yangilangan", "jon_kuni"])
        return None, "jon_yoq"

    savollar = _savollar_tanla(center)
    if len(savollar) < SAVOLLAR_SONI:
        return None, "savol_yetarli_emas"

    if raqib_id is not None:
        # Revansh — faqat robot bilan. Odam bilan duel chaqiriq orqali bo'ladi.
        robot = GameProfile.objects.filter(id=raqib_id, robot=True).first()
        if robot is None:
            return None, "raqib_topilmadi"
    else:
        robot = _robot_tanla(center)

    if robot is None:
        return None, "raqib_yoq"

    if not profile.jon_sarfla():
        return None, "jon_yoq"

    duel = Duel.objects.create(
        oyinchi=user,
        center=center,
        raqib=robot,
        raqib_nomi=robot.nomi,
    )

    javoblar = _robot_javoblari(robot, len(savollar))

    for tartib, (savol, (raqib_togri, raqib_ms)) in enumerate(
        zip(savollar, javoblar), start=1
    ):
        DuelQuestion.objects.create(
            duel=duel,
            savol=savol,
            tartib=tartib,
            variantlar=savol.variantlar(),
            raqib_togri=raqib_togri,
            raqib_ms=raqib_ms,
            raqib_ball=ball_hisobla(raqib_togri, raqib_ms),
        )

    duel.raqib_ball = sum(dq.raqib_ball for dq in duel.savollar.all())
    duel.save(update_fields=["raqib_ball"])
    return duel, ""


def javob_yoz(duel: Duel, tartib: int, tanlangan: str, sarflangan_ms: int) -> DuelQuestion | None:
    """O'yinchining javobini yozadi va ball beradi."""
    dq = duel.savollar.filter(tartib=tartib).select_related("savol").first()
    if dq is None or dq.togri is not None:
        return None  # Yo'q savol yoki allaqachon javob berilgan.

    dq.tanlangan = tanlangan
    dq.togri = tanlangan.strip().casefold() == dq.savol.togri_javob.strip().casefold()
    dq.sarflangan_ms = max(0, int(sarflangan_ms))
    dq.olingan_ball = ball_hisobla(dq.togri, dq.sarflangan_ms)
    dq.javob_berilgan = timezone.now()
    dq.save()

    savollar = list(duel.savollar.all())
    duel.ball = sum(q.olingan_ball for q in savollar)
    duel.togri_javoblar = sum(1 for q in savollar if q.togri)
    duel.save(update_fields=["ball", "togri_javoblar"])
    return dq


def duel_yakunla(duel: Duel) -> dict:
    """Duelni yakunlaydi: XP, chaqmoq beradi, robotning ham hisobini yuritadi."""
    profile = profil_ol(duel.oyinchi, duel.center)

    if duel.holat == Duel.HOLAT_TUGAGAN:
        return _natija_dict(duel, profile)

    if duel.ball > duel.raqib_ball:
        duel.natija = Duel.NATIJA_GALABA
        xp = XP_GALABA
    elif duel.ball < duel.raqib_ball:
        duel.natija = Duel.NATIJA_MAGLUBIYAT
        xp = XP_MAGLUBIYAT
    else:
        duel.natija = Duel.NATIJA_DURRANG
        xp = XP_DURRANG

    # Chaqmoq — g'alaba emas, ANIQLIK uchun beriladi. Shunda mag'lub bo'lgan
    # o'quvchi ham mehnati uchun mukofot oladi va tashlab ketmaydi.
    chaqmoq = chaqmoq_mukofoti(duel.togri_javoblar)

    duel.olingan_xp = xp
    duel.olingan_chaqmoq = chaqmoq
    duel.holat = Duel.HOLAT_TUGAGAN
    duel.tugagan = timezone.now()
    duel.save(
        update_fields=["natija", "olingan_xp", "olingan_chaqmoq", "holat", "tugagan"]
    )

    profile.xp += xp
    profile.hafta_xp += xp
    profile.chaqmoq = (profile.chaqmoq or Decimal("0.0")) + chaqmoq
    profile.streak_yangila()
    profile.liga_yangila()
    profile.save()

    # Robot ham reytingda yashaydi — u ham XP va chaqmoq yig'adi.
    _robot_hisobini_yurit(duel)

    return _natija_dict(duel, profile)


def _robot_hisobini_yurit(duel: Duel) -> None:
    robot = duel.raqib
    if robot is None or not robot.robot:
        return

    robot_togri = duel.savollar.filter(raqib_togri=True).count()

    if duel.raqib_ball > duel.ball:
        robot_xp = XP_GALABA
    elif duel.raqib_ball < duel.ball:
        robot_xp = XP_MAGLUBIYAT
    else:
        robot_xp = XP_DURRANG

    robot.xp += robot_xp
    robot.hafta_xp += robot_xp
    robot.chaqmoq = (robot.chaqmoq or Decimal("0.0")) + chaqmoq_mukofoti(robot_togri)
    robot.liga_yangila()
    robot.save(update_fields=["xp", "hafta_xp", "chaqmoq", "liga"])


def _natija_dict(duel: Duel, profile: GameProfile) -> dict:
    return {
        "duel_id": duel.id,
        "natija": duel.natija,
        "ball": duel.ball,
        "raqib_ball": duel.raqib_ball,
        "raqib_nomi": duel.raqib_nomi,
        "togri_javoblar": duel.togri_javoblar,
        "savollar_soni": SAVOLLAR_SONI,
        "olingan_xp": duel.olingan_xp,
        "olingan_chaqmoq": float(duel.olingan_chaqmoq),
        "jon": profile.joriy_jon,
        "max_jon": profile.max_jon,
        "xp": profile.xp,
        "chaqmoq": float(profile.chaqmoq),
        "streak_kun": profile.streak_kun,
        "liga": profile.liga,
    }
