"""SuperAdmin: Chaqmoq Game boshqaruvi.

Bitta sahifada uchta bo'lim:

  • **Do'kon**     — o'yin do'koni mahsulotlari (chaqmoqqa sotiladi),
  • **To'lovlar**  — tarif so'rovlarini tasdiqlash yoki bekor qilish,
  • **O'yinchilar** — jon berish, tarif yoqish, o'yin qulfini ochish.

Django admin ham bor, lekin u kundalik ish uchun noqulay: bu sahifa
superadmin panelining o'z uslubida va tez ishlash uchun qilingan.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from game.cooldowns import qulflar_xaritasi
from game.models import (
    GameCooldown,
    GameProfile,
    Obuna,
    Purchase,
    ShopItem,
    Tarif,
    TarifSorovi,
)
from game.payments import obunani_yoq

User = get_user_model()

superadmin_only = user_passes_test(lambda u: u.is_superuser)


def _json(request) -> dict:
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


def _xato(matn: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": matn}, status=status)


# ═══════════════════════════════════════════════════════════════
# SAHIFA
# ═══════════════════════════════════════════════════════════════

@login_required
@superadmin_only
def superadmin_game(request):
    """Chaqmoq Game boshqaruv sahifasi."""
    mahsulotlar = list(
        ShopItem.objects.all()
        .annotate(xarid_soni=Count("xaridlar"))
        .order_by("tartib", "narx_chaqmoq")
    )

    sorovlar = list(
        TarifSorovi.objects.select_related("user", "tarif", "center")
        .order_by("-yaratilgan")[:100]
    )
    kutayotgan = sum(1 for s in sorovlar if s.holat == TarifSorovi.HOLAT_KUTILMOQDA)

    # Faqat odam o'yinchilar — robotlar bu ro'yxatda kerak emas.
    oyinchilar = list(
        GameProfile.objects.filter(robot=False)
        .select_related("user", "center")
        .order_by("-hafta_xp", "-xp")[:60]
    )

    topshirilmagan = Purchase.objects.filter(topshirildi=False).count()
    jami_chaqmoq = (
        GameProfile.objects.filter(robot=False).aggregate(j=Sum("chaqmoq"))["j"] or 0
    )

    context = {
        "mahsulotlar": mahsulotlar,
        "mahsulot_turlari": ShopItem.TUR_CHOICES,
        "sorovlar": sorovlar,
        "oyinchilar": [
            {
                "id": p.id,
                "ism": p.nomi,
                "email": p.user.email if p.user else "",
                "markaz": p.center.name if p.center else "Markazsiz",
                "chaqmoq": p.chaqmoq,
                "jon": p.jon,
                "max_jon": p.max_jon,
                "xp": p.xp,
                "liga": p.get_liga_display(),
                "tarif": p.obuna.tarif.nom if p.obuna else "",
            }
            for p in oyinchilar
        ],
        "tariflar": list(Tarif.objects.filter(faol=True).order_by("tartib")),
        "totals": {
            "oyinchilar": GameProfile.objects.filter(robot=False).count(),
            "kutayotgan": kutayotgan,
            "mahsulotlar": len(mahsulotlar),
            "topshirilmagan": topshirilmagan,
            "chaqmoq": round(float(jami_chaqmoq)),
        },
    }
    return render(request, "accounts/superadmin_game.html", context)


# ═══════════════════════════════════════════════════════════════
# DO'KON MAHSULOTLARI
# ═══════════════════════════════════════════════════════════════

@login_required
@superadmin_only
def game_shop_save(request, item_id: int = 0):
    """Mahsulot qo'shish yoki tahrirlash. `item_id=0` → yangi."""
    if request.method != "POST":
        return _xato("Method not allowed", 405)

    data = _json(request)
    nom = str(data.get("nom") or "").strip()
    if not nom:
        return _xato("Mahsulot nomini kiriting")

    try:
        narx = Decimal(str(data.get("narx_chaqmoq") or "0"))
    except (InvalidOperation, ValueError):
        return _xato("Narx noto'g'ri")
    if narx <= 0:
        return _xato("Narx 0 dan katta bo'lishi kerak")

    tur = str(data.get("tur") or ShopItem.TUR_ASSESUAR)
    if tur not in dict(ShopItem.TUR_CHOICES):
        tur = ShopItem.TUR_ASSESUAR

    maydonlar = {
        "nom": nom,
        "izoh": str(data.get("izoh") or "").strip()[:200],
        "tur": tur,
        "narx_chaqmoq": narx,
        "beradigan_jon": max(0, int(data.get("beradigan_jon") or 0)),
        "zaxira": int(data.get("zaxira", -1)),
        "faol": bool(data.get("faol", True)),
        "tartib": max(0, int(data.get("tartib") or 0)),
    }

    if item_id:
        item = get_object_or_404(ShopItem, pk=item_id)
        for kalit, qiymat in maydonlar.items():
            setattr(item, kalit, qiymat)
        item.save()
    else:
        item = ShopItem.objects.create(**maydonlar)

    return JsonResponse({"ok": True, "id": item.id, "nom": item.nom})


