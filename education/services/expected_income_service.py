"""
expected_income_service.py

"Bu oy maksimali" — o'qituvchi oy davomida barcha o'quvchilar oy_dars_soni
dars kelgan taqdirda oladigan maksimal oylik.

Avvalgi versiya StudentGroupHistory dan foydalanardi — bu Enrollment ning
kurs_narhi/oqituvchi_foiz bilan mos kelmasdi va progress_pct noto'g'ri
chiqardi.

Yangi versiya to'liq historical_finance_service._build_dynamic_teacher_salary
bilan bir xil ma'lumot manbayidan foydalanadi: Enrollment.full_course_amount
va teacher.oqituvchi_foizi.
"""

import calendar
from datetime import date

from django.db.models import Prefetch
from django.utils import timezone

from education.models import (
    Enrollment,
    Group,
    StudentGroupHistory,
    TeacherExpectedIncomeSnapshot,
)


def calculate_expected_income(teacher, year=None, month=None, center=None, course_id=None):
    """
    O'qituvchining berilgan oy uchun maksimal kutilgan daromadi.

    Formula (har bir aktiv o'quvchi uchun):
        max_per_student = full_course_amount(enrollment) * teacher_percent / 100

    Bu Enrollment ma'lumotiga asoslanadi — xuddi _build_dynamic_teacher_salary
    kabi. Shu sababli "Bu oy maksimali" = haqiqiy oylik × 100% (barcha dars
    kelgan taqdirda) qiymati to'g'ri chiqadi.
    """
    from education.services.tuition import full_course_amount

    now = timezone.now()
    req_year = int(year) if year else now.year
    req_month = int(month) if month else now.month

    # O'tgan oylar uchun snapshot'dan foydalanish
    if not course_id:
        snapshot = TeacherExpectedIncomeSnapshot.objects.filter(
            teacher=teacher, year=req_year, month=req_month, center=center
        ).first()
        if snapshot and (req_year < now.year or (req_year == now.year and req_month < now.month)):
            return {
                "teacher_id": teacher.id,
                "teacher_name": teacher.ism or teacher.email,
                "active_students": snapshot.active_students,
                "income_per_student": snapshot.income_per_student,
                "expected_income": snapshot.expected_income,
                "breakdown": [],
            }

    # Guruhlarni olish (xuddi _teacher_groups kabi)
    groups_qs = Group.objects.filter(oqituvchi=teacher, is_archived=False)
    if center:
        groups_qs = groups_qs.filter(center=center)
    if course_id:
        groups_qs = groups_qs.filter(category_obj_id=course_id)

    groups = list(
        groups_qs.prefetch_related(
            Prefetch(
                "enrollments",
                queryset=Enrollment.all_objects.select_related("student", "group"),
                to_attr="all_enrollments",
            )
        )
    )

    if not groups:
        return _empty_result(teacher)

    group_ids = [g.id for g in groups]

    # Oy chegaralari
    month_start = date(req_year, req_month, 1)
    month_end = date(req_year, req_month, calendar.monthrange(req_year, req_month)[1])

    # StudentGroupHistory — faqat sana filtratsiyasi uchun
    history_lookup: dict[int, dict[int, list[tuple]]] = {}
    for row in StudentGroupHistory.objects.filter(group_id__in=group_ids).values(
        "group_id", "student_id", "start_date", "end_date"
    ):
        history_lookup.setdefault(row["group_id"], {}).setdefault(
            row["student_id"], []
        ).append((row["start_date"], row["end_date"]))

    # O'qituvchining umumiy foizi
    teacher_percent = int(getattr(teacher, "oqituvchi_foizi", 0) or 0)

    total_expected = 0
    total_active_students = 0
    breakdown = []

    for group in groups:
        # Enrollment lookup: faol enrollment ustuvor (_build_dynamic_teacher_salary kabi)
        student_enr: dict[int, Enrollment] = {}
        for enr in getattr(group, "all_enrollments", []):
            sid = enr.student_id
            existing = student_enr.get(sid)
            if existing is None:
                student_enr[sid] = enr
            elif getattr(enr, "is_active", False) and not getattr(existing, "is_active", False):
                student_enr[sid] = enr

        group_expected = 0
        group_students = 0

        today = timezone.localdate()

        for student_id, enrollment in student_enr.items():
            # O'quvchi shu oyda guruhda bo'lganligini tekshirish
            periods = history_lookup.get(group.id, {}).get(student_id, [])
            if periods:
                active_in_month = any(
                    start <= month_end and (end or today) >= month_start
                    for start, end in periods
                )
                if not active_in_month:
                    continue
            else:
                # History yo'q: enrollment sanasiga qarab filtrlaymiz
                created_at = getattr(enrollment, "created_at", None)
                created_date = created_at.date() if created_at else None
                if created_date and created_date > month_end:
                    continue

            fa = full_course_amount(enrollment)
            if fa <= 0:
                continue

            # Foizni _build_dynamic_teacher_salary kabi aniqlaymiz
            eff_pct = teacher_percent
            if eff_pct <= 0:
                eff_pct = int(getattr(enrollment, "oqituvchi_foiz", 0) or 0)
            if eff_pct <= 0:
                continue

            student_expected = fa * eff_pct // 100
            group_expected += student_expected
            group_students += 1

        if group_students <= 0:
            continue

        total_expected += group_expected
        total_active_students += group_students
        breakdown.append({
            "group_name": group.nom,
            "students": group_students,
            "group_total": group_expected,
            "avg_kurs_narxi": group_expected // group_students,
            "avg_percent": teacher_percent or 50,
            "avg_per_student": group_expected // group_students,
        })

    income_per_student = (
        total_expected / total_active_students if total_active_students > 0 else 0
    )

    # Joriy oy uchun snapshot yangilash
    if not course_id and (req_year == now.year and req_month == now.month):
        TeacherExpectedIncomeSnapshot.objects.update_or_create(
            teacher=teacher,
            year=req_year,
            month=req_month,
            center=center,
            defaults={
                "active_students": total_active_students,
                "expected_income": total_expected,
                "income_per_student": income_per_student,
            },
        )

    return {
        "teacher_id": teacher.id,
        "teacher_name": teacher.ism or teacher.email,
        "active_students": total_active_students,
        "income_per_student": income_per_student,
        "expected_income": int(total_expected),
        "breakdown": breakdown,
    }


def _empty_result(teacher) -> dict:
    return {
        "teacher_id": teacher.id,
        "teacher_name": teacher.ism or teacher.email,
        "active_students": 0,
        "income_per_student": 0,
        "expected_income": 0,
        "breakdown": [],
    }
