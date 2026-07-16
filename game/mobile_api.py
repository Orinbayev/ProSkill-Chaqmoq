"""Chaqmoq Game — mobil ilova uchun API.

Kirish ikki yo'l bilan:
  1. ChaqmoqApp hisobi bilan (o'quv markazi o'quvchisi) — mavjud login endpointi,
  2. O'yinda o'zi ro'yxatdan o'tish (`/register/`) — markazsiz o'yinchi.

Ikkala holatda ham chaqmoq 0 dan boshlanadi.

Autentifikatsiya ChaqmoqApp bilan bir xil: `Authorization: Bearer <token>`.
"""

from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.mobile_api import _create_mobile_access_token, mobile_login_required

from .models import (
    SAVOLLAR_SONI,
    Duel,
    DuelInvite,
    Friendship,
    GameProfile,
    NewsPost,
    Purchase,
    ShopItem,
    Tarif,
)
from .services import duel_boshla, duel_yakunla, javob_yoz, profil_ol

User = get_user_model()


def _center(request):
    return getattr(request, "center", None) or getattr(request.user, "center", None)


def _ok(**payload) -> JsonResponse:
    return JsonResponse({"ok": True, **payload})


def _error(message: str, *, status: int = 400, code: str = "", **extra) -> JsonResponse:
    payload = {"ok": False, "error": message}
    if code:
        payload["code"] = code
    payload.update(extra)
    return JsonResponse(payload, status=status)


def _body(request) -> dict:
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


# ═══════════════════════════════════════════════════════════════
# SERIALIZATSIYA
# ═══════════════════════════════════════════════════════════════

def _avatar_url(profile: GameProfile, request) -> str | None:
    if profile.avatar:
        return request.build_absolute_uri(profile.avatar.url)
    return None


def _profil_dict(profile: GameProfile, request) -> dict:
    obuna = profile.obuna
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "ism": profile.nomi,
        "avatar": _avatar_url(profile, request),
        "xp": profile.xp,
        "hafta_xp": profile.hafta_xp,
        "chaqmoq": float(profile.chaqmoq),
        "jon": profile.joriy_jon,
        "max_jon": profile.max_jon,
        "keyingi_jon_soniya": profile.keyingi_jon_soniya(),
        "streak_kun": profile.streak_kun,
        "liga": profile.liga,
        "pro": profile.pro,
        "tarif": obuna.tarif.nom if obuna else None,
        "tarif_tugaydi": obuna.tugaydi.isoformat() if obuna else None,
    }


def _yangilik_dict(post: NewsPost, request) -> dict:
    return {
        "id": post.id,
        "sarlavha": post.sarlavha,
        "matn": post.matn,
        "tur": post.tur,
        "muhim": post.muhim,
        "rasm": request.build_absolute_uri(post.rasm.url) if post.rasm else None,
        "sana": post.chop_etilgan.isoformat(),
    }


def _mahsulot_dict(item: ShopItem, request) -> dict:
    return {
        "id": item.id,
        "nom": item.nom,
        "izoh": item.izoh,
        "tur": item.tur,
        "rasm": request.build_absolute_uri(item.rasm.url) if item.rasm else None,
        "narx_chaqmoq": float(item.narx_chaqmoq),
        "beradigan_jon": item.beradigan_jon,
        "zaxira": item.zaxira,
        "mavjud": item.mavjud,
    }


def _reyting(profile: GameProfile) -> int:
    """O'yinchining markazidagi o'rni (haftalik XP bo'yicha). Robotlar ham sanaladi."""
    return (
        GameProfile.objects
        .filter(center=profile.center, hafta_xp__gt=profile.hafta_xp)
        .count()
        + 1
    )


# ═══════════════════════════════════════════════════════════════
# RO'YXATDAN O'TISH
# ═══════════════════════════════════════════════════════════════

