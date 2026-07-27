"""Chaqmoq Game — mobil ilova uchun API.

Kirish ikki yo'l bilan:
  1. ChaqmoqApp hisobi bilan (o'quv markazi o'quvchisi) — mavjud login endpointi,
  2. O'yinda o'zi ro'yxatdan o'tish (`/register/`) — markazsiz o'yinchi.

Ikkala holatda ham chaqmoq 0 dan boshlanadi.

Autentifikatsiya ChaqmoqApp bilan bir xil: `Authorization: Bearer <token>`.
"""

from __future__ import annotations

import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.mobile_api import _create_mobile_access_token, mobile_login_required

from .cooldowns import qulflangan_soniya, qulflar_xaritasi
from .engines import MOTORLAR
from .google_auth import (
    GoogleXatosi,
    foydalanuvchini_top_yoki_yarat as google_foydalanuvchi,
    sozlangan as google_sozlangan,
    tokenni_tekshir as google_tokenni_tekshir,
)
from .matchmaking import (
    navbat_holati,
    navbatga_qoy,
    navbatni_bekor_qil,
    robotga_otkaz,
)
from .models import (
    BEPUL_JON,
    BEPUL_JON_SOAT,
    BEPUL_OYIN_QULF_SOAT,
    SAVOLLAR_SONI,
    Duel,
    DuelInvite,
    DuelQueue,
    Feedback,
    Friendship,
    GameMode,
    GameProfile,
    GameSession,
    NewsPost,
    Purchase,
    Question,
    ShopItem,
    Tarif,
    TarifSorovi,
)
from .services import (
    NAVBAT_KUTISH_SONIYA,
    duel_boshla,
    duel_yakunla,
    javob_yoz,
    profil_ol,
    pvp_kutayotganlarni_yakunla,
    raqib_jami,
)
from .session_services import (
    eskirgan_sessiyalarni_yop,
    savol_dict,
    sessiya_boshla,
    sessiya_yakunla,
)
from .session_services import javob_yoz as sessiya_javob_yoz

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
    if profile.center_id is None:
        return _umumiy_orin(profile)
    return (
        GameProfile.objects
        .filter(center=profile.center, hafta_xp__gt=profile.hafta_xp)
        .count()
        + 1
    )