@login_required
@superadmin_only
def game_shop_delete(request, item_id: int):
    if request.method != "POST":
        return _xato("Method not allowed", 405)

    item = get_object_or_404(ShopItem, pk=item_id)
    # Sotib olingan mahsulotni o'chirib bo'lmaydi (xaridlar tarixi buziladi) —
    # uni faqat yashiramiz.
    if item.xaridlar.exists():
        item.faol = False
        item.save(update_fields=["faol"])
        return JsonResponse(
            {"ok": True, "yashirildi": True,
             "xabar": "Bu mahsulot sotib olingan — o'chirilmadi, faqat yashirildi."}
        )

    item.delete()
    return JsonResponse({"ok": True, "yashirildi": False})


# ═══════════════════════════════════════════════════════════════
# TO'LOVLAR
# ═══════════════════════════════════════════════════════════════

@login_required
@superadmin_only
def game_payment_action(request, sorov_id: int):
    """To'lovni tasdiqlash yoki bekor qilish."""
    if request.method != "POST":
        return _xato("Method not allowed", 405)

    sorov = get_object_or_404(
        TarifSorovi.objects.select_related("tarif", "user"), pk=sorov_id
    )
    amal = str(_json(request).get("amal") or "").strip()

    if sorov.holat != TarifSorovi.HOLAT_KUTILMOQDA:
        return _xato("Bu so'rov allaqachon yakunlangan", 409)

    if amal == "tasdiqlash":
        obuna = obunani_yoq(sorov, izoh=f"SuperAdmin tasdiqladi: {request.user}")
        return JsonResponse({
            "ok": True,
            "holat": sorov.HOLAT_TOLANGAN,
            "tugaydi": timezone.localtime(obuna.tugaydi).strftime("%d.%m.%Y"),
        })

    if amal == "bekor":
        sorov.holat = TarifSorovi.HOLAT_BEKOR
        sorov.izoh = f"SuperAdmin bekor qildi: {request.user}"[:200]
        sorov.save(update_fields=["holat", "izoh"])
        return JsonResponse({"ok": True, "holat": sorov.HOLAT_BEKOR})

    return _xato("Noma'lum amal")


# ═══════════════════════════════════════════════════════════════
# O'YINCHILAR — limitni ko'tarish
# ═══════════════════════════════════════════════════════════════

