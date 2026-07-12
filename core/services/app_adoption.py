"""Mobil ilova (ChaqmoqApp) qamrovi statistikasi.

Har bir o'quv markazда nechta o'quvchi mobil ilovani o'rnatgan/ishlatayotganini
hisoblaydi. "O'rnatgan" = ilovaga kamida bir marta login qilgan (MobileAccessToken
mavjud). "Faol" = oxirgi `active_days` kun ichida ilovadan foydalangan.

Manba: `core.models.MobileAccessToken` (center + user + last_used_at). Yangi
migratsiya kerak emas — mavjud tokenlardan hisoblanadi. Panel (SuperAdmin) va
Telegram bot shu bitta funksiyани ishlatadi.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import Center, User
from core.models import MobileAccessToken


def center_app_adoption(active_days: int = 30, include_zero: bool = True) -> list[dict]:
    """Har markaz uchun mobil ilova qamrovини qaytaradi (eng ko'pdan kamiga tartibda).

    Qaytadi: har markaz uchun dict — id, name, total_students, app_users,
    active_users, adoption_pct.
    """
    active_cutoff = timezone.now() - timedelta(days=active_days)

    # 1) Har markazда jami o'quvchilar soni (soft-delete chiqarilgan — default manager).
    total_by_center = {
        row["center"]: row["total"]
        for row in (
            User.objects.filter(role="student", center__isnull=False)
            .values("center")
            .annotate(total=Count("id"))
        )
    }

    # 2) Har markazда ilovadan foydalangan o'quvchilar (distinct), va faollar.
    token_by_center = {
        row["center"]: row
        for row in (
            MobileAccessToken.objects.filter(
                user__role="student", center__isnull=False
            )
            .values("center")
            .annotate(
                app_users=Count("user", distinct=True),
                active_users=Count(
                    "user", distinct=True, filter=Q(last_used_at__gte=active_cutoff)
                ),
            )
        )
    }

    # 3) Markaz nomlari (demo markazlar chiqariladi).
    center_names = {
        c.id: c.name
        for c in Center.objects.filter(is_demo=False).only("id", "name")
    }

    rows: list[dict] = []
    for center_id, name in center_names.items():
        total = total_by_center.get(center_id, 0)
        tok = token_by_center.get(center_id) or {}
        app_users = tok.get("app_users", 0)
        active_users = tok.get("active_users", 0)
        if not include_zero and app_users == 0:
            continue
        rows.append(
            {
                "id": center_id,
                "name": name,
                "total_students": total,
                "app_users": app_users,
                "active_users": active_users,
                "adoption_pct": round(app_users / total * 100) if total else 0,
            }
        )

    rows.sort(key=lambda r: (r["app_users"], r["adoption_pct"], r["active_users"]), reverse=True)
    return rows


def app_adoption_totals(rows: list[dict] | None = None, active_days: int = 30) -> dict:
    """Umumiy yig'indilar — KPI kartalar uchun."""
    if rows is None:
        rows = center_app_adoption(active_days=active_days)
    total_students = sum(r["total_students"] for r in rows)
    app_users = sum(r["app_users"] for r in rows)
    active_users = sum(r["active_users"] for r in rows)
    return {
        "centers_with_users": sum(1 for r in rows if r["app_users"] > 0),
        "total_students": total_students,
        "app_users": app_users,
        "active_users": active_users,
        "adoption_pct": round(app_users / total_students * 100) if total_students else 0,
    }