@csrf_exempt
@require_POST
def game_register(request):
    """O'yinda mustaqil ro'yxatdan o'tish — faqat login va parol, markazsiz.

    ChaqmoqApp o'quvchilari bu endpointdan foydalanmaydi — ular mavjud
    `/api/mobile/auth/login/` orqali o'z hisobi bilan kiradi.

    `login` email bo'lishi shart emas: agar `@` bo'lmasa, ichki maqsadda
    sun'iy email (`<login>@chaqmoq.game`) yasab qo'yamiz. Foydalanuvchi uchun
    bu shunchaki login/parol bo'lib qoladi.
    """
    data = _body(request)

    ism = str(data.get("ism") or "").strip()
    login = str(data.get("login") or data.get("email") or "").strip()
    parol = str(data.get("parol") or "")

    if not login or not parol:
        return _error("Login va parol to'ldirilishi shart.", code="toliq_emas")
    if len(parol) < 6:
        return _error("Parol kamida 6 belgidan iborat bo'lsin.", code="parol_qisqa")

    email = login.lower() if "@" in login else f"{login.lower()}@chaqmoq.game"

    if User.objects.filter(email__iexact=email).exists():
        return _error("Bu login allaqachon band.", code="login_band", status=409)

    with transaction.atomic():
        user = User.objects.create_user(
            email=email,
            password=parol,
            # Ism berilmasa — login'ni ism sifatida ishlatamiz.
            ism=ism or login,
            familya="",
            role="student",
        )
        # Chaqmoq 0 dan boshlanadi — bu ataylab, ChaqmoqApp balansidan alohida.
        GameProfile.objects.create(user=user, center=None)

    raw_token, _token = _create_mobile_access_token(request, user, None, data)
    return _ok(access_token=raw_token, ism=user.ism)


# ═══════════════════════════════════════════════════════════════
# BOSH EKRAN
# ═══════════════════════════════════════════════════════════════

@require_GET
@mobile_login_required
def game_home(request):
    center = _center(request)
    profile = profil_ol(request.user, center)
    profile.save()

    muhim = (
        NewsPost.objects
        .filter(faol=True, muhim=True)
        .filter(Q(center__isnull=True) | Q(center=center))
        .first()
    )

    kutayotgan_chaqiriq = DuelInvite.objects.filter(
        kimga=request.user, holat=DuelInvite.KUTILMOQDA
    ).count()
    kutayotgan_dostlik = Friendship.objects.filter(
        kimga=request.user, holat=Friendship.KUTILMOQDA
    ).count()

    return _ok(
        profil=_profil_dict(profile, request),
        orin=_reyting(profile),
        muhim_yangilik=_yangilik_dict(muhim, request) if muhim else None,
        kutayotgan_chaqiriq=kutayotgan_chaqiriq,
        kutayotgan_dostlik=kutayotgan_dostlik,
    )


# ═══════════════════════════════════════════════════════════════
# DUEL
# ═══════════════════════════════════════════════════════════════

@csrf_exempt
@require_POST
@mobile_login_required
def game_duel_start(request):
    center = _center(request)

    # `raqib_id` berilsa — tarixdagi o'sha robot bilan revansh.
    raqib_id = _body(request).get("raqib_id")
    duel, xato = duel_boshla(
        request.user,
        center,
        raqib_id=int(raqib_id) if isinstance(raqib_id, int) else None,
    )

    if xato == "raqib_topilmadi":
        return _error("Bu raqib bilan qayta oʻynab boʻlmaydi.", status=404, code="raqib_topilmadi")

    if xato == "jon_yoq":
        profile = profil_ol(request.user, center)
        return _error(
            "Bugungi jonlaringiz tugadi.",
            status=409,
            code="jon_yoq",
            keyingi_jon_soniya=profile.keyingi_jon_soniya(),
        )

    if xato == "savol_yetarli_emas":
        return _error(
            f"Savollar yetarli emas (kamida {SAVOLLAR_SONI} ta kerak). "
            "Admin paneldan savol qo'shing.",
            status=409,
            code="savol_yetarli_emas",
        )

    if xato == "raqib_yoq":
        return _error(
            "Raqib topilmadi. Admin paneldan robot qo'shing.",
            status=409,
            code="raqib_yoq",
        )

    savollar = [
        {
            "tartib": dq.tartib,
            "tur": dq.savol.tur,
            "savol": dq.savol.savol,
            "variantlar": dq.variantlar,
            "audio": request.build_absolute_uri(dq.savol.audio.url) if dq.savol.audio else None,
            "rasm": request.build_absolute_uri(dq.savol.rasm.url) if dq.savol.rasm else None,
        }
        for dq in duel.savollar.select_related("savol").all()
    ]

    profile = profil_ol(request.user, center)
    raqib = duel.raqib

    return _ok(
        duel_id=duel.id,
        raqib_nomi=duel.raqib_nomi,
        raqib_avatar=_avatar_url(raqib, request) if raqib else None,
        savollar=savollar,
        jon=profile.joriy_jon,
    )


