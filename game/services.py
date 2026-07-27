"""Chaqmoq Game — duel mantiqi.

Raqib — **robot**. Har robotning o'z mahorati bor (`maxorat`, 0.5–0.9), ya'ni
10 ta savoldan o'rtacha shuncha ulushiga to'g'ri javob beradi. Javob vaqti ham
tasodifiy — shuning uchun robot jonli odamdek tuyuladi va har duel har xil
kechadi. Serverda WebSocket ham, matchmaking navbati ham kerak emas.
"""

from __future__ import annotations

import random
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from .cooldowns import qulflangan_soniya, qulfni_yangila
from .models import (
    SAVOLLAR_SONI,
    Duel,
    DuelQuestion,
    GameProfile,
    Question,
    chaqmoq_aniqlik_boyicha,
    mukofotni_olchash,
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

# ─── Real duel (PvP) ───────────────────────────────────────────

# Raqib qidirish davomiyligi. Shu vaqt ichida odam topilmasa — robot.
NAVBAT_KUTISH_SONIYA = 15

# Navbatdagi yozuv shuncha soniyadan keyin eskirgan hisoblanadi (ilova yopilgan).
NAVBAT_ESKIRISH_SONIYA = 25

# Raqib duelni tashlab ketsa, shuncha daqiqadan keyin bor hisob bo'yicha yopiladi.
PVP_KUTISH_DAQIQA = 6


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


def duel_boshla(
    user,
    center,
    raqib_id: int | None = None,
    mode=None,
) -> tuple[Duel | None, str]:
    """Yangi duel yaratadi. Xatolik bo'lsa (None, sabab) qaytaradi.

    `raqib_id` berilsa — o'sha robot bilan revansh (duel tarixidan "Qayta o'ynash").
    Berilmasa — tasodifiy robot tanlanadi.

    `mode` — katalogdagi duel o'yini (GameMode). Berilsa savollar shu o'yin
    to'plamlaridan olinadi va uzunligi/jon narxi ham o'shandan. Berilmasa eski
    standart qoida ishlaydi (10 savol, 1 jon) — bu eski ilova versiyalari uchun.
    """
    profile = profil_ol(user, center)

    if mode is not None and mode.faqat_pro and not profile.pro:
        return None, "pro_kerak"

    if mode is not None and qulflangan_soniya(profile, mode) > 0:
        return None, "oyin_qulflangan"

    jon_narxi = mode.jon_narxi if mode is not None else 1
    if jon_narxi > 0 and profile.joriy_jon < jon_narxi:
        profile.save(update_fields=["jon", "jon_yangilangan", "jon_kuni"])
        return None, "jon_yoq"

    kerakli = max(1, mode.savollar_soni) if mode is not None else SAVOLLAR_SONI
    if mode is not None:
        savollar = list(mode.savollar_qs().order_by("?")[:kerakli])
    else:
        savollar = _savollar_tanla(center, kerakli)

    if len(savollar) < kerakli:
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

    for _ in range(jon_narxi):
        if not profile.jon_sarfla():
            return None, "jon_yoq"

    if mode is not None:
        qulfni_yangila(profile, mode)

    duel = Duel.objects.create(
        oyinchi=user,
        center=center,
        mode=mode,
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


def raqib_jami(duel: Duel, tartib: int) -> int:
    """Raqibning **shu savolgacha** yig'gan bali.

    Robot bilan: javoblari duel boshida hisoblab qo'yilgan, lekin ilovaga
    bosqichma-bosqich ochiladi — aks holda birinchi javobdanoq yakuniy hisob
    ko'rinib qolardi.

    Odam bilan (PvP): juft dueldan **jonli** o'qiladi — raqib qaysi savolgacha
    yetgan bo'lsa, o'shancha.
    """
    if duel.pvp and duel.juft_id:
        manba = Duel.objects.get(pk=duel.juft_id).savollar
        maydon = "olingan_ball"
    else:
        manba = duel.savollar
        maydon = "raqib_ball"

    return manba.filter(tartib__lte=tartib).aggregate(jami=Sum(maydon))["jami"] or 0


def raqib_yakuniy_ball(duel: Duel) -> int:
    """Raqibning hozirgi yakuniy bali."""
    if duel.pvp and duel.juft_id:
        return Duel.objects.get(pk=duel.juft_id).ball
    return duel.raqib_ball


def duel_yakunla(duel: Duel) -> dict:
    """Duelni yakunlaydi.

    Chaqmoq **aniqlik** uchun beriladi va raqibga bog'liq emas — shuning uchun
    darhol yoziladi. G'alaba/mag'lubiyat (va XP) esa raqibning hisobiga bog'liq:
    robot bilan darhol ma'lum, odam bilan esa ikkalasi tugagach hisoblanadi.
    """
    profile = profil_ol(duel.oyinchi, duel.center)

    if duel.holat == Duel.HOLAT_TUGAGAN:
        _pvp_natijani_tekshir(duel)
        duel.refresh_from_db()
        return _natija_dict(duel, profile)

    chaqmoq = _duel_chaqmoq(duel, duel.togri_javoblar)
    haqiqiy_chaqmoq = profile.chaqmoq_qosh(chaqmoq) if chaqmoq else Decimal("0.0")

    duel.olingan_chaqmoq = haqiqiy_chaqmoq
    duel.holat = Duel.HOLAT_TUGAGAN
    duel.tugagan = timezone.now()
    duel.save(update_fields=["olingan_chaqmoq", "holat", "tugagan"])

    profile.streak_yangila()
    profile.liga_yangila()
    profile.save()

    if duel.pvp:
        _pvp_natijani_tekshir(duel)
    else:
        _natijani_belgila(duel, duel.raqib_ball)
        # Robot ham reytingda yashaydi — u ham XP va chaqmoq yig'adi.
        _robot_hisobini_yurit(duel)

    duel.refresh_from_db()
    return _natija_dict(duel, profile)


def _natijani_belgila(duel: Duel, raqib_ball: int) -> None:
    """G'alaba/mag'lubiyat/durrangni yozadi va XP beradi."""
    if duel.natija:
        return

    galaba_xp = duel.mode.xp_mukofot if duel.mode else XP_GALABA
    if duel.ball > raqib_ball:
        duel.natija = Duel.NATIJA_GALABA
        xp = galaba_xp
    elif duel.ball < raqib_ball:
        duel.natija = Duel.NATIJA_MAGLUBIYAT
        xp = round(galaba_xp * XP_MAGLUBIYAT / XP_GALABA)
    else:
        duel.natija = Duel.NATIJA_DURRANG
        xp = round(galaba_xp * XP_DURRANG / XP_GALABA)

    duel.olingan_xp = xp
    duel.raqib_ball = raqib_ball
    duel.save(update_fields=["natija", "olingan_xp", "raqib_ball"])

    profile = profil_ol(duel.oyinchi, duel.center)
    profile.xp += xp
    profile.hafta_xp += xp
    profile.liga_yangila()
    profile.save(update_fields=["xp", "hafta_xp", "liga"])


def _pvp_natijani_tekshir(duel: Duel) -> None:
    """Ikkala o'yinchi tugagan bo'lsa — ikkalasiga natija yozadi.

    Bittasi tashlab ketgan bo'lsa, `PVP_KUTISH_DAQIQA` dan keyin bor hisob
    bo'yicha yakunlanadi — aks holda duel abadiy ochiq qolardi.
    """
    juft = Duel.objects.filter(pk=duel.juft_id).first() if duel.juft_id else None
    if juft is None:
        # Juft yo'qolgan (o'chirilgan) — bor hisob bo'yicha yopamiz.
        _natijani_belgila(duel, 0)
        return

    ikkalasi_tugagan = (
        duel.holat == Duel.HOLAT_TUGAGAN and juft.holat == Duel.HOLAT_TUGAGAN
    )
    muddat_otdi = duel.boshlangan < timezone.now() - timezone.timedelta(
        minutes=PVP_KUTISH_DAQIQA
    )

    if not (ikkalasi_tugagan or muddat_otdi):
        return

    _natijani_belgila(duel, juft.ball)
    if juft.holat == Duel.HOLAT_TUGAGAN or muddat_otdi:
        _natijani_belgila(juft, duel.ball)


def pvp_kutayotganlarni_yakunla(user) -> None:
    """Raqibi tugatgan (yoki tashlab ketgan) duellarni yopadi.

    Katalog so'ralganda chaqiriladi — alohida cron kerak emas.
    """
    kutayotganlar = Duel.objects.filter(
        oyinchi=user,
        pvp=True,
        natija="",
        holat=Duel.HOLAT_TUGAGAN,
    ).select_related("juft")[:20]
    for duel in kutayotganlar:
        _pvp_natijani_tekshir(duel)


def _duel_chaqmoq(duel: Duel, togri: int) -> Decimal:
    """Duel uzunligi katalogdan o'zgarishi mumkin — shuning uchun chaqmoq
    aniqlik foizidan hisoblanadi. 10 savolli duelda natija eski qoida bilan
    aynan bir xil chiqadi."""
    jami = duel.savollar.count() or SAVOLLAR_SONI
    baza = chaqmoq_aniqlik_boyicha(togri / jami)
    koef = duel.mode.chaqmoq_koef if duel.mode else Decimal("1.0")
    return mukofotni_olchash(baza, koef)


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
    robot.chaqmoq_qosh(_duel_chaqmoq(duel, robot_togri))
    robot.liga_yangila()
    robot.save(update_fields=["xp", "hafta_xp", "chaqmoq", "liga"])


def _natija_dict(duel: Duel, profile: GameProfile) -> dict:
    return {
        "duel_id": duel.id,
        "natija": duel.natija,
        "ball": duel.ball,
        "raqib_ball": duel.raqib_ball,
        "raqib_nomi": duel.raqib_nomi,
        "pvp": duel.pvp,
        # PvP'da raqib hali o'ynayotgan bo'lsa natija keyinroq ma'lum bo'ladi.
        "kutilmoqda": duel.pvp and not duel.natija,
        "togri_javoblar": duel.togri_javoblar,
        "savollar_soni": duel.savollar.count() or SAVOLLAR_SONI,
        "olingan_xp": duel.olingan_xp,
        "olingan_chaqmoq": float(duel.olingan_chaqmoq),
        "jon": profile.joriy_jon,
        "max_jon": profile.max_jon,
        "xp": profile.xp,
        "chaqmoq": float(profile.chaqmoq),
        "streak_kun": profile.streak_kun,
        "liga": profile.liga,
    }
