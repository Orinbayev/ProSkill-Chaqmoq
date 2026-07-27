"""Yakka o'yin sessiyalari — duel'dan tashqari barcha motorlar uchun mantiq.

Duel alohida yuritiladi (`services.py`), chunki u robot raqib, revansh va
chaqiriq bilan bog'liq. Qolgan motorlar (viktorina, sprint, xotira, ...) esa
bitta umumiy oqimdan foydalanadi:

    boshla → javob → javob → ... → yakunla

Motor faqat **ilovadagi ko'rinish va vaqt qoidalarini** o'zgartiradi; ball,
XP va chaqmoq har doim shu yerda, serverda hisoblanadi.
"""

from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from .cooldowns import qulflangan_soniya, qulfni_yangila
from .engines import Motor
from .models import (
    GameMode,
    GameSession,
    GameSessionQuestion,
    chaqmoq_aniqlik_boyicha,
    mukofotni_olchash,
)
from .services import profil_ol


# Sessiya ochiq qolib ketsa (ilova yopilgan) — shuncha vaqtdan keyin uni
# "tashlab ketilgan" deb hisoblaymiz va yangisini ochishga to'sqinlik qilmaydi.
ESKIRISH_SOAT = 3


def _savollar_tanla(mode: GameMode, soni: int):
    return list(mode.savollar_qs().order_by("?")[:soni])


def sessiya_boshla(user, center, mode: GameMode) -> tuple[GameSession | None, str]:
    """Yangi sessiya ochadi. Xatolikda (None, sabab) qaytaradi."""
    motor = mode.motor_obyekt
    if motor is None:
        return None, "motor_nomalum"

    profile = profil_ol(user, center)

    if mode.faqat_pro and not profile.pro:
        return None, "pro_kerak"

    if qulflangan_soniya(profile, mode) > 0:
        return None, "oyin_qulflangan"

    if mode.jon_narxi > 0 and profile.joriy_jon < mode.jon_narxi:
        profile.save(update_fields=["jon", "jon_yangilangan", "jon_kuni"])
        return None, "jon_yoq"

    soni = max(1, mode.savollar_soni)
    savollar = _savollar_tanla(mode, soni)
    if len(savollar) < motor.min_savol:
        return None, "savol_yetarli_emas"

    # Jon faqat hamma tekshiruvdan o'tgach yechiladi.
    for _ in range(mode.jon_narxi):
        if not profile.jon_sarfla():
            return None, "jon_yoq"

    # Jon yechilgach o'yin qulflanadi — endi u `oyin_qulf_soat` soat yopiq.
    qulfni_yangila(profile, mode)

    sessiya = GameSession.objects.create(
        user=user,
        center=center,
        mode=mode,
        oyin_nomi=mode.nom,
        motor=mode.motor,
        jami_savol=len(savollar),
    )

    GameSessionQuestion.objects.bulk_create(
        [
            GameSessionQuestion(
                sessiya=sessiya,
                savol=savol,
                tartib=tartib,
                variantlar=savol.variantlar(),
            )
            for tartib, savol in enumerate(savollar, start=1)
        ]
    )
    return sessiya, ""


def javob_yoz(sessiya: GameSession, tartib: int, tanlangan: str, sarflangan_ms: int):
    """Bitta javobni yozadi. Savol topilmasa yoki javob berilgan bo'lsa None."""
    sq = (
        sessiya.savollar.filter(tartib=tartib)
        .select_related("savol")
        .first()
    )
    if sq is None or sq.togri is not None:
        return None

    sq.tanlangan = tanlangan
    sq.togri = tanlangan.strip().casefold() == sq.savol.togri_javob.strip().casefold()
    sq.sarflangan_ms = max(0, int(sarflangan_ms))
    sq.olingan_ball = 1 if sq.togri else 0
    sq.javob_berilgan = timezone.now()
    sq.save(
        update_fields=[
            "tanlangan",
            "togri",
            "sarflangan_ms",
            "olingan_ball",
            "javob_berilgan",
        ]
    )

    javoblar = list(sessiya.savollar.values_list("togri", "olingan_ball"))
    sessiya.togri_javoblar = sum(1 for togri, _ in javoblar if togri is True)
    sessiya.xato_javoblar = sum(1 for togri, _ in javoblar if togri is False)
    sessiya.ball = sum(ball for _, ball in javoblar)
    sessiya.save(update_fields=["togri_javoblar", "xato_javoblar", "ball"])
    return sq