@csrf_exempt
@require_POST
@mobile_login_required
def game_duel_answer(request, duel_id: int):
    duel = Duel.objects.filter(id=duel_id, oyinchi=request.user).first()
    if duel is None:
        return _error("Duel topilmadi.", status=404)
    if duel.holat == Duel.HOLAT_TUGAGAN:
        return _error("Duel allaqachon tugagan.", status=409)

    data = _body(request)
    tartib = data.get("tartib")
    if not isinstance(tartib, int):
        return _error("«tartib» butun son bo'lishi kerak.")

    dq = javob_yoz(
        duel,
        tartib,
        str(data.get("tanlangan") or ""),
        int(data.get("sarflangan_ms") or 0),
    )
    if dq is None:
        return _error("Bu savolga javob berib bo'lingan yoki savol topilmadi.", status=409)

    # Raqibning javoblari duel boshida hisoblab qo'yilgan, lekin ilovaga faqat
    # SHU SAVOLGACHA yig'ilgan balini beramiz. Aks holda birinchi javobdanoq
    # raqibning yakuniy hisobi ochilib qoladi va poyga hissi yo'qoladi.
    raqib_jami = (
        duel.savollar
        .filter(tartib__lte=tartib)
        .aggregate(jami=Sum("raqib_ball"))["jami"]
        or 0
    )

    return _ok(
        togri=dq.togri,
        togri_javob=dq.savol.togri_javob,
        izoh=dq.savol.izoh,
        olingan_ball=dq.olingan_ball,
        raqib_togri=dq.raqib_togri,
        raqib_ball=dq.raqib_ball,
        ball=duel.ball,
        raqib_jami=raqib_jami,
    )


@csrf_exempt
@require_POST
@mobile_login_required
def game_duel_finish(request, duel_id: int):
    duel = Duel.objects.filter(id=duel_id, oyinchi=request.user).first()
    if duel is None:
        return _error("Duel topilmadi.", status=404)
    return _ok(**duel_yakunla(duel))


