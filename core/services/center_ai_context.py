from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import re

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accounts.models import Center, User
from core.services.center_ai_security import privacy_mode_label, visible_phone
from education.models import Attendance, Enrollment, Group, Payment, PaymentAllocation, TeacherIncome, TuitionMonth
from store.models import Expense, Lead, Product, PurchaseRequest, Sale, TrialLesson

RISK_DEBT_THRESHOLD = 200_000
LOW_GROUP_STUDENT_THRESHOLD = 3


def _coerce_date(value):
    if isinstance(value, date):
        return value
    if not value:
        return None
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _period(date_from=None, date_to=None) -> tuple[date, date]:
    """
    Sana berilmasa avtomatik joriy oy oralig'ini qaytaradi.
    """
    today = timezone.localdate()
    start = _coerce_date(date_from)
    end = _coerce_date(date_to)

    if start and not end:
        end = start
    if end and not start:
        start = end

    if not start and not end:
        start = today.replace(day=1)
        end = today

    if start and end and start > end:
        start, end = end, start

    return start, end


def _month_start(day: date) -> date:
    return day.replace(day=1)


def _shift_month(day: date, delta: int) -> date:
    month_index = (day.year * 12 + day.month - 1) + delta
    year, month_index = divmod(month_index, 12)
    return date(year, month_index + 1, 1)


def _month_end(day: date) -> date:
    return _shift_month(_month_start(day), 1) - timedelta(days=1)


def _safe_sum(qs, field: str) -> int:
    return int(qs.aggregate(total=Sum(field)).get("total") or 0)


def _user_phone(user: User, viewer=None) -> str:
    return (
        visible_phone(
            (
                user.telefon1
                or user.phone_number
                or user.telefon2
                or ""
            ).strip(),
            viewer,
        )
    ).strip()


def _full_name(obj) -> str:
    full_name = getattr(obj, "full_name", None)
    if callable(full_name):
        return full_name()
    if isinstance(full_name, str) and full_name.strip():
        return full_name.strip()
    return " ".join(
        part
        for part in [
            getattr(obj, "ism", ""),
            getattr(obj, "familya", ""),
            getattr(obj, "otchestvo", ""),
        ]
        if part
    ).strip()


def _center_or_none(center_id: int | None) -> Center | None:
    if not center_id:
        return None
    return Center.objects.filter(id=center_id, is_deleted=False).only("id", "name", "slug", "plan").first()


def _student_search_q(query: str) -> Q:
    query = str(query or "").strip()
    phone_digits = re.sub(r"\D+", "", query)
    if len(phone_digits) >= 4:
        return (
            Q(telefon1__icontains=query)
            | Q(telefon2__icontains=query)
            | Q(phone_number__icontains=query)
        )

    tokens = [token for token in re.split(r"\s+", query) if token]
    if not tokens:
        return Q(pk__isnull=True)

    combined = Q()
    for token in tokens:
        combined &= (
            Q(ism__icontains=token)
            | Q(familya__icontains=token)
            | Q(otchestvo__icontains=token)
        )
    return combined


def _teacher_search_q(query: str) -> Q:
    query = str(query or "").strip()
    phone_digits = re.sub(r"\D+", "", query)
    if len(phone_digits) >= 4:
        return (
            Q(telefon1__icontains=query)
            | Q(telefon2__icontains=query)
            | Q(phone_number__icontains=query)
        )

    tokens = [token for token in re.split(r"\s+", query) if token]
    if not tokens:
        return Q(pk__isnull=True)

    combined = Q()
    for token in tokens:
        combined &= (
            Q(ism__icontains=token)
            | Q(familya__icontains=token)
            | Q(otchestvo__icontains=token)
        )
    return combined