def sessiya_yakunla(sessiya: GameSession) -> dict:
    """Sessiyani yopadi va XP/chaqmoq beradi."""
    profile = profil_ol(sessiya.user, sessiya.center)

    if sessiya.holat == GameSession.HOLAT_TUGAGAN:
        return natija_dict(sessiya, profile)

    mode = sessiya.mode
    aniqlik = sessiya.aniqlik

    xp_max = mode.xp_mukofot if mode else 40
    koef = mode.chaqmoq_koef if mode else Decimal("1.0")

    # Hech bir savolga javob bermay chiqib ketgan bo'lsa — na mukofot, na jarima.
    javob_berilgan = sessiya.togri_javoblar + sessiya.xato_javoblar
    if javob_berilgan == 0:
        xp, chaqmoq = 0, Decimal("0.0")
    else:
        xp = int(round(xp_max * aniqlik))
        chaqmoq = mukofotni_olchash(chaqmoq_aniqlik_boyicha(aniqlik), koef)

    # Balans 0 da bo'lsa jarima yechilmaydi — haqiqiy o'zgarishni yozamiz.
    haqiqiy_chaqmoq = profile.chaqmoq_qosh(chaqmoq) if chaqmoq else Decimal("0.0")

    sessiya.olingan_xp = xp
    sessiya.olingan_chaqmoq = haqiqiy_chaqmoq
    sessiya.holat = GameSession.HOLAT_TUGAGAN
    sessiya.tugagan = timezone.now()
    sessiya.save(
        update_fields=["olingan_xp", "olingan_chaqmoq", "holat", "tugagan"]
    )

    if xp or haqiqiy_chaqmoq:
        profile.xp += xp
        profile.hafta_xp += xp
        profile.streak_yangila()
        profile.liga_yangila()
        profile.save()

    return natija_dict(sessiya, profile)


def natija_dict(sessiya: GameSession, profile) -> dict:
    return {
        "sessiya_id": sessiya.id,
        "oyin_nomi": sessiya.oyin_nomi,
        "motor": sessiya.motor,
        "ball": sessiya.ball,
        "togri_javoblar": sessiya.togri_javoblar,
        "xato_javoblar": sessiya.xato_javoblar,
        "jami_savol": sessiya.jami_savol,
        "aniqlik": round(sessiya.aniqlik * 100),
        "olingan_xp": sessiya.olingan_xp,
        "olingan_chaqmoq": float(sessiya.olingan_chaqmoq),
        "jon": profile.joriy_jon,
        "max_jon": profile.max_jon,
        "xp": profile.xp,
        "chaqmoq": float(profile.chaqmoq),
        "streak_kun": profile.streak_kun,
        "liga": profile.liga,
    }


def savol_dict(sq: GameSessionQuestion, motor: Motor | None, request) -> dict:
    """Sessiya savolini ilovaga yuboriladigan ko'rinishga o'giradi.

    `javob_ochiq` motorlarda (xotira, juftlash) to'g'ri javob ham beriladi —
    u yerda kartaning ikkala tomoni baribir ekranda turadi.
    """
    savol = sq.savol
    natija = {
        "tartib": sq.tartib,
        "tur": savol.tur,
        "savol": savol.savol,
        "variantlar": sq.variantlar,
        "audio": request.build_absolute_uri(savol.audio.url) if savol.audio else None,
        "rasm": request.build_absolute_uri(savol.rasm.url) if savol.rasm else None,
    }
    if motor is not None and motor.javob_ochiq:
        natija["javob"] = savol.togri_javob
    return natija


def eskirgan_sessiyalarni_yop(user) -> None:
    """Ilova yopilib qolgan eski sessiyalarni yakunlaydi.

    Aks holda ular abadiy "davom etmoqda" holatida qolib, tarixni ifloslantiradi.
    """
    chegara = timezone.now() - timezone.timedelta(hours=ESKIRISH_SOAT)
    eskilar = GameSession.objects.filter(
        user=user, holat=GameSession.HOLAT_DAVOM, boshlangan__lt=chegara
    )
    for sessiya in eskilar:
        sessiya_yakunla(sessiya)