@require_GET
@mobile_login_required
def game_duel_history(request):
    """Duel tarixi — kim bilan o'ynagani va natijasi.

    Odam raqib bo'lsa, u bilan do'stlik holati ham qaytariladi — ilova
    "Doʻst qoʻshish" tugmasini shunga qarab ko'rsatadi.
    """
    duellar = (
        Duel.objects
        .filter(oyinchi=request.user, holat=Duel.HOLAT_TUGAGAN)
        .select_related("raqib", "raqib__user")[:50]
    )

    # Barcha raqiblar (robot ham, odam ham) bilan do'stlik holatini olamiz —
    # robotning ham endi hisobi bor, unga ham do'stlik yuborsa bo'ladi.
    raqib_idlari = {d.raqib.user_id for d in duellar if d.raqib and d.raqib.user_id}
    dostliklar: dict[int, str] = {}
    if raqib_idlari:
        for f in Friendship.objects.filter(
            Q(kimdan=request.user, kimga_id__in=raqib_idlari)
            | Q(kimdan_id__in=raqib_idlari, kimga=request.user)
        ):
            boshqa = f.kimga_id if f.kimdan_id == request.user.id else f.kimdan_id
            dostliklar[boshqa] = f.holat

    return _ok(
        duellar=[
            {
                "id": d.id,
                "raqib_nomi": d.raqib_nomi,
                # `raqib_id` — GameProfile id (revansh uchun).
                # `raqib_user_id` — odam bo'lsa User id (do'stlik/chaqiriq uchun).
                "raqib_id": d.raqib_id,
                "raqib_user_id": d.raqib.user_id if d.raqib else None,
                "raqib_robot": d.raqib.robot if d.raqib else True,
                "raqib_avatar": _avatar_url(d.raqib, request) if d.raqib else None,
                "dostlik_holati": (
                    dostliklar.get(d.raqib.user_id) if d.raqib else None
                ),
                "natija": d.natija,
                "ball": d.ball,
                "raqib_ball": d.raqib_ball,
                "togri_javoblar": d.togri_javoblar,
                "savollar_soni": SAVOLLAR_SONI,
                "olingan_chaqmoq": float(d.olingan_chaqmoq),
                "sana": d.tugagan.isoformat() if d.tugagan else None,
            }
            for d in duellar
        ]
    )


# ═══════════════════════════════════════════════════════════════
# LIGA — robotlar ham qatnashadi
# ═══════════════════════════════════════════════════════════════

@require_GET
@mobile_login_required
def game_league(request):
    center = _center(request)
    profile = profil_ol(request.user, center)
    profile.save()

    doira = request.GET.get("doira", "markaz")  # markaz | umumiy
    qs = GameProfile.objects.select_related("user")
    if doira == "markaz":
        qs = qs.filter(center=center)

    top = qs.order_by("-hafta_xp", "-xp")[:50]

    return _ok(
        doira=doira,
        liga=profile.liga,
        mening_orinim=_reyting(profile),
        qatorlar=[
            {
                "orin": i,
                "user_id": p.user_id,
                "ism": p.nomi,
                "avatar": _avatar_url(p, request),
                "hafta_xp": p.hafta_xp,
                "chaqmoq": float(p.chaqmoq),
                "liga": p.liga,
                "robot": p.robot,
                "men": p.user_id is not None and p.user_id == request.user.id,
            }
            for i, p in enumerate(top, start=1)
        ],
    )


# ═══════════════════════════════════════════════════════════════
# YANGILIKLAR
# ═══════════════════════════════════════════════════════════════

@require_GET
@mobile_login_required
def game_news(request):
    center = _center(request)
    posts = (
        NewsPost.objects
        .filter(faol=True)
        .filter(Q(center__isnull=True) | Q(center=center))[:50]
    )
    return _ok(yangiliklar=[_yangilik_dict(p, request) for p in posts])


# ═══════════════════════════════════════════════════════════════
# DO'KON
# ═══════════════════════════════════════════════════════════════

@require_GET
@mobile_login_required
def game_shop(request):
    center = _center(request)
    profile = profil_ol(request.user, center)

    items = (
        ShopItem.objects
        .filter(faol=True)
        .filter(Q(center__isnull=True) | Q(center=center))
    )
    return _ok(
        chaqmoq=float(profile.chaqmoq),
        mahsulotlar=[_mahsulot_dict(i, request) for i in items],
    )


