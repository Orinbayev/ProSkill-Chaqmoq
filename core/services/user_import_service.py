"""
core/services/user_import_service.py

Excel orqali foydalanuvchi import qilish bilan bog'liq barcha yordamchi funksiyalar.
Views da bu funksiyalar chaqiriladi, lekin biznes logika shu yerda yashaydi.
"""

from __future__ import annotations

import re
import secrets
import string
import logging

logger = logging.getLogger(__name__)


def normalize_header(x: str) -> str:
    """Excel ustun sarlavhasini normallashtiradi (kichik harf, bo'sh joylar va belgilar olib tashlanadi)."""
    return (
        str(x or "").strip().lower()
        .replace("'", "").replace("\u2018", "").replace("`", "")
        .replace(" ", "").replace("_", "").replace("-", "")
        .replace("(", "").replace(")", "").replace("/", "")
    )


def pick_col(headers_map: dict, *aliases: str) -> int | None:
    """Excel ustunlari xaritasidan birinchi mos keladigan ustun indeksini qaytaradi."""
    for alias in aliases:
        key = normalize_header(alias)
        if key in headers_map:
            return headers_map[key]
    return None


def cell_to_str(v) -> str:
    """Excel katakcha qiymatini stringga aylantiradi."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v)).strip()
    return str(v).strip()


def clean_for_login(text: str) -> str:
    """Ishoralarni va maxsus belgilarni olib tashlab, login uchun mos string hosil qiladi."""
    s = (text or "").strip().lower()
    s = s.replace("o\u2019", "o").replace("o'", "o")
    s = s.replace("g\u2019", "g").replace("g'", "g")
    s = s.replace("\u2018", "").replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def normalize_phone(p: str) -> str:
    """Telefon raqamdan barcha raqam bo'lmagan belgilarni olib tashlaydi."""
    if not p:
        return ""
    return re.sub(r"\D", "", str(p))


def gen_default_password(length: int = 10) -> str:
    """Tasodifiy kuchli parol yaratadi."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def gen_unique_email(user_model, ism: str, familya: str) -> str:
    """Ism va familyadan unikal gmail-ko'rinishidagi email hosil qiladi."""
    first = clean_for_login(ism) or "user"
    last = clean_for_login(familya)
    base = f"{first}.{last}" if last else first

    for _ in range(80):
        suffix = secrets.randbelow(9000) + 1000
        email = f"{base}{suffix}@gmail.com"
        if not user_model.objects.filter(email=email).exists():
            return email

    token = secrets.token_hex(3)
    return f"{base}{token}@gmail.com"


def normalize_gender(val: str | None) -> str | None:
    """
    Jins qiymatini normallashtiradi.
    Qaytaradi: 'male', 'female', yoki None.
    """
    if not val:
        return None
    s = str(val).strip().lower()

    female_exact = {"ayol", "female", "qiz", "f", "jenskiy", "zhenskiy"}
    male_exact = {"erkak", "male", "o'g'il", "o'gil", "ogil", "m", "mujskoy"}

    if s in female_exact:
        return "female"
    if s in male_exact:
        return "male"

    if s.startswith(("ayol", "fem", "qiz")):
        return "female"
    if s.startswith(("erk", "mal", "o\u2019g", "og")):
        return "male"

    return None


def validate_import_row(row_data: dict) -> list[str]:
    """
    Import qatorini tekshiradi va xatolar ro'yxatini qaytaradi.
    Bo'sh ro'yxat = xato yo'q.
    """
    errors = []
    ism = (row_data.get("ism") or "").strip()
    familya = (row_data.get("familya") or "").strip()

    if not ism and not familya:
        errors.append("Ism yoki familya kiritilishi shart.")

    phone = row_data.get("phone", "")
    if phone:
        normalized = normalize_phone(str(phone))
        if normalized and len(normalized) < 9:
            errors.append(f"Telefon raqam noto'g'ri: '{phone}'")

    return errors