def _student_debt_snapshot(center: Center, student_ids: list[int], *, as_of: date | None = None) -> tuple[dict[int, int], dict[int, int]]:
    if not student_ids:
        return {}, {}

    as_of = as_of or timezone.localdate()
    month_cap = _month_start(as_of)
    enrollments = list(
        Enrollment.objects.filter(center=center, student_id__in=student_ids)
        .values("id", "student_id", "kurs_narhi")
    )
    if not enrollments:
        return {}, {}

    enrollment_ids = [row["id"] for row in enrollments]
    enrollment_student = {row["id"]: row["student_id"] for row in enrollments}
    enrollment_fee = {row["id"]: int(row["kurs_narhi"] or 0) for row in enrollments}

    tuition_rows = list(
        TuitionMonth.objects.filter(center=center, enrollment_id__in=enrollment_ids, month__lte=month_cap)
        .values("id", "enrollment_id", "fee_amount")
    )

    tuition_ids = [row["id"] for row in tuition_rows]
    allocation_map = {}
    if tuition_ids:
        allocation_map = {
            row["tuition_month_id"]: int(row["total"] or 0)
            for row in (
                PaymentAllocation.objects.filter(
                    center=center,
                    tuition_month_id__in=tuition_ids,
                    payment__paid_date__lte=as_of,
                )
                .values("tuition_month_id")
                .annotate(total=Sum("amount"))
            )
        }

    debt_map: dict[int, int] = defaultdict(int)
    overdue_map: dict[int, int] = defaultdict(int)
    covered_enrollments: set[int] = set()

    for row in tuition_rows:
        covered_enrollments.add(row["enrollment_id"])
        fee_amount = int(row["fee_amount"] or 0)
        paid_amount = int(allocation_map.get(row["id"]) or 0)
        debt_amount = max(fee_amount - paid_amount, 0)
        if debt_amount <= 0:
            continue
        student_id = enrollment_student.get(row["enrollment_id"])
        if not student_id:
            continue
        debt_map[student_id] += debt_amount
        overdue_map[student_id] += 1

    fallback_enrollment_ids = [enrollment_id for enrollment_id in enrollment_ids if enrollment_id not in covered_enrollments]
    if fallback_enrollment_ids:
        fallback_payments = {
            row["enrollment_id"]: int(row["total"] or 0)
            for row in (
                Payment.objects.filter(center=center, enrollment_id__in=fallback_enrollment_ids, paid_date__lte=as_of)
                .values("enrollment_id")
                .annotate(total=Sum("summa"))
            )
        }
        for enrollment_id in fallback_enrollment_ids:
            fee_amount = int(enrollment_fee.get(enrollment_id) or 0)
            debt_amount = max(fee_amount - int(fallback_payments.get(enrollment_id) or 0), 0)
            if debt_amount <= 0:
                continue
            student_id = enrollment_student.get(enrollment_id)
            if not student_id:
                continue
            debt_map[student_id] += debt_amount
            overdue_map[student_id] += 1

    return dict(debt_map), dict(overdue_map)


def _student_profile_items(
    center: Center,
    student_ids: list[int],
    *,
    viewer=None,
    attendance_start: date | None = None,
    attendance_end: date | None = None,
    as_of: date | None = None,
) -> list[dict]:
    if not student_ids:
        return []

    students = list(
        User.objects.filter(center=center, role="student", is_archived=False, id__in=student_ids)
        .only("id", "ism", "familya", "otchestvo", "telefon1", "telefon2", "phone_number", "chaqmoq")
        .order_by("ism", "familya", "id")
    )
    if not students:
        return []

    student_order = {student_id: index for index, student_id in enumerate(student_ids)}
    students.sort(key=lambda student: student_order.get(student.id, 999999))

    student_ids = [student.id for student in students]
    as_of = as_of or timezone.localdate()
    attendance_start = attendance_start or (as_of - timedelta(days=29))
    attendance_end = attendance_end or as_of

    active_enrollments = list(
        Enrollment.objects.filter(center=center, student_id__in=student_ids, is_active=True)
        .select_related("group__oqituvchi")
        .order_by("group__nom", "id")
    )

    course_map: dict[int, list[str]] = defaultdict(list)
    teacher_map: dict[int, list[str]] = defaultdict(list)
    monthly_fee_map: dict[int, int] = defaultdict(int)
    for enrollment in active_enrollments:
        if enrollment.group_id and enrollment.group:
            if enrollment.group.nom not in course_map[enrollment.student_id]:
                course_map[enrollment.student_id].append(enrollment.group.nom)
            teacher_name = _full_name(enrollment.group.oqituvchi) if enrollment.group.oqituvchi_id else ""
            if teacher_name and teacher_name not in teacher_map[enrollment.student_id]:
                teacher_map[enrollment.student_id].append(teacher_name)
        monthly_fee_map[enrollment.student_id] += int(enrollment.kurs_narhi or 0)

    payment_map = {
        row["student_id"]: int(row["total"] or 0)
        for row in (
            Payment.objects.filter(center=center, student_id__in=student_ids)
            .values("student_id")
            .annotate(total=Sum("summa"))
        )
    }

    period_payment_map = {
        row["student_id"]: int(row["total"] or 0)
        for row in (
            Payment.objects.filter(center=center, student_id__in=student_ids, paid_date__range=(attendance_start, attendance_end))
            .values("student_id")
            .annotate(total=Sum("summa"))
        )
    }

    debt_map, overdue_map = _student_debt_snapshot(center, student_ids, as_of=as_of)

    attendance_raw = {
        row["student_id"]: {
            "present": int(row["present"] or 0),
            "total": int(row["total"] or 0),
        }
        for row in (
            Attendance.objects.filter(center=center, student_id__in=student_ids, date__range=(attendance_start, attendance_end))
            .values("student_id")
            .annotate(
                present=Count("id", filter=Q(status="present") | Q(present=True) | Q(forced=True)),
                total=Count("id"),
            )
        )
    }

    items = []
    for student in students:
        attendance = attendance_raw.get(student.id, {"present": 0, "total": 0})
        total_lessons = int(attendance["total"] or 0)
        present_lessons = int(attendance["present"] or 0)
        absent_lessons = max(total_lessons - present_lessons, 0)
        attendance_rate = round((present_lessons / total_lessons) * 100, 1) if total_lessons else 0.0
        courses = course_map.get(student.id, [])
        teachers = teacher_map.get(student.id, [])
        items.append(
            {
                "id": student.id,
                "full_name": _full_name(student),
                "phone": _user_phone(student, viewer),
                "course": ", ".join(courses) if courses else "",
                "courses": courses,
                "teacher_name": ", ".join(teachers) if teachers else "",
                "teachers": teachers,
                "total_payment": int(payment_map.get(student.id) or 0),
                "paid_in_period": int(period_payment_map.get(student.id) or 0),
                "debt": int(debt_map.get(student.id) or 0),
                "overdue_months": int(overdue_map.get(student.id) or 0),
                "monthly_fee": int(monthly_fee_map.get(student.id) or 0),
                "status": "active" if courses else "inactive",
                "status_label": "Faol" if courses else "Nofaol",
                "attendance_present": present_lessons,
                "attendance_absent": absent_lessons,
                "attendance_rate": attendance_rate,
                "attendance": {
                    "present": present_lessons,
                    "absent": absent_lessons,
                    "rate": attendance_rate,
                    "date_from": attendance_start.isoformat(),
                    "date_to": attendance_end.isoformat(),
                },
                "chaqmoq": int(student.chaqmoq or 0),
                "groups_count": len(courses),
            }
        )
    return items