@csrf_exempt
@require_POST
@mobile_login_required
def game_shop_buy(request, item_id: int):
    center = _center(request)

    with transaction.atomic():
        # Bir vaqtda ikki marta bosilsa, chaqmoq ikki marta yechilmasin.
        profile = (
            GameProfile.objects
            .select_for_update()
            .filter(user=request.user)
            .first()
        )
        if profile is None:
            profile = profil_ol(request.user, center)

        item = (
            ShopItem.objects
            .select_for_update()
            .filter(id=item_id, faol=True)
            .first()
        )
        if item is None:
            return _error("Mahsulot topilmadi.", status=404)
        if not item.mavjud:
            return _error("Mahsulot tugagan.", status=409, code="tugagan")

        if profile.chaqmoq < item.narx_chaqmoq:
            return _error(
                "Chaqmoq yetarli emas.",
                status=409,
                code="chaqmoq_yetmaydi",
                kerak=float(item.narx_chaqmoq),
                bor=float(profile.chaqmoq),
            )

        profile.chaqmoq -= item.narx_chaqmoq

        # Jon to'plami bo'lsa — darhol jon qo'shiladi.
        if item.beradigan_jon:
            profile.jon = min(profile.max_jon, profile.joriy_jon + item.beradigan_jon)

        profile.save()

        if item.zaxira > 0:
            item.zaxira -= 1
            item.save(update_fields=["zaxira"])

        Purchase.objects.create(
            user=request.user,
            item=item,
            narx_chaqmoq=item.narx_chaqmoq,
        )

    return _ok(
        chaqmoq=float(profile.chaqmoq),
        jon=profile.joriy_jon,
        xabar=f"«{item.nom}» sotib olindi.",
    )


@require_GET
@mobile_login_required
def game_purchases(request):
    xaridlar = Purchase.objects.filter(user=request.user).select_related("item")[:50]
    return _ok(
        xaridlar=[
            {
                "id": p.id,
                "nom": p.item.nom,
                "tur": p.item.tur,
                "narx_chaqmoq": float(p.narx_chaqmoq),
                "topshirildi": p.topshirildi,
                "sana": p.sana.isoformat(),
            }
            for p in xaridlar
        ]
    )


# ═══════════════════════════════════════════════════════════════
# TARIFLAR
# ═══════════════════════════════════════════════════════════════

@require_GET
@mobile_login_required
def game_tariffs(request):
    center = _center(request)
    profile = profil_ol(request.user, center)
    obuna = profile.obuna

    return _ok(
        joriy_tarif=obuna.tarif.nom if obuna else None,
        tugaydi=obuna.tugaydi.isoformat() if obuna else None,
        bepul_jon=profile.max_jon if obuna is None else None,
        tariflar=[
            {
                "id": t.id,
                "nom": t.nom,
                "narx_som": t.narx_som,
                "kun": t.kun,
                "jon_soni": t.jon_soni,
                "soat": t.soat,
                "tavsif": t.tavsif,
                "izoh": t.izoh,
            }
            for t in Tarif.objects.filter(faol=True)
        ],
    )


# ═══════════════════════════════════════════════════════════════
# PROFIL
# ═══════════════════════════════════════════════════════════════

def _statistika(user) -> dict:
    duellar = Duel.objects.filter(oyinchi=user, holat=Duel.HOLAT_TUGAGAN)
    jami = duellar.count()
    galabalar = duellar.filter(natija=Duel.NATIJA_GALABA).count()

    javoblar = 0
    togri = 0
    for d in duellar.prefetch_related("savollar"):
        for dq in d.savollar.all():
            if dq.togri is not None:
                javoblar += 1
                togri += int(dq.togri)

    return {
        "duellar": jami,
        "galabalar": galabalar,
        "aniqlik": round(togri / javoblar * 100) if javoblar else 0,
        "javoblar": javoblar,
    }


@require_GET
@mobile_login_required
def game_profile(request):
    center = _center(request)
    profile = profil_ol(request.user, center)
    profile.save()

    return _ok(
        profil=_profil_dict(profile, request),
        orin=_reyting(profile),
        statistika=_statistika(request.user),
    )


@require_GET
@mobile_login_required
def game_user_profile(request, user_id: int):
    """Boshqa o'quvchining profili."""
    profile = GameProfile.objects.filter(user_id=user_id).select_related("user").first()
    if profile is None:
        return _error("O'yinchi topilmadi.", status=404)

    dostlik = Friendship.objects.filter(
        Q(kimdan=request.user, kimga_id=user_id) | Q(kimdan_id=user_id, kimga=request.user)
    ).first()

    return _ok(
        profil=_profil_dict(profile, request),
        orin=_reyting(profile),
        statistika=_statistika(profile.user),
        dostlik_holati=dostlik.holat if dostlik else None,
        dostlik_men_yubordim=bool(dostlik and dostlik.kimdan_id == request.user.id),
    )


