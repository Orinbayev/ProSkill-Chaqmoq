"""
education/helpers.py

Views va servislar tomonidan umumiy ishlatiladigan yordamchi funksiyalar.
Bu yerda kichik, toza utilitylar joylashadi.
"""

from __future__ import annotations

from datetime import date
from typing import Any


def get_int(querydict_or_dict, key: str, default: int = 0) -> int:
    """GET/POST parametridan xavfsiz int olish."""
    try:
        val = querydict_or_dict.get(key, None)
        if val in (None, "", "None"):
            return default
        return int(val)
    except (TypeError, ValueError):
        return default


def month_first_day(d: date) -> date:
    """Berilgan sananing oy boshini qaytaradi."""
    return date(d.year, d.month, 1)


def add_months(d: date, n: int = 1) -> date:
    """Sanaga n oy qo'shadi."""
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)


def parse_month_str(s: str | None) -> date | None:
    """
    'YYYY-MM' yoki 'YYYY-M' formatidagi satrni date(YYYY, M, 1) ga aylantiradi.
    Xato bo'lsa None qaytaradi.
    """
    if not s:
        return None
    try:
        parts = str(s).strip().split("-")
        if len(parts) == 2:
            y, m = int(parts[0]), int(parts[1])
            if 1 <= m <= 12:
                return date(y, m, 1)
    except (ValueError, TypeError):
        pass
    return None


def model_has_field(model_cls: Any, field_name: str) -> bool:
    """Model da berilgan nom bilan field borligini tekshiradi."""
    return any(f.name == field_name for f in model_cls._meta.get_fields())


def can_manage(user) -> bool:
    """Director yoki manager ekanlini tekshiradi."""
    return user.is_superuser or getattr(user, "role", None) in ("director", "manager")


def can_give_points(user, group) -> bool:
    """Foydalanuvchi guruhga ball bera olishini tekshiradi."""
    if user.is_superuser:
        return True
    role = getattr(user, "role", None)
    if role in ("director", "manager"):
        return True
    if role == "teacher":
        return getattr(group, "oqituvchi_id", None) == user.pk
    return False