def _teacher_profile_items(center: Center, teacher_ids: list[int], *, viewer=None) -> list[dict]:
    if not teacher_ids:
        return []

    teachers = list(
        User.objects.filter(center=center, role="teacher", is_archived=False, id__in=teacher_ids)
        .only("id", "ism", "familya", "otchestvo", "telefon1", "telefon2", "phone_number", "oqituvchi_foizi")
        .order_by("ism", "familya", "id")
    )
    if not teachers:
        return []

    teacher_order = {teacher_id: index for index, teacher_id in enumerate(teacher_ids)}
    teachers.sort(key=lambda teacher: teacher_order.get(teacher.id, 999999))
    teacher_ids = [teacher.id for teacher in teachers]

    groups = list(
        Group.objects.filter(center=center, oqituvchi_id__in=teacher_ids, is_archived=False)
        .only("id", "oqituvchi_id", "nom", "is_closed")
        .order_by("nom", "id")
    )
    group_ids = [group.id for group in groups]

    group_names: dict[int, list[str]] = defaultdict(list)
    groups_count: dict[int, int] = defaultdict(int)
    active_groups_count: dict[int, int] = defaultdict(int)
    for group in groups:
        group_names[group.oqituvchi_id].append(group.nom)
        groups_count[group.oqituvchi_id] += 1
        if not group.is_closed:
            active_groups_count[group.oqituvchi_id] += 1

    student_counts = {
        row["group__oqituvchi_id"]: int(row["students"] or 0)
        for row in (
            Enrollment.objects.filter(center=center, is_active=True, group__oqituvchi_id__in=teacher_ids)
            .values("group__oqituvchi_id")
            .annotate(students=Count("student_id", distinct=True))
        )
    }

    revenue_map = {
        row["group__oqituvchi_id"]: int(row["total"] or 0)
        for row in (
            Payment.objects.filter(center=center, group__oqituvchi_id__in=teacher_ids)
            .values("group__oqituvchi_id")
            .annotate(total=Sum("summa"))
        )
    }

    payout_map = {
        row["teacher_id"]: int(row["total"] or 0)
        for row in (
            TeacherIncome.objects.filter(center=center, teacher_id__in=teacher_ids)
            .values("teacher_id")
            .annotate(total=Sum("amount"))
        )
    }

    items = []
    for teacher in teachers:
        groups_total = int(groups_count.get(teacher.id) or 0)
        active_groups = int(active_groups_count.get(teacher.id) or 0)
        items.append(
            {
                "id": teacher.id,
                "teacher_name": _full_name(teacher),
                "phone": _user_phone(teacher, viewer),
                "groups_count": groups_total,
                "active_groups": active_groups,
                "students_count": int(student_counts.get(teacher.id) or 0),
                "total_income": int(revenue_map.get(teacher.id) or 0),
                "teacher_payout": int(payout_map.get(teacher.id) or 0),
                "status": "active" if active_groups > 0 else "inactive",
                "status_label": "Faol" if active_groups > 0 else "Nofaol",
                "group_names": group_names.get(teacher.id, []),
                "share_percent": int(teacher.oqituvchi_foizi or 0),
            }
        )
    return items