def _umumiy_orin(profile: GameProfile) -> int:
    """Barcha o'yinchilar orasidagi o'rin — markazlardan qat'i nazar."""
    return (
        GameProfile.objects.filter(hafta_xp__gt=profile.hafta_xp).count() + 1
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


def _oyinchi_profil_dict(user) -> dict:
    """Mustaqil o'yinchining profili — markaz paneli maydonlarisiz."""
    return {
        "id": user.id,
        "email": user.email,
        "ism": user.ism or "",
        "familya": user.familya or "",
        "tugilgan_sana": user.birth_date.isoformat() if user.birth_date else None,
        "yosh": _yosh(user.birth_date),
        # Profil to'ldirilganmi — ilova shunga qarab «ma'lumotni to'ldiring»
        # ekranini ko'rsatadi.
        "toliq": bool((user.ism or "").strip() and user.birth_date),
        "game_only": bool(getattr(user, "game_only", False)),
    }


def _yosh(sana) -> int | None:
    if sana is None:
        return None
    bugun = timezone.localdate()
    return (
        bugun.year
        - sana.year
        - ((bugun.month, bugun.day) < (sana.month, sana.day))
    )


@csrf_exempt
@require_POST
def game_google_login(request):
    """Google hisobi orqali kirish / ro'yxatdan o'tish.

    Ilova Google'dan olgan **ID token**ni yuboradi, biz uni serverda
    tekshiramiz va o'z tokenimizni qaytaramiz.
    """
    if not google_sozlangan():
        return _error(
            "Google orqali kirish hozircha sozlanmagan.",
            status=503,
            code="google_sozlanmagan",
        )

    data = _body(request)
    try:
        malumot = google_tokenni_tekshir(str(data.get("id_token") or ""))
    except GoogleXatosi as xato:
        return _error(xato.matn, status=401, code=xato.kod)

    user, yangi = google_foydalanuvchi(malumot)

    if not user.is_active:
        return _error("Bu hisob bloklangan.", status=403, code="hisob_bloklangan")

    # O'yin profili darhol ochiladi — chaqmoq 0 dan boshlanadi.
    GameProfile.objects.get_or_create(
        user=user, defaults={"center": user.center}
    )

    raw_token, _token = _create_mobile_access_token(request, user, user.center, data)
    return _ok(
        access_token=raw_token,
        yangi=yangi,
        profil=_oyinchi_profil_dict(user),
    )


@csrf_exempt
@require_POST
@mobile_login_required
def game_profile_setup(request):
    """Ro'yxatdan o'tgandan keyingi ma'lumot: ism, familya, yosh."""
    user = request.user
    if not getattr(user, "game_only", False):
        return _error(
            "Bu amal faqat o'yin uchun ro'yxatdan o'tganlarga.",
            status=403,
            code="faqat_oyinchi",
        )

    data = _body(request)
    ism = str(data.get("ism") or "").strip()
    familya = str(data.get("familya") or "").strip()

    if len(ism) < 2:
        return _error("Ismingizni kiriting.", code="ism_qisqa")
    if len(familya) < 2:
        return _error("Familyangizni kiriting.", code="familya_qisqa")

    # Yosh yoki tug'ilgan sana — ikkalasidan biri yetadi.
    sana = None
    xom_sana = str(data.get("tugilgan_sana") or "").strip()
    if xom_sana:
        sana = parse_date(xom_sana)
        if sana is None:
            return _error("Tug'ilgan sana noto'g'ri.", code="sana_notogri")
    else:
        try:
            yosh = int(data.get("yosh") or 0)
        except (TypeError, ValueError):
            yosh = 0
        if not (5 <= yosh <= 100):
            return _error("Yoshingizni kiriting (5–100).", code="yosh_notogri")
        bugun = timezone.localdate()
        # Aniq sana bo'lmasa, yoshdan taxminiy tug'ilgan yilni yozamiz.
        sana = bugun.replace(year=bugun.year - yosh)

    user.ism = ism[:100]
    user.familya = familya[:120]
    user.birth_date = sana
    user.save(update_fields=["ism", "familya", "birth_date"])

    return _ok(profil=_oyinchi_profil_dict(user))


@require_GET
@mobile_login_required
def game_my_profile(request):
    """Mustaqil o'yinchi profili + o'yin statistikasi."""
    center = _center(request)
    profile = profil_ol(request.user, center)
    return _ok(
        profil=_oyinchi_profil_dict(request.user),
        oyin=_profil_dict(profile, request),
        orin=_reyting(profile),
    )


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
    data = _body(request)

    # `mode_id` — katalogdagi duel o'yini (yangi ilova yuboradi). Berilmasa
    # eski standart duel o'ynaladi — eski ilova versiyalari ishlayveradi.
    mode = None
    mode_id = data.get("mode_id")
    if isinstance(mode_id, int):
        mode = (
            GameMode.objects.filter(faol=True, id=mode_id)
            .filter(Q(center__isnull=True) | Q(center=center))
            .prefetch_related("kategoriyalar")
            .first()
        )

    # `raqib_id` berilsa — tarixdagi o'sha robot bilan revansh.
    raqib_id = data.get("raqib_id")
    duel, xato = duel_boshla(
        request.user,
        center,
        raqib_id=int(raqib_id) if isinstance(raqib_id, int) else None,
        mode=mode,
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

    if xato == "pro_kerak":
        return _error(
            "Bu o'yin faqat tarifli o'quvchilar uchun.", status=403, code="pro_kerak"
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

    # Robot bilan: javoblari duel boshida hisoblangan, lekin bosqichma-bosqich
    # ochiladi. Odam bilan: juft dueldan jonli o'qiladi.
    jami = raqib_jami(duel, tartib)

    return _ok(
        togri=dq.togri,
        togri_javob=dq.savol.togri_javob,
        izoh=dq.savol.izoh,
        olingan_ball=dq.olingan_ball,
        raqib_togri=dq.raqib_togri,
        raqib_ball=dq.raqib_ball,
        ball=duel.ball,
        raqib_jami=jami,
        pvp=duel.pvp,
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
# O'YINLAR KATALOGI
#
# Admin panelida yangi o'yin qo'shilishi bilanoq u shu ro'yxatga tushadi va
# ilovada paydo bo'ladi — ilovani yangilash shart emas.
# ═══════════════════════════════════════════════════════════════

def _savol_sanogi(center) -> list[tuple[int, str, int]]:
    """(kategoriya_id, daraja, savollar_soni) — bitta so'rovda.

    Har o'yin uchun alohida COUNT qilmaslik uchun shunday: katalogda 20 ta
    o'yin bo'lsa ham baza bilan bir marta gaplashamiz.
    """
    rows = (
        Question.objects.filter(faol=True, kategoriya__faol=True)
        .filter(Q(center__isnull=True) | Q(center=center))
        .values("kategoriya_id", "kategoriya__daraja")
        .annotate(soni=Count("id"))
    )
    return [(r["kategoriya_id"], r["kategoriya__daraja"], r["soni"]) for r in rows]


def _mode_savol_soni(mode: GameMode, sanoq: list[tuple[int, str, int]]) -> int:
    kat_idlari = {k.id for k in mode.kategoriyalar.all() if k.faol}
    jami = 0
    for kategoriya_id, daraja, soni in sanoq:
        if kat_idlari and kategoriya_id not in kat_idlari:
            continue
        if mode.daraja and daraja != mode.daraja:
            continue
        jami += soni
    return jami


def _oyin_dict(
    mode: GameMode,
    request,
    *,
    profile: GameProfile,
    mavjud_savol: int,
    qulf_soniya: int = 0,
) -> dict:
    motor = mode.motor_obyekt
    min_savol = motor.min_savol if motor else 1

    # Qulf sabablari — ilova shuni tugma ostida tushuntirib yozadi.
    qulf = ""
    if motor is None:
        qulf = "motor_nomalum"
    elif mavjud_savol < min_savol:
        qulf = "savol_yetarli_emas"
    elif mode.faqat_pro and not profile.pro:
        qulf = "pro_kerak"
    elif qulf_soniya > 0:
        # Bu o'yin yaqinda o'ynalgan — hammasini teng o'ynash uchun kutish kerak.
        qulf = "oyin_qulflangan"
    elif mode.jon_narxi > 0 and profile.joriy_jon < mode.jon_narxi:
        qulf = "jon_yoq"

    return {
        "id": mode.id,
        "slug": mode.slug,
        "nom": mode.nom,
        "izoh": mode.izoh or (motor.izoh if motor else ""),
        "yoriqnoma": mode.qoida,
        "motor": mode.motor,
        "motor_nomi": motor.nom if motor else mode.motor,
        "ikonka": mode.belgi,
        "rang": mode.tus,
        "rasm": request.build_absolute_uri(mode.rasm.url) if mode.rasm else None,
        "savollar_soni": min(mode.savollar_soni, mavjud_savol) or mode.savollar_soni,
        "savol_soniya": mode.savol_soniya,
        "jon_narxi": mode.jon_narxi,
        "xp_mukofot": mode.xp_mukofot,
        "sozlamalar": mode.toliq_sozlamalar,
        "javob_ochiq": bool(motor and motor.javob_ochiq),
        "duel_oqimi": mode.duel_oqimi,
        "faqat_pro": mode.faqat_pro,
        "mavjud_savol": mavjud_savol,
        "ochiq": qulf == "",
        "qulf": qulf,
        # O'yin qayta ochilishiga qancha qolgani (soniya). 0 = ochiq.
        "qulf_soniya": qulf_soniya,
    }


@require_GET
@mobile_login_required
def game_catalog(request):
    """Ilova ko'rsatadigan o'yinlar ro'yxati."""
    center = _center(request)
    profile = profil_ol(request.user, center)

    # Yarim qolgan sessiyalarni va raqibi tugatgan duellarni yopib qo'yamiz —
    # aks holda tarix chalkashadi va PvP natijasi abadiy kutilib qolardi.
    eskirgan_sessiyalarni_yop(request.user)
    pvp_kutayotganlarni_yakunla(request.user)

    modes = (
        GameMode.objects.filter(faol=True)
        .filter(Q(center__isnull=True) | Q(center=center))
        .prefetch_related("kategoriyalar")
    )
    sanoq = _savol_sanogi(center)
    qulflar = qulflar_xaritasi(profile)

    oyinlar = [
        _oyin_dict(
            mode,
            request,
            profile=profile,
            mavjud_savol=_mode_savol_soni(mode, sanoq),
            qulf_soniya=qulflar.get(mode.id, 0),
        )
        for mode in modes
    ]

    return _ok(
        profil=_profil_dict(profile, request),
        orin=_reyting(profile),
        oyinlar=oyinlar,
        # Ilova tanimaydigan motor uchun hech bo'lmasa nomi va qoidasi bo'lsin.
        motorlar=[m.dict() for m in MOTORLAR.values()],
    )


# ═══════════════════════════════════════════════════════════════
# O'YINNI O'YNASH — duel va yakka sessiyalar uchun bitta kirish nuqtasi
# ═══════════════════════════════════════════════════════════════

_XATO_JAVOBLARI = {
    "motor_nomalum": (
        "Bu o'yin ilovaning yangi versiyasini talab qiladi.",
        409,
    ),
    "pro_kerak": ("Bu o'yin faqat tarifli o'quvchilar uchun.", 403),
    "raqib_yoq": ("Raqib topilmadi. Admin paneldan robot qo'shing.", 409),
    "raqib_topilmadi": ("Bu raqib bilan qayta o'ynab bo'lmaydi.", 404),
}


def _boshlash_xatosi(xato: str, mode: GameMode, profile: GameProfile):
    if xato == "jon_yoq":
        return _error(
            "Jonlaringiz tugadi.",
            status=409,
            code="jon_yoq",
            keyingi_jon_soniya=profile.keyingi_jon_soniya(),
        )
    if xato == "oyin_qulflangan":
        qolgan = qulflangan_soniya(profile, mode)
        soat = qolgan // 3600
        daqiqa = (qolgan % 3600) // 60
        qachon = f"{soat} soat {daqiqa} daqiqa" if soat else f"{daqiqa} daqiqa"
        return _error(
            f"«{mode.nom}» yaqinda o'ynalgan. {qachon}dan keyin qayta ochiladi — "
            "shu vaqt ichida boshqa o'yinlarni sinab ko'ring.",
            status=409,
            code="oyin_qulflangan",
            qulf_soniya=qolgan,
        )
    if xato == "savol_yetarli_emas":
        return _error(
            f"«{mode.nom}» uchun savollar yetarli emas. "
            "Admin paneldan savol qo'shing.",
            status=409,
            code="savol_yetarli_emas",
        )
    matn, status = _XATO_JAVOBLARI.get(xato, ("O'yinni boshlab bo'lmadi.", 400))
    return _error(matn, status=status, code=xato or "xato")


@csrf_exempt
@require_POST
@mobile_login_required
def game_play_start(request, mode_id: int):
    """Katalogdagi o'yinni boshlaydi.

    Duel motori bo'lsa duel yaratiladi (robot raqib bilan), qolganlari uchun
    yakka sessiya ochiladi. Ilova ikkalasini `tur` maydoniga qarab ajratadi.
    """
    center = _center(request)
    mode = (
        GameMode.objects.filter(faol=True, id=mode_id)
        .filter(Q(center__isnull=True) | Q(center=center))
        .prefetch_related("kategoriyalar")
        .first()
    )
    if mode is None:
        return _error("O'yin topilmadi.", status=404, code="oyin_topilmadi")

    motor = mode.motor_obyekt
    if motor is None:
        return _boshlash_xatosi("motor_nomalum", mode, profil_ol(request.user, center))

    if mode.duel_oqimi:
        data = _body(request)
        raqib_id = data.get("raqib_id")

        # Tasodifiy duel — avval odam raqib qidiramiz. `raqib_id` berilgan
        # bo'lsa (revansh) to'g'ridan-to'g'ri robot bilan o'ynaladi.
        if raqib_id is None and data.get("robot") is not True:
            javob = _duel_navbatga(request, center, mode)
            if javob is not None:
                return javob

        duel, xato = duel_boshla(
            request.user,
            center,
            raqib_id=int(raqib_id) if isinstance(raqib_id, int) else None,
            mode=mode,
        )
        if xato:
            return _boshlash_xatosi(xato, mode, profil_ol(request.user, center))

        profile = profil_ol(request.user, center)
        return _ok(
            tur="duel",
            duel_id=duel.id,
            motor=mode.motor,
            oyin_nomi=mode.nom,
            sozlamalar=mode.toliq_sozlamalar,
            savol_soniya=mode.savol_soniya,
            raqib_nomi=duel.raqib_nomi,
            raqib_avatar=_avatar_url(duel.raqib, request) if duel.raqib else None,
            savollar=[
                {
                    "tartib": dq.tartib,
                    "tur": dq.savol.tur,
                    "savol": dq.savol.savol,
                    "variantlar": dq.variantlar,
                    "audio": request.build_absolute_uri(dq.savol.audio.url)
                    if dq.savol.audio
                    else None,
                    "rasm": request.build_absolute_uri(dq.savol.rasm.url)
                    if dq.savol.rasm
                    else None,
                }
                for dq in duel.savollar.select_related("savol").all()
            ],
            jon=profile.joriy_jon,
            max_jon=profile.max_jon,
        )

    sessiya, xato = sessiya_boshla(request.user, center, mode)
    if xato:
        return _boshlash_xatosi(xato, mode, profil_ol(request.user, center))

    profile = profil_ol(request.user, center)
    return _ok(
        tur="sessiya",
        sessiya_id=sessiya.id,
        motor=mode.motor,
        oyin_nomi=mode.nom,
        sozlamalar=mode.toliq_sozlamalar,
        savol_soniya=mode.savol_soniya,
        savollar=[
            savol_dict(sq, motor, request)
            for sq in sessiya.savollar.select_related("savol").all()
        ],
        jon=profile.joriy_jon,
        max_jon=profile.max_jon,
    )


# ═══════════════════════════════════════════════════════════════
# REAL DUEL — raqib qidirish
# ═══════════════════════════════════════════════════════════════

def _duel_savollari(mode: GameMode) -> list:
    return list(mode.savollar_qs().order_by("?")[: max(1, mode.savollar_soni)])


def _duel_dict(duel, request, mode: GameMode, profile: GameProfile) -> dict:
    return {
        "tur": "duel",
        "duel_id": duel.id,
        "pvp": duel.pvp,
        "motor": mode.motor,
        "oyin_nomi": mode.nom,
        "sozlamalar": mode.toliq_sozlamalar,
        "savol_soniya": mode.savol_soniya,
        "raqib_nomi": duel.raqib_nomi,
        "raqib_avatar": _avatar_url(duel.raqib, request) if duel.raqib else None,
        "savollar": [
            {
                "tartib": dq.tartib,
                "tur": dq.savol.tur,
                "savol": dq.savol.savol,
                "variantlar": dq.variantlar,
                "audio": request.build_absolute_uri(dq.savol.audio.url)
                if dq.savol.audio
                else None,
                "rasm": request.build_absolute_uri(dq.savol.rasm.url)
                if dq.savol.rasm
                else None,
            }
            for dq in duel.savollar.select_related("savol").all()
        ],
        "jon": profile.joriy_jon,
        "max_jon": profile.max_jon,
    }


def _duel_navbatga(request, center, mode: GameMode):
    """Duelni navbatga qo'yadi. Raqib darhol topilsa duelni qaytaradi."""
    profile = profil_ol(request.user, center)

    # Navbatga qo'yishdan oldin o'ynay olishini tekshiramiz — aks holda
    # o'quvchi 15 soniya kutib, keyin "jon yo'q" degan javob olardi.
    if mode.faqat_pro and not profile.pro:
        return _boshlash_xatosi("pro_kerak", mode, profile)
    if qulflangan_soniya(profile, mode) > 0:
        return _boshlash_xatosi("oyin_qulflangan", mode, profile)
    if mode.jon_narxi > 0 and profile.joriy_jon < mode.jon_narxi:
        return _boshlash_xatosi("jon_yoq", mode, profile)

    savollar = _duel_savollari(mode)
    if len(savollar) < max(1, mode.savollar_soni):
        return _boshlash_xatosi("savol_yetarli_emas", mode, profile)

    navbat, duel = navbatga_qoy(request.user, center, mode, savollar)

    if duel is not None:
        return _ok(**_duel_dict(duel, request, mode, profil_ol(request.user, center)))

    return _ok(
        tur="kutish",
        navbat_id=navbat.id,
        kutish_soniya=NAVBAT_KUTISH_SONIYA,
        oyin_nomi=mode.nom,
    )


def _navbat_ol(request, navbat_id: int) -> DuelQueue | None:
    return DuelQueue.objects.filter(id=navbat_id, user=request.user).first()


@require_GET
@mobile_login_required
def game_queue_status(request, navbat_id: int):
    """Ilova har 2 soniyada shu yerga so'rov yuboradi."""
    navbat = _navbat_ol(request, navbat_id)
    if navbat is None:
        return _error("Navbat topilmadi.", status=404)

    holat, duel = navbat_holati(navbat)
    if holat == "topildi" and duel is not None:
        return _ok(
            holat="topildi",
            **_duel_dict(duel, request, navbat.mode, profil_ol(request.user, navbat.center)),
        )

    qolgan = max(
        0,
        NAVBAT_KUTISH_SONIYA
        - int((timezone.now() - navbat.yaratilgan).total_seconds()),
    )
    return _ok(holat=holat, qolgan_soniya=qolgan)


@csrf_exempt
@require_POST
@mobile_login_required
def game_queue_robot(request, navbat_id: int):
    """Raqib topilmadi — robot bilan o'ynaymiz."""
    navbat = _navbat_ol(request, navbat_id)
    if navbat is None:
        return _error("Navbat topilmadi.", status=404)

    duel, xato = robotga_otkaz(navbat)
    if xato:
        return _boshlash_xatosi(xato, navbat.mode, profil_ol(request.user, navbat.center))

    return _ok(
        **_duel_dict(duel, request, navbat.mode, profil_ol(request.user, navbat.center))
    )


@csrf_exempt
@require_POST
@mobile_login_required
def game_queue_cancel(request, navbat_id: int):
    navbat = _navbat_ol(request, navbat_id)
    if navbat is None:
        return _error("Navbat topilmadi.", status=404)
    navbatni_bekor_qil(navbat)
    return _ok(bekor=True)


def _sessiya_ol(request, sessiya_id: int) -> GameSession | None:
    return GameSession.objects.filter(id=sessiya_id, user=request.user).first()


@csrf_exempt
@require_POST
@mobile_login_required
def game_session_answer(request, sessiya_id: int):
    sessiya = _sessiya_ol(request, sessiya_id)
    if sessiya is None:
        return _error("Sessiya topilmadi.", status=404)
    if sessiya.holat == GameSession.HOLAT_TUGAGAN:
        return _error("Bu o'yin allaqachon tugagan.", status=409, code="tugagan")

    data = _body(request)
    tartib = data.get("tartib")
    if not isinstance(tartib, int):
        return _error("«tartib» butun son bo'lishi kerak.")

    sq = sessiya_javob_yoz(
        sessiya,
        tartib,
        str(data.get("tanlangan") or ""),
        int(data.get("sarflangan_ms") or 0),
    )
    if sq is None:
        return _error(
            "Bu savolga javob berib bo'lingan yoki savol topilmadi.", status=409
        )

    return _ok(
        togri=sq.togri,
        togri_javob=sq.savol.togri_javob,
        izoh=sq.savol.izoh,
        olingan_ball=sq.olingan_ball,
        ball=sessiya.ball,
        togri_javoblar=sessiya.togri_javoblar,
        xato_javoblar=sessiya.xato_javoblar,
    )


@csrf_exempt
@require_POST
@mobile_login_required
def game_session_finish(request, sessiya_id: int):
    sessiya = _sessiya_ol(request, sessiya_id)
    if sessiya is None:
        return _error("Sessiya topilmadi.", status=404)
    return _ok(**sessiya_yakunla(sessiya))


@require_GET
@mobile_login_required
def game_session_history(request):
    """Yakka o'yinlar tarixi — duel tarixidan alohida."""
    sessiyalar = (
        GameSession.objects
        .filter(user=request.user, holat=GameSession.HOLAT_TUGAGAN)
        .select_related("mode")[:50]
    )
    return _ok(
        sessiyalar=[
            {
                "id": s.id,
                "mode_id": s.mode_id,
                "oyin_nomi": s.oyin_nomi,
                "motor": s.motor,
                "ikonka": s.mode.belgi if s.mode else "🎮",
                "rang": s.mode.tus if s.mode else "#0EA5E9",
                "ball": s.ball,
                "togri_javoblar": s.togri_javoblar,
                "jami_savol": s.jami_savol,
                "aniqlik": round(s.aniqlik * 100),
                "olingan_xp": s.olingan_xp,
                "olingan_chaqmoq": float(s.olingan_chaqmoq),
                "sana": s.tugagan.isoformat() if s.tugagan else None,
            }
            for s in sessiyalar
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

    # Bu reyting **faqat o'yin ichida** — o'quv markazining chaqmoq reytingiga
    # aloqasi yo'q. «Umumiy» doirada barcha markazlar o'quvchilari va ilovani
    # o'zi o'rnatib ro'yxatdan o'tganlar bir ro'yxatda ko'rinadi.
    doira = request.GET.get("doira", "markaz")
    if center is None:
        # Markazsiz o'yinchi uchun «markazim» doirasining ma'nosi yo'q.
        doira = "umumiy"

    qs = GameProfile.objects.select_related("user")
    if doira == "markaz":
        qs = qs.filter(center=center)

    top = qs.order_by("-hafta_xp", "-xp")[:50]

    return _ok(
        doira=doira,
        # Markazsiz o'yinchida doira almashtirgich ilovada ko'rsatilmaydi.
        markaz_bor=center is not None,
        liga=profile.liga,
        mening_orinim=_umumiy_orin(profile) if doira == "umumiy" else _reyting(profile),
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

    kutayotgan = (
        TarifSorovi.objects
        .filter(user=request.user, holat=TarifSorovi.HOLAT_KUTILMOQDA)
        .select_related("tarif")
        .first()
    )

    return _ok(
        joriy_tarif=obuna.tarif.nom if obuna else None,
        tugaydi=obuna.tugaydi.isoformat() if obuna else None,
        # Bepul rejaning qoidalari — ilova taqqoslash uchun ko'rsatadi.
        bepul={
            "jon_soni": BEPUL_JON,
            "jon_soat": BEPUL_JON_SOAT,
            "oyin_qulf_soat": BEPUL_OYIN_QULF_SOAT,
        },
        joriy={
            "jon_soni": profile.max_jon,
            "jon_soat": profile.jon_soat,
            "oyin_qulf_soat": profile.oyin_qulf_soat,
            "chaqmoq_bonus_foiz": profile.chaqmoq_bonus_foiz,
        },
        kutayotgan_sorov=(
            {
                "id": kutayotgan.id,
                "tarif": kutayotgan.tarif.nom,
                "usul": kutayotgan.usul,
                "narx_som": kutayotgan.narx_som,
                "sana": kutayotgan.yaratilgan.isoformat(),
            }
            if kutayotgan
            else None
        ),
        tariflar=[
            {
                "id": t.id,
                "nom": t.nom,
                "narx_som": t.narx_som,
                "haftalik_narx": t.haftalik_narx,
                "kun": t.kun,
                "jon_soni": t.jon_soni,
                "soat": t.soat,
                "oyin_qulf_soat": t.oyin_qulf_soat,
                "chaqmoq_bonus_foiz": t.chaqmoq_bonus_foiz,
                "tavsif": t.tavsif,
                "izoh": t.izoh,
                "joriy": bool(obuna and obuna.tarif_id == t.id),
            }
            for t in Tarif.objects.filter(faol=True)
        ],
    )


@csrf_exempt
@require_POST
@mobile_login_required
def game_tariff_buy(request, tarif_id: int):
    """Tarif sotib olish so'rovi.

    `usul` = "click" → onlayn to'lov havolasi qaytariladi;
    `usul` = "naqd" → admin qo'lda tasdiqlaydigan so'rov yaratiladi.
    """
    tarif = Tarif.objects.filter(id=tarif_id, faol=True).first()
    if tarif is None:
        return _error("Tarif topilmadi.", status=404, code="tarif_topilmadi")

    usul = str(_body(request).get("usul") or TarifSorovi.USUL_CLICK).strip()
    if usul not in {TarifSorovi.USUL_CLICK, TarifSorovi.USUL_NAQD}:
        return _error("To'lov usuli noto'g'ri.", code="usul_notogri")

    center = _center(request)

    # Bir vaqtda bitta kutayotgan so'rov — takror bosishdan himoya.
    mavjud = TarifSorovi.objects.filter(
        user=request.user, holat=TarifSorovi.HOLAT_KUTILMOQDA
    ).first()
    if mavjud is not None:
        return _error(
            "Sizda hali tasdiqlanmagan so'rov bor.",
            status=409,
            code="sorov_mavjud",
            sorov_id=mavjud.id,
        )

    sorov = TarifSorovi.objects.create(
        user=request.user,
        tarif=tarif,
        center=center,
        usul=usul,
        narx_som=tarif.narx_som,
    )

    # Ikkala usulda ham o'quvchi Telegram orqali admin bilan bog'lanadi:
    # so'rov superadmin panelida ko'rinadi, to'lov kelishuvi esa lichkada
    # bo'ladi. Click avtomatik oqimi merchant sozlangach yoqiladi.
    return _ok(
        sorov_id=sorov.id,
        usul=usul,
        telegram=_telegram_havolasi(sorov),
        xabar=(
            f"«{tarif.nom}» uchun so'rov yuborildi. "
            "Telegramda to'lovni kelishing — tasdiqlangach tarif yoqiladi."
        ),
    )


def _telegram_havolasi(sorov: TarifSorovi) -> dict:
    """Telegram lichkaga o'tish uchun havola va tayyor xabar matni.

    Ilova bu matnni nusxalab, foydalanuvchi faqat «yuborish» bosadi —
    admin so'rov raqamini darrov ko'radi.
    """
    username = str(getattr(settings, "GAME_SUPPORT_TELEGRAM", "") or "").strip().lstrip("@")
    ism = (sorov.user.ism or "").strip() or sorov.user.email
    matn = (
        f"Salom! ChaqmoqApp o'yinida «{sorov.tarif.nom}» tarifini "
        f"sotib olmoqchiman.\n"
        f"So'rov raqami: #{sorov.id}\n"
        f"Summa: {sorov.narx_som:,} so'm\n"
        f"Ism: {ism}"
    ).replace(",", " ")

    return {
        "username": username,
        "url": f"https://t.me/{username}" if username else "",
        "matn": matn,
    }


@require_GET
@mobile_login_required
def game_tariff_requests(request):
    """O'quvchining tarif so'rovlari tarixi."""
    sorovlar = (
        TarifSorovi.objects.filter(user=request.user)
        .select_related("tarif")[:30]
    )
    return _ok(
        sorovlar=[
            {
                "id": s.id,
                "tarif": s.tarif.nom,
                "narx_som": s.narx_som,
                "usul": s.usul,
                "holat": s.holat,
                "sana": s.yaratilgan.isoformat(),
                "tasdiqlangan": s.tasdiqlangan.isoformat() if s.tasdiqlangan else None,
            }
            for s in sorovlar
        ]
    )


# ═══════════════════════════════════════════════════════════════
# SHIKOYAT VA TAKLIFLAR
# ═══════════════════════════════════════════════════════════════

@csrf_exempt
@require_POST
@mobile_login_required
def game_feedback_send(request):
    data = _body(request)
    matn = str(data.get("matn") or "").strip()
    tur = str(data.get("tur") or Feedback.TUR_TAKLIF).strip()

    if len(matn) < 5:
        return _error("Xabar juda qisqa — kamida 5 ta belgi.", code="matn_qisqa")
    if tur not in dict(Feedback.TUR_CHOICES):
        tur = Feedback.TUR_TAKLIF

    mode = None
    mode_id = data.get("mode_id")
    if isinstance(mode_id, int):
        mode = GameMode.objects.filter(id=mode_id).first()

    feedback = Feedback.objects.create(
        user=request.user,
        center=_center(request),
        mode=mode,
        tur=tur,
        matn=matn[:4000],
        aloqa=str(data.get("aloqa") or "").strip()[:120],
    )
    return _ok(
        id=feedback.id,
        xabar="Xabaringiz yuborildi. Rahmat!",
    )


@require_GET
@mobile_login_required
def game_feedback_list(request):
    murojaatlar = Feedback.objects.filter(user=request.user)[:30]
    return _ok(
        turlar=[{"kalit": k, "nom": n} for k, n in Feedback.TUR_CHOICES],
        murojaatlar=[
            {
                "id": f.id,
                "tur": f.tur,
                "tur_nomi": f.get_tur_display(),
                "matn": f.matn,
                "holat": f.holat,
                "holat_nomi": f.get_holat_display(),
                "javob": f.javob,
                "sana": f.yaratilgan.isoformat(),
            }
            for f in murojaatlar
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
