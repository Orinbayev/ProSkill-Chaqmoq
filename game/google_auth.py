"""Google hisobi orqali o'yinga kirish.

O'quv markaziga bog'liq bo'lmagan foydalanuvchi ilovani o'rnatib, Google
hisobi bilan ro'yxatdan o'tadi. Bunday foydalanuvchi `game_only=True` va
`center=None` bo'ladi — unga davomat, to'lov va qarzdorlik ko'rinmaydi.

Xavfsizlik: ilova yuborgan **ID token** shu yerda, serverda tekshiriladi.
Ilovaning o'zi "men falonchiман" deb ayta olmaydi — token Google imzosi bilan
tasdiqlanadi va `aud` (client ID) bizniki ekaniga ishonch hosil qilinadi.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

logger = logging.getLogger(__name__)

# Google ID tokenlari shu emitentlar tomonidan beriladi.
KUTILGAN_EMITENTLAR = {"accounts.google.com", "https://accounts.google.com"}


class GoogleXatosi(Exception):
    """Token tekshiruvi o'tmadi."""

    def __init__(self, matn: str, kod: str = "google_xato"):
        super().__init__(matn)
        self.matn = matn
        self.kod = kod


def sozlangan() -> bool:
    return bool(ruxsat_etilgan_client_idlar())


def ruxsat_etilgan_client_idlar() -> list[str]:
    """`GOOGLE_OAUTH_CLIENT_IDS` — vergul bilan ajratilgan client ID'lar.

    iOS, Android va Web uchun alohida client ID bo'ladi; qaysi biri bilan
    kirilganidan qat'i nazar token qabul qilinishi kerak.
    """
    xom = getattr(settings, "GOOGLE_OAUTH_CLIENT_IDS", "") or ""
    return [q.strip() for q in str(xom).split(",") if q.strip()]


def tokenni_tekshir(token: str) -> dict:
    """Google ID tokenini tekshiradi va foydalanuvchi ma'lumotini qaytaradi.

    Qaytadi: {"sub", "email", "ism", "familya", "rasm"}
    """
    if not sozlangan():
        raise GoogleXatosi(
            "Google orqali kirish hozircha sozlanmagan.", "google_sozlanmagan"
        )
    if not token:
        raise GoogleXatosi("Google tokeni yuborilmadi.", "token_yoq")

    idlar = ruxsat_etilgan_client_idlar()
    malumot = None
    oxirgi_xato: Exception | None = None

    # `verify_oauth2_token` bitta audience bilan ishlaydi — barchasini sinaymiz.
    for client_id in idlar:
        try:
            malumot = google_id_token.verify_oauth2_token(
                token, google_requests.Request(), client_id
            )
            break
        except ValueError as xato:
            oxirgi_xato = xato

    if malumot is None:
        logger.warning("Google token tekshirilmadi: %s", oxirgi_xato)
        raise GoogleXatosi(
            "Google hisobini tasdiqlab bo'lmadi. Qaytadan urinib ko'ring.",
            "token_notogri",
        )

    if malumot.get("iss") not in KUTILGAN_EMITENTLAR:
        raise GoogleXatosi("Token manbasi noto'g'ri.", "token_notogri")

    email = str(malumot.get("email") or "").strip().lower()
    if not email:
        raise GoogleXatosi("Google hisobida email topilmadi.", "email_yoq")
    if not malumot.get("email_verified", False):
        raise GoogleXatosi("Google emailingiz tasdiqlanmagan.", "email_tasdiqlanmagan")

    return {
        "sub": str(malumot.get("sub") or ""),
        "email": email,
        "ism": str(malumot.get("given_name") or "").strip(),
        "familya": str(malumot.get("family_name") or "").strip(),
        "rasm": str(malumot.get("picture") or "").strip(),
    }


def foydalanuvchini_top_yoki_yarat(malumot: dict):
    """Google ma'lumotidan foydalanuvchini topadi yoki yaratadi.

    Qaytadi: (user, yangi_yaratildimi).

    Muhim: shu email bilan **o'quv markazi** hisobi allaqachon bo'lsa, uni
    o'yin hisobiga aylantirmaymiz — foydalanuvchi o'z markaz hisobiga kiradi
    va markaz paneli ochiladi.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    email = malumot["email"]
    sub = malumot["sub"]

    mavjud = (
        User.objects.filter(google_sub=sub).first()
        if sub
        else None
    ) or User.objects.filter(email__iexact=email).first()

    if mavjud is not None:
        yangilanadi = []
        if sub and mavjud.google_sub != sub:
            mavjud.google_sub = sub
            yangilanadi.append("google_sub")
        if not mavjud.gmail:
            mavjud.gmail = email
            yangilanadi.append("gmail")
        if yangilanadi:
            mavjud.save(update_fields=yangilanadi)
        return mavjud, False

    with transaction.atomic():
        user = User.objects.create_user(
            email=email,
            password=None,  # Parol yo'q — faqat Google orqali kiriladi.
            ism=malumot.get("ism") or email.split("@")[0],
            familya=malumot.get("familya") or "",
            role="student",
            center=None,
        )
        user.set_unusable_password()
        user.google_sub = sub
        user.gmail = email
        user.game_only = True
        user.save(update_fields=["password", "google_sub", "gmail", "game_only"])

    return user, True