def _center_month_revenue(center: Center, start: date, end: date) -> int:
    return _safe_sum(Payment.objects.filter(center=center, paid_date__range=(start, end)), "summa")


def _center_month_attendance_rate(center: Center, start: date, end: date) -> float:
    summary = (
        Attendance.objects.filter(center=center, date__range=(start, end))
        .aggregate(
            present=Count("id", filter=Q(status="present") | Q(present=True) | Q(forced=True)),
            total=Count("id"),
        )
    )
    total = int(summary.get("total") or 0)
    present = int(summary.get("present") or 0)
    return round((present / total) * 100, 1) if total else 0.0


def _center_total_debt(center: Center, *, as_of: date | None = None) -> int:
    student_ids = list(
        Enrollment.objects.filter(center=center, is_active=True)
        .values_list("student_id", flat=True)
        .distinct()
    )
    debt_map, _ = _student_debt_snapshot(center, student_ids, as_of=as_of)
    return int(sum(debt_map.values()))


def get_student_full_info(center_id, query, *, viewer=None, limit: int = 10, as_of: date | None = None) -> dict:
    center = _center_or_none(center_id)
    query = str(query or "").strip()
    if not center or not query:
        return {"query": query, "count": 0, "items": []}

    students = list(
        User.objects.filter(center=center, role="student", is_archived=False)
        .filter(_student_search_q(query))
        .only("id", "ism", "familya", "otchestvo", "telefon1", "telefon2", "phone_number", "chaqmoq")
        .order_by("ism", "familya", "id")[:limit]
    )
    items = _student_profile_items(center, [student.id for student in students], viewer=viewer, as_of=as_of)
    return {
        "query": query,
        "count": len(items),
        "items": items,
    }


def get_teacher_full_info(center_id, query, *, viewer=None, limit: int = 10) -> dict:
    center = _center_or_none(center_id)
    query = str(query or "").strip()
    if not center or not query:
        return {"query": query, "count": 0, "items": []}

    teachers = list(
        User.objects.filter(center=center, role="teacher", is_archived=False)
        .filter(_teacher_search_q(query))
        .only("id", "ism", "familya", "otchestvo", "telefon1", "telefon2", "phone_number", "oqituvchi_foizi")
        .order_by("ism", "familya", "id")[:limit]
    )
    items = _teacher_profile_items(center, [teacher.id for teacher in teachers], viewer=viewer)
    return {
        "query": query,
        "count": len(items),
        "items": items,
    }


def _growth_percentage(current: int, previous: int) -> float:
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


def get_monthly_stats(center_id, *, as_of: date | None = None) -> dict:
    center = _center_or_none(center_id)
    if not center:
        return {
            "this_month_students": 0,
            "last_month_students": 0,
            "growth_percentage": 0.0,
        }

    as_of = as_of or timezone.localdate()
    this_month_start = _month_start(as_of)
    this_month_end = as_of
    last_month_start = _shift_month(this_month_start, -1)
    last_month_end = this_month_start - timedelta(days=1)

    student_qs = User.objects.filter(center=center, role="student", is_archived=False)
    this_month_students = student_qs.filter(date_joined__date__range=(this_month_start, this_month_end)).count()
    last_month_students = student_qs.filter(date_joined__date__range=(last_month_start, last_month_end)).count()
    growth_percentage = _growth_percentage(this_month_students, last_month_students)

    return {
        "this_month_students": int(this_month_students),
        "last_month_students": int(last_month_students),
        "growth_percentage": growth_percentage,
        "this_month_label": this_month_start.strftime("%Y-%m"),
        "last_month_label": last_month_start.strftime("%Y-%m"),
    }