@csrf_exempt
@require_POST
@mobile_login_required
def game_avatar(request):
    """Profil rasmini yuklash (multipart/form-data)."""
    fayl = request.FILES.get("avatar")
    if fayl is None:
        return _error("Rasm yuborilmadi.", code="rasm_yoq")

    profile = profil_ol(request.user, _center(request))
    profile.avatar = fayl
    profile.save(update_fields=["avatar"])

    return _ok(avatar=_avatar_url(profile, request))


# ═══════════════════════════════════════════════════════════════
# DO'STLAR
# ═══════════════════════════════════════════════════════════════

@require_GET
@mobile_login_required
def game_friends(request):
    """Do'stlar + kelgan so'rovlar."""
    qabul = Friendship.objects.filter(
        Q(kimdan=request.user) | Q(kimga=request.user),
        holat=Friendship.QABUL,
    ).select_related("kimdan", "kimga")

    dostlar = []
    for f in qabul:
        dost = f.kimga if f.kimdan_id == request.user.id else f.kimdan
        profile = GameProfile.objects.filter(user=dost).first()
        dostlar.append({
            "user_id": dost.id,
            "ism": profile.nomi if profile else (dost.ism or dost.email),
            "avatar": _avatar_url(profile, request) if profile else None,
            "hafta_xp": profile.hafta_xp if profile else 0,
            "liga": profile.liga if profile else "bronza",
        })

    sorovlar = Friendship.objects.filter(
        kimga=request.user, holat=Friendship.KUTILMOQDA
    ).select_related("kimdan")

    return _ok(
        dostlar=dostlar,
        sorovlar=[
            {
                "id": s.id,
                "user_id": s.kimdan_id,
                "ism": s.kimdan.ism or s.kimdan.email,
            }
            for s in sorovlar
        ],
    )


@require_GET
@mobile_login_required
def game_online(request):
    """Hozir onlayn o'yinchilar — do'stlik yoki duelga taklif uchun.

    Onlayn = oxirgi 5 daqiqada faol odamlar + robotlar (doim onlayn).
    O'zi va allaqachon do'st bo'lganlar chetlab o'tiladi.
    """
    chegara = timezone.now() - timezone.timedelta(minutes=GameProfile.ONLAYN_DAQIQA)

    # Do'st bo'lganlarni chetlab o'tamiz — ular allaqachon do'stlar ro'yxatida.
    dost_idlari = set()
    for f in Friendship.objects.filter(
        Q(kimdan=request.user) | Q(kimga=request.user),
        holat=Friendship.QABUL,
    ).values_list("kimdan_id", "kimga_id"):
        dost_idlari.update(f)

    qs = (
        GameProfile.objects
        .filter(user__isnull=False)
        .filter(Q(robot=True) | Q(oxirgi_faol__gt=chegara))
        .exclude(user=request.user)
        .exclude(user_id__in=dost_idlari)
        .select_related("user")
        .order_by("robot", "-oxirgi_faol")[:30]
    )

    # Yuborilgan/kutilayotgan so'rovlar holati.
    holatlar: dict[int, str] = {}
    for f in Friendship.objects.filter(
        Q(kimdan=request.user) | Q(kimga=request.user)
    ):
        boshqa = f.kimga_id if f.kimdan_id == request.user.id else f.kimdan_id
        holatlar[boshqa] = f.holat

    return _ok(
        oyinchilar=[
            {
                "user_id": p.user_id,
                "profil_id": p.id,
                "ism": p.nomi,
                "avatar": _avatar_url(p, request),
                "hafta_xp": p.hafta_xp,
                "liga": p.liga,
                "robot": p.robot,
                "dostlik_holati": holatlar.get(p.user_id),
            }
            for p in qs
        ]
    )


