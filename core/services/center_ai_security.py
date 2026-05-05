from __future__ import annotations

import re

from accounts.models import Center


def _normalize_text(value: str) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("’", "'")
        .replace("`", "'")
        .replace("yoʻ", "yo'")
        .replace("oʻ", "o'")
        .replace("gʻ", "g'")
    )


def can_view_private_details(viewer) -> bool:
    if not viewer or not getattr(viewer, "is_authenticated", False):
        return False
    return bool(
        getattr(viewer, "is_superuser", False)
        or getattr(viewer, "role", None) == "director"
    )


def mask_phone(phone: str) -> str:
    raw = re.sub(r"\D+", "", str(phone or ""))
    if not raw:
        return ""
    if len(raw) <= 4:
        return "*" * len(raw)
    return f"{raw[:4]}***{raw[-2:]}"


def visible_phone(phone: str, viewer) -> str:
    cleaned = str(phone or "").strip()
    if not cleaned:
        return ""
    return cleaned if can_view_private_details(viewer) else mask_phone(cleaned)


def detect_cross_center_probe(center: Center, question: str) -> str:
    q = _normalize_text(question)
    if not q:
        return ""

    generic_patterns = [
        "boshqa markaz",
        "boshqa o'quv markaz",
        "boshqa oquv markaz",
        "barcha markaz",
        "hamma markaz",
        "boshqa filial",
        "hamma filial",
    ]
    if any(pattern in q for pattern in generic_patterns):
        return "generic"

    generic_center_tokens = {
        "center",
        "markaz",
        "o'quv",
        "oquv",
        "talim",
        "ta'lim",
        "academy",
        "crm",
        "test",
        "demo",
    }

    # Bir so'zli oddiy "yaxshi", "tmp", "amirxon" kabi sluglar tasodifan
    # boshqa savollarda (mas. "eng yaxshi o'qituvchi kim?") triggerlanishini
    # oldini olish uchun: kamida 2 ta mazmunli token bo'lishi shart, yoki
    # 1 ta token bo'lsa ham juda uzun (>=10) va so'rovda "boshqa/barcha/hamma"
    # signali bor bo'lsa.
    has_explicit_other = any(p in q for p in ("boshqa ", "barcha ", "hamma "))

    def _is_specific_match(tokens: list[str]) -> bool:
        if not tokens:
            return False
        if not all(token in q for token in tokens):
            return False
        if len(tokens) >= 2:
            return True
        # bitta token — faqat juda uzun (10+ harfli) yoki "boshqa" signali bor bo'lsa
        single = tokens[0]
        return len(single) >= 10 or has_explicit_other

    other_centers = Center.objects.exclude(id=center.id).filter(is_deleted=False).only("id", "name", "slug")
    for other_center in other_centers:
        slug_value = _normalize_text(other_center.slug or "").replace("-", " ")
        slug_tokens = [token for token in slug_value.split() if token and token not in generic_center_tokens and len(token) >= 3]
        if _is_specific_match(slug_tokens):
            return other_center.name

        name_value = _normalize_text(other_center.name or "")
        name_tokens = [token for token in name_value.split() if token and token not in generic_center_tokens and len(token) >= 3]
        if _is_specific_match(name_tokens):
            return other_center.name
    return ""


def guard_cross_center_question(center: Center, question: str) -> str:
    hit = detect_cross_center_probe(center, question)
    if not hit:
        return ""
    return (
        "Boshqa o'quv markaz ma'lumotlari maxfiy. Men faqat siz turgan markazning ichki ma'lumotlari bilan "
        "ishlayman va boshqa markazlar raqamlarini ko'rsatmayman."
    )


def privacy_mode_label(viewer) -> str:
    return "full" if can_view_private_details(viewer) else "limited"
