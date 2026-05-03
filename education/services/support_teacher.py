"""Support teacher feature — bitta o'quv markazi uchun ixtiyoriy.

Markaz `features` JSON'ida `support_teacher_enabled: true` bo'lsa yoqiladi.
SuperAdmin panel (`/platform/center/<id>/edit/`)'dan toggle qilinadi.

Davomat asosiy o'qituvchi tomonidan olinadi, lekin oylik hisoblashda
support xodimga ham `Group.support_foiz` foiziga mos summa yoziladi.
"""

from __future__ import annotations

from typing import Iterable

from django.db.models import Prefetch, Q

from core.center_features import (
    FEATURE_SUPPORT_TEACHER,
    center_ui_feature_enabled,
)
from education.services.tuition import teacher_monthly_financials


# Backward-compatibility uchun eski konstanta.
FEATURE_KEY = FEATURE_SUPPORT_TEACHER


def is_support_enabled(center) -> bool:
    """Markazda support_teacher xususiyati yoqilgan-mi."""
    return center_ui_feature_enabled(center, FEATURE_SUPPORT_TEACHER, default=False)


def set_support_enabled(center, enabled: bool):
    """Markazga feature'ni yoqish/o'chirish (programmatic API)."""
    features = dict(getattr(center, "features", None) or {})
    features[FEATURE_SUPPORT_TEACHER] = bool(enabled)
    center.features = features
    center.save(update_fields=["features"])


def get_support_groups_for_user(user, center=None):
    """Foydalanuvchi support sifatida belgilangan barcha guruhlar."""
    from education.models import Enrollment, Group

    qs = Group.objects.filter(
        support_teacher=user,
        is_archived=False,
        support_foiz__gt=0,
    )
    if center:
        qs = qs.filter(center=center)
    return list(
        qs.prefetch_related(
            Prefetch(
                "enrollments",
                queryset=Enrollment.all_objects.select_related("student"),
                to_attr="all_enrollments",
            )
        )
    )


def calculate_support_salary(user, year, month, center=None):
    """Foydalanuvchi support sifatida ishlagan oylik ulushini hisoblaydi.

    Logika asosiy o'qituvchi salary'siga o'xshash:
    har student davomati uchun `support_foiz` foiziga to'g'ri keladigan summa.
    Markaz foydasiga ta'sir qilish (alohida) — bu yerda hisoblanmaydi
    chunki hozirgi tizimda asosiy o'qituvchi uchun `center_profit` allaqachon
    `turnover - teacher_salary` deb hisoblangan; support summasi shu
    `center_profit`'dan ayriladi (markaz hisobotida quyidagicha ko'rsatiladi).
    """
    groups = get_support_groups_for_user(user, center=center)
    if not groups:
        return {
            "salary": 0,
            "attendance_count": 0,
            "details": [],
        }

    from education.services.historical_finance_service import HistoricalFinanceService

    group_ids = [g.id for g in groups]
    month_start, month_end = HistoricalFinanceService._month_bounds(year, month)
    att_lookup = HistoricalFinanceService._attendance_lookup(group_ids, year, month)
    history_lookup = HistoricalFinanceService._history_lookup(group_ids)

    total_salary = 0
    total_lessons = 0
    details = []

    for group in groups:
        support_foiz = int(getattr(group, "support_foiz", 0) or 0)
        if support_foiz <= 0:
            continue

        enr_lookup = {
            e.student_id: e for e in getattr(group, "all_enrollments", [])
        }

        group_salary = 0
        group_lessons = 0
        group_students = []

        for student_id, days in att_lookup.get(group.id, {}).items():
            if not days:
                continue
            enrollment = enr_lookup.get(student_id)
            if enrollment is None:
                continue

            membership_hit = HistoricalFinanceService._student_was_in_group(
                history_lookup, group.id, student_id, month_start, month_end
            )
            if membership_hit is False:
                continue
            if membership_hit is None:
                created_at = getattr(enrollment, "created_at", None)
                created_date = created_at.date() if created_at else None
                if created_date and created_date > month_end:
                    continue

            financials = teacher_monthly_financials(
                enrollment, len(days), teacher_percent=support_foiz
            )
            if financials["billable_lessons"] <= 0:
                continue

            group_salary += financials["teacher_salary"]
            group_lessons += financials["billable_lessons"]
            try:
                student_name = (
                    enrollment.student.get_full_name() or enrollment.student.email
                )
            except Exception:
                student_name = "Noma'lum"
            group_students.append(
                {
                    "student_id": student_id,
                    "student_name": student_name,
                    "attended": financials["billable_lessons"],
                    "daromad": financials["teacher_salary"],
                }
            )

        if group_salary > 0:
            total_salary += group_salary
            total_lessons += group_lessons
            details.append(
                {
                    "group_id": group.id,
                    "group_name": group.nom,
                    "salary": group_salary,
                    "attendance": group_lessons,
                    "fi": support_foiz,
                    "is_support": True,
                    "students": group_students,
                }
            )

    return {
        "salary": int(total_salary),
        "attendance_count": int(total_lessons),
        "details": details,
    }


def list_support_user_ids(center=None) -> set:
    """Markaz ichida support qilib biriktirilgan barcha userlar ro'yxati (set of ids)."""
    from education.models import Group

    qs = Group.objects.filter(
        is_archived=False,
        support_teacher__isnull=False,
        support_foiz__gt=0,
    )
    if center:
        qs = qs.filter(center=center)
    return set(qs.values_list("support_teacher_id", flat=True))


def staff_queryset_for_support_dropdown(center):
    """Group form'da support sifatida tanlanishi mumkin bo'lgan xodimlar.

    Talabalar va ota-onalar ro'yxatga kirmaydi.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    qs = User.objects.exclude(role__in=["student", "parent"])
    if center:
        qs = qs.filter(center=center)
    return qs.order_by("ism", "familya", "email")
