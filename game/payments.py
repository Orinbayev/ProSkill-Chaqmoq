"""O'yin tariflari uchun to'lov.

Ikki yo'l:

  • **Naqd** — o'quvchi markazga to'laydi, admin panelda tasdiqlaydi.
  • **Click** — onlayn to'lov. Bu yerda **alohida** webhook ishlatiladi
    (`/click/game/prepare/`, `/click/game/complete/`), chunki markaz obunasi
    uchun mavjud `billing/click_views.py` oqimi tirik pul bilan ishlaydi va
    unga tegmaslik xavfsizroq.

Click sozlanmagan bo'lsa (env'da SERVICE_ID/MERCHANT_ID/SECRET yo'q) —
to'lov havolasi qaytarilmaydi va ilova naqd usulini taklif qiladi.
"""

from __future__ import annotations

import hashlib
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Obuna, TarifSorovi

logger = logging.getLogger(__name__)

CLICK_CHECKOUT = "https://my.click.uz/services/pay"

# Click xatolik kodlari (rasmiy hujjatdan).
XATO_YOQ = 0
XATO_IMZO = -1
XATO_SUMMA = -2
XATO_SOROV_TOPILMADI = -5
XATO_ALLAQACHON_TOLANGAN = -4
XATO_BEKOR = -9


def _sozlangan() -> bool:
    return all(
        str(getattr(settings, nom, "") or "").strip()
        for nom in ("CLICK_SERVICE_ID", "CLICK_MERCHANT_ID", "CLICK_SECRET_KEY")
    )


def _merchant_trans_id(sorov: TarifSorovi) -> str:
    """Click uchun so'rov identifikatori.

    `game-` prefiksi markaz obunasi to'lovlaridan ajratib turadi — bir xil
    Click hisobi ikkala oqimga ishlatilsa ham chalkashmaydi.
    """
    return f"game-{sorov.id}"


def sorovni_topish(merchant_trans_id: str) -> TarifSorovi | None:
    matn = str(merchant_trans_id or "").strip()
    if not matn.startswith("game-"):
        return None
    try:
        sorov_id = int(matn.split("-", 1)[1])
    except (IndexError, ValueError):
        return None
    return TarifSorovi.objects.filter(id=sorov_id).select_related("tarif").first()


def tolov_havolasi(request, sorov: TarifSorovi) -> str:
    """Click to'lov sahifasiga havola. Sozlanmagan bo'lsa bo'sh satr."""
    if not _sozlangan():
        return ""

    sorov.transaction_id = _merchant_trans_id(sorov)
    sorov.save(update_fields=["transaction_id"])

    parametrlar = {
        "service_id": str(settings.CLICK_SERVICE_ID).strip(),
        "merchant_id": str(settings.CLICK_MERCHANT_ID).strip(),
        "amount": sorov.narx_som,
        "transaction_param": sorov.transaction_id,
    }
    qaytish = str(getattr(settings, "CLICK_RETURN_URL", "") or "").strip()
    if qaytish:
        parametrlar["return_url"] = qaytish

    return f"{CLICK_CHECKOUT}?{urlencode(parametrlar)}"


# ═══════════════════════════════════════════════════════════════
# OBUNANI YOQISH
# ═══════════════════════════════════════════════════════════════

def obunani_yoq(sorov: TarifSorovi, *, izoh: str = "") -> Obuna:
    """So'rovni to'langan deb belgilaydi va obunani yoqadi.

    Amaldagi obuna bo'lsa — muddati uzaytiriladi (yo'qolib ketmaydi).
    Ikki marta chaqirilsa ikkinchisi hech narsa qilmaydi (idempotent).
    """
    with transaction.atomic():
        sorov = TarifSorovi.objects.select_for_update().get(pk=sorov.pk)
        if sorov.holat == TarifSorovi.HOLAT_TOLANGAN and sorov.obuna_id:
            return sorov.obuna

        hozir = timezone.now()
        amaldagi = (
            Obuna.objects
            .filter(user=sorov.user, tolangan=True, tugaydi__gt=hozir)
            .order_by("-tugaydi")
            .first()
        )
        boshlanish = amaldagi.tugaydi if amaldagi else hozir

        obuna = Obuna.objects.create(
            user=sorov.user,
            tarif=sorov.tarif,
            boshlangan=boshlanish,
            tugaydi=boshlanish + timezone.timedelta(days=sorov.tarif.kun),
            tolangan=True,
            izoh=izoh or f"Tarif so'rovi #{sorov.id} ({sorov.get_usul_display()})",
        )

        sorov.holat = TarifSorovi.HOLAT_TOLANGAN
        sorov.tasdiqlangan = hozir
        sorov.obuna = obuna
        sorov.save(update_fields=["holat", "tasdiqlangan", "obuna"])

    return obuna