def generate_center_alerts(center_id, *, as_of: date | None = None) -> list[dict]:
    center = _center_or_none(center_id)
    if not center:
        return []

    as_of = as_of or timezone.localdate()
    this_month_start = _month_start(as_of)
    last_month_start = _shift_month(this_month_start, -1)
    last_month_end = this_month_start - timedelta(days=1)

    alerts: list[dict] = []

    current_debt = _center_total_debt(center, as_of=as_of)
    previous_debt = _center_total_debt(center, as_of=last_month_end)
    if current_debt > previous_debt:
        alerts.append(
            {
                "type": "warning",
                "message": f"Qarzdorlik oshgan: {_safe_money(current_debt)}. O'tgan oy yakunida {_safe_money(previous_debt)} edi.",
                "priority": "high",
                "code": "debt_increased",
                "current_value": current_debt,
                "previous_value": previous_debt,
            }
        )

    current_attendance = _center_month_attendance_rate(center, this_month_start, as_of)
    previous_attendance = _center_month_attendance_rate(center, last_month_start, last_month_end)
    if current_attendance < previous_attendance:
        alerts.append(
            {
                "type": "warning",
                "message": f"Davomat pasaygan: bu oy {current_attendance:.1f}%, o'tgan oy {previous_attendance:.1f}%.",
                "priority": "medium",
                "code": "attendance_dropped",
                "current_value": current_attendance,
                "previous_value": previous_attendance,
            }
        )

    monthly_stats = get_monthly_stats(center.id, as_of=as_of)
    if int(monthly_stats["this_month_students"]) < int(monthly_stats["last_month_students"]):
        alerts.append(
            {
                "type": "warning",
                "message": f"Yangi o'quvchilar oqimi kamaygan: bu oy {monthly_stats['this_month_students']} ta, o'tgan oy {monthly_stats['last_month_students']} ta.",
                "priority": "medium",
                "code": "students_decreased",
                "current_value": int(monthly_stats["this_month_students"]),
                "previous_value": int(monthly_stats["last_month_students"]),
            }
        )

    current_revenue = _center_month_revenue(center, this_month_start, as_of)
    previous_revenue = _center_month_revenue(center, last_month_start, last_month_end)
    if current_revenue < previous_revenue:
        alerts.append(
            {
                "type": "warning",
                "message": f"Daromad pasaygan: bu oy {_safe_money(current_revenue)}, o'tgan oy {_safe_money(previous_revenue)}.",
                "priority": "high",
                "code": "revenue_dropped",
                "current_value": current_revenue,
                "previous_value": previous_revenue,
            }
        )

    low_groups = list(
        Group.objects.filter(center=center, is_archived=False, is_closed=False)
        .annotate(
            active_students=Count(
                "enrollments__student_id",
                filter=Q(enrollments__is_active=True),
                distinct=True,
            )
        )
        .filter(active_students__lte=LOW_GROUP_STUDENT_THRESHOLD)
        .order_by("active_students", "nom")[:3]
    )
    for group in low_groups:
        alerts.append(
            {
                "type": "warning",
                "message": f"{group.nom} guruhi yopilish xavfida: faol o'quvchilar {int(group.active_students or 0)} ta.",
                "priority": "medium" if int(group.active_students or 0) > 1 else "high",
                "code": "group_at_risk",
                "group_id": group.id,
                "current_value": int(group.active_students or 0),
            }
        )

    return alerts


def _safe_money(value: int | float) -> str:
    amount = int(value or 0)
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:.1f} mlrd so'm"
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.1f} mln so'm"
    if amount >= 1_000:
        return f"{round(amount / 1_000)} ming so'm"
    return f"{amount} so'm"


def get_center_finance_context(center: Center, date_from=None, date_to=None) -> dict:
    start, end = _period(date_from, date_to)

    payments_qs = Payment.objects.filter(center=center, paid_date__range=(start, end))
    expenses_qs = Expense.objects.filter(center=center, sana__date__range=(start, end))
    teacher_income_qs = TeacherIncome.objects.filter(center=center, attendance__date__range=(start, end))

    revenue = _safe_sum(payments_qs, "summa")
    expenses_total = _safe_sum(expenses_qs, "summa")
    teacher_payout = _safe_sum(teacher_income_qs, "amount")
    profit = revenue - expenses_total - teacher_payout

    daily_revenue = [
        {
            "day": row["paid_date"].isoformat(),
            "amount": int(row["amount"] or 0),
        }
        for row in payments_qs.values("paid_date").annotate(amount=Sum("summa")).order_by("paid_date")
    ]

    monthly_revenue = [
        {
            "month": row["month"].date().isoformat() if hasattr(row["month"], "date") else row["month"].isoformat(),
            "amount": int(row["amount"] or 0),
        }
        for row in (
            Payment.objects.filter(
                center=center,
                paid_date__gte=end - timedelta(days=365),
                paid_date__lte=end,
            )
            .annotate(month=TruncMonth("paid_date"))
            .values("month")
            .annotate(amount=Sum("summa"))
            .order_by("month")
        )
    ]

    return {
        "period": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "summary": {
            "revenue": revenue,
            "expenses": expenses_total,
            "teacher_payout": teacher_payout,
            "profit": profit,
            "payments_count": payments_qs.count(),
            "expense_count": expenses_qs.count(),
        },
        "daily_revenue": daily_revenue,
        "monthly_revenue": monthly_revenue,
    }


