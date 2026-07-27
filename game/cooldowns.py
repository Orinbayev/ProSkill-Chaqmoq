"""O'yin qulfi (cooldown) mantiqi — bitta joyda.

Ikkita mustaqil to'siq bor:

  1. **Jon** — har `jon_soat` soatda `max_jon` taga tiklanadi (bepulda 8 soat / 3 ta).
     Har o'yin bitta jon yeydi.
  2. **O'yin qulfi** — o'ynalgan o'yin `oyin_qulf_soat` soatga yopiladi
     (bepulda 24 soat).

Ikkinchisi bo'lmasa, o'quvchi eng oson o'yinni takrorlab chaqmoq yig'ar edi.
Shu qulf tufayli 3 ta jon **turli** o'yinlarga sarflanadi.
"""

from __future__ import annotations

from django.utils import timezone

from .models import GameCooldown, GameMode, GameProfile


def qulflar_xaritasi(profile: GameProfile) -> dict[int, int]:
    """{mode_id: qolgan_soniya} — faqat hali ochilmagan o'yinlar.

    Bitta so'rovda o'qiladi: katalogda 20 ta o'yin bo'lsa ham baza bilan
    bir marta gaplashamiz.
    """
    qulf_soat = profile.oyin_qulf_soat
    if qulf_soat <= 0:
        return {}

    chegara = timezone.now() - timezone.timedelta(hours=qulf_soat)
    qatorlar = GameCooldown.objects.filter(
        profile=profile, oxirgi_oynalgan__gt=chegara
    ).values_list("mode_id", "oxirgi_oynalgan")

    natija: dict[int, int] = {}
    hozir = timezone.now()
    for mode_id, oxirgi in qatorlar:
        qolgan = int(
            (oxirgi + timezone.timedelta(hours=qulf_soat) - hozir).total_seconds()
        )
        if qolgan > 0:
            natija[mode_id] = qolgan
    return natija


def qulflangan_soniya(profile: GameProfile, mode: GameMode) -> int:
    """Shu o'yin qancha vaqt qulflangan. 0 = ochiq."""
    qulf_soat = profile.oyin_qulf_soat
    if qulf_soat <= 0:
        return 0

    qulf = GameCooldown.objects.filter(profile=profile, mode=mode).first()
    if qulf is None:
        return 0
    return qulf.qolgan_soniya(qulf_soat)


def qulfni_yangila(profile: GameProfile, mode: GameMode) -> None:
    """O'yin boshlangach qulfni qo'yadi (yoki yangilaydi)."""
    GameCooldown.objects.update_or_create(
        profile=profile,
        mode=mode,
        defaults={"oxirgi_oynalgan": timezone.now()},
    )
