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
    `daily_breakdown` — kunlik daromad grafigi uchun (31 elementli list).
    """
    groups = get_support_groups_for_user(user, center=center)
    if not groups:
        return {
            "salary": 0,
            "attendance_count": 0,
            "details": [],
            "daily_breakdown": [0] * 31,
        }

    from education.services.historical_finance_service import HistoricalFinanceService

    group_ids = [g.id for g in groups]
    month_start, month_end = HistoricalFinanceService._month_bounds(year, month)
    att_lookup = HistoricalFinanceService._attendance_lookup(group_ids, year, month)
    history_lookup = HistoricalFinanceService._history_lookup(group_ids)

    total_salary = 0
    total_lessons = 0
    details = []
    daily_breakdown = [0] * 31

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

            # Kunlik daromadni hisoblash (grafik uchun)
            if financials["billable_lessons"] > 0 and days:
                base = financials["teacher_salary"] // financials["billable_lessons"]
                extra = financials["teacher_salary"] - (base * financials["billable_lessons"])
                for idx, day in enumerate(sorted(days)):
                    day_idx = day - 1
                    if 0 <= day_idx < 31:
                        daily_breakdown[day_idx] += base + (1 if idx < extra else 0)

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
        "daily_breakdown": daily_breakdown,
    }


def get_yearly_support_salary(user, year, center=None) -> list:
    """Support teacher uchun yillik (12 oy) daromad ro'yxatini qaytaradi.

    Qaytaradi: [jan, feb, ..., dec] — har oylik support daromad (so'm).
    """
    groups = get_support_groups_for_user(user, center=center)
    if not groups:
        return [0] * 12

    from education.services.historical_finance_service import HistoricalFinanceService
    from django.db.models import Q

    from education.models import Attendance, StudentGroupHistory

    group_ids = [g.id for g in groups]
    history_lookup = HistoricalFinanceService._history_lookup(group_ids)

    # Bir so'rovda barcha yillik davomatni olamiz
    rows = (
        Attendance.objects.filter(
            group_id__in=group_ids,
            date__year=year,
        )
        .filter(HistoricalFinanceService._billable_attendance_filter())
        .values("group_id", "student_id", "date__month", "date__day")
    )

    # group_id -> month -> student_id -> [days]
    yearly_att: dict = {}
    for row in rows:
        (
            yearly_att
            .setdefault(row["group_id"], {})
            .setdefault(row["date__month"], {})
            .setdefault(row["student_id"], [])
            .append(row["date__day"])
        )

    enr_lookup = {}
    for group in groups:
        enr_lookup[group.id] = {
            e.student_id: e for e in getattr(group, "all_enrollments", [])
        }

    monthly_totals = [0] * 12

    for month_num in range(1, 13):
        month_start, month_end = HistoricalFinanceService._month_bounds(year, month_num)
        month_total = 0

        for group in groups:
            support_foiz = int(getattr(group, "support_foiz", 0) or 0)
            if support_foiz <= 0:
                continue
            enr_map = enr_lookup.get(group.id, {})
            for student_id, days in yearly_att.get(group.id, {}).get(month_num, {}).items():
                if not days:
                    continue
                enrollment = enr_map.get(student_id)
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
                month_total += financials["teacher_salary"]

        monthly_totals[month_num - 1] = int(month_total)

    return monthly_totals


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

    Markazning o'z xodimlaridan tashqari, shu filialda ishlashga ruxsat
    olgan MEHMON o'qituvchilar ham kiradi (`TeacherCenterAccess`) — aks holda
    ko'p filialli o'qituvchini support sifatida tanlab bo'lmasdi.
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    User = get_user_model()
    qs = User.objects.exclude(role__in=["student", "parent"])
    if center:
        qs = qs.filter(
            Q(center=center)
            | Q(
                extra_center_access_teacher__center=center,
                extra_center_access_teacher__is_active=True,
            )
        ).distinct()
    return qs.order_by("ism", "familya", "email")