def get_center_students_context(center: Center, query: str | None = None, *, viewer=None, limit: int = 20, date_from=None, date_to=None) -> dict:
    start, end = _period(date_from, date_to)
    students_qs = User.objects.filter(center=center, role="student", is_archived=False).order_by("ism", "familya", "id")
    if query:
        students_qs = students_qs.filter(_student_search_q(query))

    students = list(students_qs.only("id", "ism", "familya", "otchestvo", "telefon1", "telefon2", "phone_number", "chaqmoq")[:limit])
    items = _student_profile_items(
        center,
        [student.id for student in students],
        viewer=viewer,
        attendance_start=start,
        attendance_end=end,
        as_of=end,
    )

    top_student_ids = list(
        Payment.objects.filter(center=center)
        .values("student_id")
        .annotate(total=Sum("summa"))
        .order_by("-total", "student_id")
        .values_list("student_id", flat=True)[:5]
    )
    top_students = _student_profile_items(center, top_student_ids, viewer=viewer, attendance_start=start, attendance_end=end, as_of=end)

    risky_student_ids = []
    active_student_ids = list(
        Enrollment.objects.filter(center=center, is_active=True)
        .values_list("student_id", flat=True)
        .distinct()
    )
    debt_map, overdue_map = _student_debt_snapshot(center, active_student_ids, as_of=end)
    risky_ranked = sorted(
        [
            (student_id, int(debt_map.get(student_id) or 0), int(overdue_map.get(student_id) or 0))
            for student_id in active_student_ids
            if int(debt_map.get(student_id) or 0) >= RISK_DEBT_THRESHOLD or int(overdue_map.get(student_id) or 0) > 0
        ],
        key=lambda item: (-item[1], -item[2], item[0]),
    )
    risky_student_ids = [student_id for student_id, _, _ in risky_ranked[:5]]
    risky_students = _student_profile_items(center, risky_student_ids, viewer=viewer, attendance_start=start, attendance_end=end, as_of=end)

    return {
        "period": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "summary": {
            "total_students": User.objects.filter(center=center, role="student", is_archived=False).count(),
            "active_students": Enrollment.objects.filter(center=center, is_active=True).values("student_id").distinct().count(),
            "returned_count": len(items),
            "privacy_mode": privacy_mode_label(viewer),
        },
        "items": items,
        "top_students": top_students,
        "risky_students": risky_students,
    }


def get_center_teachers_context(center: Center, query: str | None = None, *, viewer=None, limit: int = 20, date_from=None, date_to=None) -> dict:
    teachers_qs = User.objects.filter(center=center, role="teacher", is_archived=False).order_by("ism", "familya", "id")
    if query:
        teachers_qs = teachers_qs.filter(_teacher_search_q(query))

    teachers = list(teachers_qs.only("id", "ism", "familya", "otchestvo", "telefon1", "telefon2", "phone_number", "oqituvchi_foizi")[:limit])
    items = _teacher_profile_items(center, [teacher.id for teacher in teachers], viewer=viewer)

    performance_teacher_ids = list(
        Payment.objects.filter(center=center, group__oqituvchi__role="teacher")
        .values("group__oqituvchi_id")
        .annotate(total=Sum("summa"))
        .order_by("-total", "group__oqituvchi_id")
        .values_list("group__oqituvchi_id", flat=True)[:5]
    )
    performance = _teacher_profile_items(center, performance_teacher_ids, viewer=viewer)

    return {
        "period": {"date_from": _period(date_from, date_to)[0].isoformat(), "date_to": _period(date_from, date_to)[1].isoformat()},
        "summary": {
            "total_teachers": User.objects.filter(center=center, role="teacher", is_archived=False).count(),
            "returned_count": len(items),
            "privacy_mode": privacy_mode_label(viewer),
        },
        "items": items,
        "performance": performance,
    }