@login_required
@superadmin_only
def game_player_search(request):
    """Ism yoki email bo'yicha o'yinchi qidirish."""
    so_rov = str(request.GET.get("q") or "").strip()
    qs = GameProfile.objects.filter(robot=False).select_related("user", "center")

    if so_rov:
        qs = qs.filter(
            Q(user__ism__icontains=so_rov)
            | Q(user__familya__icontains=so_rov)
            | Q(user__email__icontains=so_rov)
        )

    natijalar = []
    for p in qs.order_by("-hafta_xp")[:40]:
        natijalar.append({
            "id": p.id,
            "ism": p.nomi,
            "email": p.user.email if p.user else "",
            "markaz": p.center.name if p.center else "Markazsiz",
            "chaqmoq": float(p.chaqmoq),
            "jon": p.joriy_jon,
            "max_jon": p.max_jon,
            "xp": p.xp,
            "liga": p.get_liga_display(),
            "tarif": p.obuna.tarif.nom if p.obuna else "",
            "qulflangan": len(qulflar_xaritasi(p)),
        })
    return JsonResponse({"ok": True, "oyinchilar": natijalar})


@login_required
@superadmin_only
def game_player_grant(request, profile_id: int):
    """O'yinchiga limit ko'tarish: jon, chaqmoq, tarif yoki qulfni ochish."""
    if request.method != "POST":
        return _xato("Method not allowed", 405)

    profile = get_object_or_404(
        GameProfile.objects.select_related("user"), pk=profile_id, robot=False
    )
    if profile.user is None:
        return _xato("Bu o'yinchida hisob yo'q")

    data = _json(request)
    amal = str(data.get("amal") or "").strip()
    xabarlar = []

    if amal == "jon":
        soni = max(1, min(50, int(data.get("soni") or 3)))
        # Berilgan jon `max_jon` chegarasidan oshib ketishi mumkin — bu ataylab:
        # superadmin sovg'a sifatida qo'shimcha jon bera oladi.
        profile.jon = profile.joriy_jon + soni
        profile.save(update_fields=["jon", "jon_yangilangan", "jon_kuni"])
        xabarlar.append(f"{soni} ta jon qo'shildi")

    elif amal == "chaqmoq":
        try:
            miqdor = Decimal(str(data.get("miqdor") or "0"))
        except (InvalidOperation, ValueError):
            return _xato("Miqdor noto'g'ri")
        if miqdor == 0:
            return _xato("Miqdor 0 bo'lmasin")
        haqiqiy = profile.chaqmoq_qosh(miqdor)
        profile.save(update_fields=["chaqmoq"])
        xabarlar.append(f"{haqiqiy} chaqmoq o'zgardi")

    elif amal == "qulf":
        soni = GameCooldown.objects.filter(profile=profile).count()
        GameCooldown.objects.filter(profile=profile).delete()
        xabarlar.append(f"{soni} ta o'yin qulfi ochildi")

    elif amal == "tarif":
        tarif = Tarif.objects.filter(pk=data.get("tarif_id"), faol=True).first()
        if tarif is None:
            return _xato("Tarif topilmadi")

        hozir = timezone.now()
        amaldagi = (
            Obuna.objects.filter(user=profile.user, tolangan=True, tugaydi__gt=hozir)
            .order_by("-tugaydi")
            .first()
        )
        boshlanish = amaldagi.tugaydi if amaldagi else hozir
        Obuna.objects.create(
            user=profile.user,
            tarif=tarif,
            boshlangan=boshlanish,
            tugaydi=boshlanish + timezone.timedelta(days=tarif.kun),
            tolangan=True,
            izoh=f"SuperAdmin sovg'asi: {request.user}",
        )
        profile.keshni_tozala()
        xabarlar.append(f"«{tarif.nom}» {tarif.kun} kunga yoqildi")

    else:
        return _xato("Noma'lum amal")

    profile.refresh_from_db()
    profile.keshni_tozala()
    return JsonResponse({
        "ok": True,
        "xabar": " · ".join(xabarlar),
        "holat": {
            "chaqmoq": float(profile.chaqmoq),
            "jon": profile.joriy_jon,
            "max_jon": profile.max_jon,
            "tarif": profile.obuna.tarif.nom if profile.obuna else "",
        },
    })