@require_GET
@mobile_login_required
def game_search_users(request):
    """Ism yoki email bo'yicha o'yinchi qidirish."""
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return _ok(natijalar=[])

    profiles = (
        GameProfile.objects
        .filter(robot=False, user__isnull=False)
        .filter(Q(user__ism__icontains=q) | Q(user__email__icontains=q))
        .exclude(user=request.user)
        .select_related("user")[:20]
    )

    return _ok(
        natijalar=[
            {
                "user_id": p.user_id,
                "ism": p.nomi,
                "avatar": _avatar_url(p, request),
                "hafta_xp": p.hafta_xp,
                "liga": p.liga,
            }
            for p in profiles
        ]
    )


@csrf_exempt
@require_POST
@mobile_login_required
def game_friend_request(request, user_id: int):
    if user_id == request.user.id:
        return _error("O'zingizga so'rov yubora olmaysiz.")

    kimga = User.objects.filter(id=user_id).first()
    if kimga is None:
        return _error("Foydalanuvchi topilmadi.", status=404)

    mavjud = Friendship.objects.filter(
        Q(kimdan=request.user, kimga=kimga) | Q(kimdan=kimga, kimga=request.user)
    ).first()
    if mavjud:
        return _error("So'rov allaqachon mavjud.", status=409, holat=mavjud.holat)

    # Robot javob bera olmaydi — shuning uchun so'rov darhol qabul qilinadi.
    robotmi = GameProfile.objects.filter(user=kimga, robot=True).exists()
    holat = Friendship.QABUL if robotmi else Friendship.KUTILMOQDA

    Friendship.objects.create(kimdan=request.user, kimga=kimga, holat=holat)
    return _ok(
        xabar="Do'st qo'shildi." if robotmi else "Do'stlik so'rovi yuborildi.",
        holat=holat,
    )


@csrf_exempt
@require_POST
@mobile_login_required
def game_friend_respond(request, friendship_id: int):
    """So'rovni qabul qilish yoki rad etish. body: {"qabul": true|false}"""
    f = Friendship.objects.filter(
        id=friendship_id, kimga=request.user, holat=Friendship.KUTILMOQDA
    ).first()
    if f is None:
        return _error("So'rov topilmadi.", status=404)

    f.holat = Friendship.QABUL if _body(request).get("qabul") else Friendship.RAD
    f.save(update_fields=["holat"])
    return _ok(holat=f.holat)


# ═══════════════════════════════════════════════════════════════
# DUELGA CHAQIRIQ
# ═══════════════════════════════════════════════════════════════

@csrf_exempt
@require_POST
@mobile_login_required
def game_invite(request, user_id: int):
    kimga = User.objects.filter(id=user_id).first()
    if kimga is None:
        return _error("Foydalanuvchi topilmadi.", status=404)

    DuelInvite.objects.create(kimdan=request.user, kimga=kimga)
    return _ok(xabar="Duelga chaqiriq yuborildi.")


@require_GET
@mobile_login_required
def game_invites(request):
    chaqiriqlar = DuelInvite.objects.filter(
        kimga=request.user, holat=DuelInvite.KUTILMOQDA
    ).select_related("kimdan")

    return _ok(
        chaqiriqlar=[
            {
                "id": c.id,
                "user_id": c.kimdan_id,
                "ism": c.kimdan.ism or c.kimdan.email,
                "sana": c.yaratilgan.isoformat(),
            }
            for c in chaqiriqlar
        ]
    )


@csrf_exempt
@require_POST
@mobile_login_required
def game_invite_respond(request, invite_id: int):
    c = DuelInvite.objects.filter(
        id=invite_id, kimga=request.user, holat=DuelInvite.KUTILMOQDA
    ).first()
    if c is None:
        return _error("Chaqiriq topilmadi.", status=404)

    c.holat = DuelInvite.QABUL if _body(request).get("qabul") else DuelInvite.RAD
    c.save(update_fields=["holat"])
    return _ok(holat=c.holat)