def get_center_groups_context(center: Center, *, limit: int = 20, date_from=None, date_to=None) -> dict:
    start, end = _period(date_from, date_to)
    groups = list(
        Group.objects.filter(center=center, is_archived=False)
        .select_related("oqituvchi")
        .order_by("nom")[:limit]
    )
    group_ids = [group.id for group in groups]

    student_counts = {
        row["group_id"]: int(row["students"] or 0)
        for row in (
            Enrollment.objects.filter(center=center, is_active=True, group_id__in=group_ids)
            .values("group_id")
            .annotate(students=Count("student_id", distinct=True))
        )
    }

    payment_map = {
        row["group_id"]: int(row["total"] or 0)
        for row in (
            Payment.objects.filter(center=center, group_id__in=group_ids, paid_date__range=(start, end))
            .values("group_id")
            .annotate(total=Sum("summa"))
        )
    }

    attendance_map = {
        row["group_id"]: int(row["present"] or 0)
        for row in (
            Attendance.objects.filter(center=center, group_id__in=group_ids, date__range=(start, end))
            .values("group_id")
            .annotate(present=Count("id", filter=Q(status="present") | Q(present=True) | Q(forced=True)))
        )
    }

    items = []
    for group in groups:
        teacher_name = _full_name(group.oqituvchi) if group.oqituvchi_id and group.oqituvchi else ""
        items.append(
            {
                "id": group.id,
                "name": group.nom,
                "teacher": teacher_name,
                "course_price": int(group.kurs_narxi or 0),
                "teacher_share_percent": int(group.oqituvchi_foiz or 0),
                "students": student_counts.get(group.id, 0),
                "revenue_in_period": payment_map.get(group.id, 0),
                "attended_lessons_in_period": attendance_map.get(group.id, 0),
                "status": "active" if not group.is_closed else "inactive",
            }
        )

    return {
        "period": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "summary": {
            "total_groups": Group.objects.filter(center=center, is_archived=False).count(),
            "returned_count": len(items),
        },
        "items": items,
    }


def get_center_leads_context(center: Center, *, viewer=None, limit: int = 20, date_from=None, date_to=None) -> dict:
    start, end = _period(date_from, date_to)
    leads_qs = Lead.objects.filter(center=center, is_archived=False)
    period_qs = leads_qs.filter(qoshilgan_sana__date__range=(start, end))

    top_sources = [
        {"name": row["manba__nom"] or "Noma'lum", "count": int(row["count"] or 0)}
        for row in (
            period_qs.values("manba__nom")
            .annotate(count=Count("id"))
            .order_by("-count", "manba__nom")[:5]
        )
    ]

    top_directions = [
        {"name": row["yonalish__nom"] or "Noma'lum", "count": int(row["count"] or 0)}
        for row in (
            period_qs.values("yonalish__nom")
            .annotate(count=Count("id"))
            .order_by("-count", "yonalish__nom")[:5]
        )
    ]

    latest_items = []
    for lead in (
        period_qs.select_related("manba", "yonalish", "status", "assigned_manager")
        .order_by("-qoshilgan_sana")[:limit]
    ):
        latest_items.append(
            {
                "id": lead.id,
                "full_name": lead.full_name,
                "phone": visible_phone(lead.telefon1, viewer),
                "source": lead.manba.nom if lead.manba_id and lead.manba else "",
                "direction": lead.yonalish.nom if lead.yonalish_id and lead.yonalish else "",
                "status": lead.status.nom if lead.status_id and lead.status else "",
                "manager": _full_name(lead.assigned_manager) if lead.assigned_manager_id and lead.assigned_manager else "",
                "converted": bool(lead.converted_to_student),
                "created_at": lead.qoshilgan_sana.isoformat(),
            }
        )

    trial_count = TrialLesson.objects.filter(center=center, scheduled_at__date__range=(start, end)).count()

    return {
        "period": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "summary": {
            "total_leads": leads_qs.count(),
            "period_leads": period_qs.count(),
            "converted_in_period": period_qs.filter(converted_to_student=True).count(),
            "trial_lessons_in_period": trial_count,
            "privacy_mode": privacy_mode_label(viewer),
        },
        "top_sources": top_sources,
        "top_directions": top_directions,
        "items": latest_items,
    }


def get_center_store_context(center: Center, *, limit: int = 20, date_from=None, date_to=None) -> dict:
    start, end = _period(date_from, date_to)

    sales_qs = Sale.objects.filter(center=center, sana__date__range=(start, end))
    requests_qs = PurchaseRequest.objects.filter(center=center, sana__date__range=(start, end))

    top_products = [
        {
            "name": row["product__nom"] or "Noma'lum",
            "qty": int(row["qty"] or 0),
            "amount": int(row["amount"] or 0),
        }
        for row in (
            sales_qs.values("product__nom")
            .annotate(qty=Sum("qty"), amount=Sum("narx_som"))
            .order_by("-qty", "-amount")[:5]
        )
    ]

    latest_products = [
        {
            "id": product.id,
            "name": product.nom,
            "price_som": int(product.narx_som or 0),
            "price_chaqmoq": int(product.narx_chaqmoq or 0),
            "sold_count": int(product.sotilgan_soni or 0),
        }
        for product in Product.objects.filter(center=center).order_by("-yaratilgan")[:limit]
    ]

    return {
        "period": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "summary": {
            "products_count": Product.objects.filter(center=center).count(),
            "sales_count": sales_qs.count(),
            "sales_amount": _safe_sum(sales_qs, "narx_som"),
            "requests_count": requests_qs.count(),
            "pending_requests": requests_qs.filter(status=PurchaseRequest.PENDING).count(),
        },
        "top_products": top_products,
        "items": latest_products,
    }