# ═══════════════════════════════════════════════════════════════
# CLICK WEBHOOK
# ═══════════════════════════════════════════════════════════════

def _imzo_togrimi(data, *, tayyorlash_id: str = "") -> bool:
    """Click imzosini tekshiradi (MD5, rasmiy hujjat bo'yicha)."""
    secret = str(getattr(settings, "CLICK_SECRET_KEY", "") or "").strip()
    if not secret:
        return False

    qismlar = [
        data.get("click_trans_id", ""),
        data.get("service_id", ""),
        secret,
        data.get("merchant_trans_id", ""),
    ]
    if tayyorlash_id:
        qismlar.append(tayyorlash_id)
    qismlar += [
        data.get("amount", ""),
        data.get("action", ""),
        data.get("sign_time", ""),
    ]

    kutilgan = hashlib.md5("".join(str(q) for q in qismlar).encode()).hexdigest()
    return kutilgan == str(data.get("sign_string", "")).strip()


def _javob(data, xato: int, izoh: str, **qoshimcha) -> JsonResponse:
    return JsonResponse(
        {
            "click_trans_id": data.get("click_trans_id", ""),
            "merchant_trans_id": data.get("merchant_trans_id", ""),
            "error": xato,
            "error_note": izoh,
            **qoshimcha,
        }
    )


def _summani_tekshir(data, sorov: TarifSorovi) -> bool:
    try:
        return abs(float(data.get("amount", 0)) - float(sorov.narx_som)) < 1
    except (TypeError, ValueError):
        return False


@csrf_exempt
@require_POST
def game_click_prepare(request):
    """Click 1-bosqich: to'lovni tayyorlash."""
    data = request.POST or {}

    sorov = sorovni_topish(data.get("merchant_trans_id", ""))
    if sorov is None:
        return _javob(data, XATO_SOROV_TOPILMADI, "So'rov topilmadi")

    if not _imzo_togrimi(data):
        logger.warning("Game Click: imzo xato, sorov=%s", sorov.id)
        return _javob(data, XATO_IMZO, "Imzo noto'g'ri")

    if not _summani_tekshir(data, sorov):
        return _javob(data, XATO_SUMMA, "Summa mos emas")

    if sorov.holat == TarifSorovi.HOLAT_TOLANGAN:
        return _javob(data, XATO_ALLAQACHON_TOLANGAN, "Allaqachon to'langan")
    if sorov.holat == TarifSorovi.HOLAT_BEKOR:
        return _javob(data, XATO_BEKOR, "So'rov bekor qilingan")

    return _javob(data, XATO_YOQ, "Success", merchant_prepare_id=sorov.id)


@csrf_exempt
@require_POST
def game_click_complete(request):
    """Click 2-bosqich: to'lovni yakunlash va tarifni yoqish."""
    data = request.POST or {}

    sorov = sorovni_topish(data.get("merchant_trans_id", ""))
    if sorov is None:
        return _javob(data, XATO_SOROV_TOPILMADI, "So'rov topilmadi")

    tayyorlash_id = str(data.get("merchant_prepare_id", "")).strip()
    if not _imzo_togrimi(data, tayyorlash_id=tayyorlash_id):
        logger.warning("Game Click: complete imzo xato, sorov=%s", sorov.id)
        return _javob(data, XATO_IMZO, "Imzo noto'g'ri")

    if not _summani_tekshir(data, sorov):
        return _javob(data, XATO_SUMMA, "Summa mos emas")

    # Click xatolik bilan kelgan bo'lsa — bekor qilamiz.
    try:
        click_xato = int(data.get("error", 0))
    except (TypeError, ValueError):
        click_xato = 0
    if click_xato < 0:
        sorov.holat = TarifSorovi.HOLAT_BEKOR
        sorov.izoh = f"Click xatosi: {data.get('error_note', '')}"[:200]
        sorov.save(update_fields=["holat", "izoh"])
        return _javob(data, XATO_BEKOR, "To'lov bekor qilindi")

    if sorov.holat == TarifSorovi.HOLAT_TOLANGAN:
        # Click bir so'rovni takrorlashi mumkin — idempotent javob.
        return _javob(
            data, XATO_YOQ, "Success", merchant_confirm_id=sorov.id
        )

    obunani_yoq(sorov, izoh=f"Click to'lovi ({data.get('click_trans_id', '')})")
    logger.info("Game Click: tarif yoqildi, sorov=%s", sorov.id)

    return _javob(data, XATO_YOQ, "Success", merchant_confirm_id=sorov.id)