def build_center_ai_context(
    center: Center,
    *,
    viewer=None,
    question: str = "",
    date_from=None,
    date_to=None,
    query: str | None = None,
    limit: int = 10,
) -> dict:
    """
    Tenant-safe context builder. Hech narsa qo'lda saqlamaydi,
    faqat joriy center uchun DB dan kerakli ma'lumotlarni yig'adi.
    """
    start, end = _period(date_from, date_to)

    students = get_center_students_context(center, query=query, viewer=viewer, limit=limit, date_from=start, date_to=end)
    teachers = get_center_teachers_context(center, query=query, viewer=viewer, limit=limit, date_from=start, date_to=end)
    monthly_stats = get_monthly_stats(center.id, as_of=end)
    alerts = generate_center_alerts(center.id, as_of=end)

    return {
        "center": {
            "id": center.id,
            "name": center.name,
            "slug": center.slug,
            "plan": center.plan,
        },
        "question": question.strip(),
        "privacy_mode": privacy_mode_label(viewer),
        "period": {"date_from": start.isoformat(), "date_to": end.isoformat()},
        "finance": get_center_finance_context(center, start, end),
        "students": students,
        "teachers": teachers,
        "groups": get_center_groups_context(center, limit=limit, date_from=start, date_to=end),
        "leads": get_center_leads_context(center, viewer=viewer, limit=limit, date_from=start, date_to=end),
        "store": get_center_store_context(center, limit=limit, date_from=start, date_to=end),
        "analytics": {
            "monthly_stats": monthly_stats,
            "teacher_performance": teachers.get("performance", []),
            "top_students": students.get("top_students", []),
            "risky_students": students.get("risky_students", []),
        },
        "alerts": alerts,
    }


def build_center_ai_prompt_context(
    center: Center,
    *,
    viewer=None,
    question: str = "",
    date_from=None,
    date_to=None,
    query: str | None = None,
    limit: int = 10,
) -> str:
    ctx = build_center_ai_context(
        center,
        viewer=viewer,
        question=question,
        date_from=date_from,
        date_to=date_to,
        query=query,
        limit=limit,
    )
    finance = ctx["finance"]["summary"]
    students = ctx["students"]["summary"]
    teachers = ctx["teachers"]["summary"]
    groups = ctx["groups"]["summary"]
    leads = ctx["leads"]["summary"]
    store = ctx["store"]["summary"]
    monthly = ctx["analytics"]["monthly_stats"]
    alerts = ctx["alerts"][:3]
    top_students = ctx["analytics"]["top_students"][:3]
    risky_students = ctx["analytics"]["risky_students"][:3]
    teacher_performance = ctx["analytics"]["teacher_performance"][:3]

    return "\n".join(
        [
            f"Markaz: {ctx['center']['name']} ({ctx['center']['slug']})",
            f"Center ID: {ctx['center']['id']}",
            f"Maxfiylik rejimi: {ctx['privacy_mode']}",
            f"Savol: {ctx['question'] or '—'}",
            f"Davr: {ctx['period']['date_from']} dan {ctx['period']['date_to']} gacha",
            f"Daromad: {finance['revenue']} so'm",
            f"Xarajat: {finance['expenses']} so'm",
            f"Ustoz ulushi: {finance['teacher_payout']} so'm",
            f"Foyda: {finance['profit']} so'm",
            f"Jami o'quvchi: {students['total_students']}",
            f"Faol o'quvchi: {students['active_students']}",
            f"Jami ustoz: {teachers['total_teachers']}",
            f"Jami guruh: {groups['total_groups']}",
            f"Jami lead: {leads['total_leads']}",
            f"Bu davr leadi: {leads['period_leads']}",
            f"Mahsulotlar: {store['products_count']}",
            f"Sotuvlar: {store['sales_count']}",
            f"So'rovlar: {store['requests_count']}",
            f"Bu oy yangi o'quvchi: {monthly['this_month_students']}",
            f"O'tgan oy yangi o'quvchi: {monthly['last_month_students']}",
            f"O'sish foizi: {monthly['growth_percentage']}",
            f"Top o'quvchilar: {', '.join(item['full_name'] for item in top_students) or 'yo‘q'}",
            f"Qarzdor o'quvchilar: {', '.join(item['full_name'] for item in risky_students) or 'yo‘q'}",
            f"Teacher performance: {', '.join(item['teacher_name'] for item in teacher_performance) or 'yo‘q'}",
            f"Alertlar: {' | '.join(alert['message'] for alert in alerts) or 'yo‘q'}",
        ]
    )
