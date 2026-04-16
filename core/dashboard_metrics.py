from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Count, ExpressionWrapper, F, IntegerField, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from education.models import Attendance, Enrollment, Group, Payment, TuitionMonth
from education.services.tuition import ensure_tuition_month, tuition_month_fee_field


def month_start(day: date | None = None) -> date:
    current_day = day or timezone.localdate()
    return current_day.replace(day=1)


def month_end(day: date | None = None) -> date:
    start = month_start(day)
    next_month = (start + timedelta(days=32)).replace(day=1)
    return next_month - timedelta(days=1)


def attendance_present_filter() -> Q:
    return Q(status="present") | Q(present=True) | Q(forced=True)


def payments_for_center(center):
    return Payment.objects.filter(
        Q(center=center)
        | Q(center__isnull=True, group__center=center)
        | Q(center__isnull=True, student__center=center)
        | Q(center__isnull=True, enrollment__center=center)
    )


def active_groups_for_center(center):
    return Group.objects.filter(
        center=center,
        is_archived=False,
        is_deleted=False,
    )


def attendance_for_center(center):
    return Attendance.objects.filter(
        Q(center=center)
        | Q(center__isnull=True, group__center=center)
    )


def active_enrollments_for_center(center):
    return Enrollment.objects.filter(
        center=center,
        is_active=True,
        is_deleted=False,
        student__is_archived=False,
        group__is_archived=False,
    )


def tuition_months_for_center(center, target_month: date | None = None):
    current_month = month_start(target_month)
    fee_field = tuition_month_fee_field()
    paid_expr = Coalesce(
        Sum("allocations__amount", filter=Q(allocations__is_deleted=False)),
        0,
    )

    return (
        TuitionMonth.objects.filter(
            month=current_month,
            is_deleted=False,
            enrollment__is_active=True,
            enrollment__is_deleted=False,
            enrollment__student__is_archived=False,
            enrollment__group__is_archived=False,
        )
        .filter(
            Q(center=center)
            | Q(center__isnull=True, enrollment__center=center)
            | Q(center__isnull=True, enrollment__group__center=center)
        )
        .annotate(
            paid_amount=paid_expr,
            debt_amount=ExpressionWrapper(
                F(fee_field) - paid_expr,
                output_field=IntegerField(),
            ),
        )
    )


def month_debtors_qs(center, target_month: date | None = None):
    return tuition_months_for_center(center, target_month).filter(debt_amount__gt=0)


def month_zero_payment_qs(center, target_month: date | None = None):
    return tuition_months_for_center(center, target_month).filter(
        paid_amount__lte=0,
        debt_amount__gt=0,
    )


def get_center_today_income(center, target_day: date | None = None) -> int:
    today = target_day or timezone.localdate()
    return int(
        payments_for_center(center)
        .filter(paid_date=today)
        .aggregate(s=Sum("summa"))["s"]
        or 0
    )


def get_center_month_income(center, target_month: date | None = None) -> int:
    start = month_start(target_month)
    end = month_end(start)
    return int(
        payments_for_center(center)
        .filter(paid_date__range=(start, end))
        .aggregate(s=Sum("summa"))["s"]
        or 0
    )


def get_center_debtors_count(center, target_month: date | None = None) -> int:
    return month_debtors_qs(center, target_month).count()


def get_center_zero_payment_count(center, target_month: date | None = None) -> int:
    return month_zero_payment_qs(center, target_month).count()


def get_center_active_groups_count(center) -> int:
    return active_groups_for_center(center).count()


def get_center_attendance_snapshot(center, target_day: date | None = None) -> dict[str, int | str]:
    today = target_day or timezone.localdate()
    att_qs = attendance_for_center(center).filter(date=today)
    total_att = att_qs.count()
    present_att = att_qs.filter(attendance_present_filter()).count()
    attendance_pct = round(present_att * 100 / total_att) if total_att else 0
    return {
        "total": total_att,
        "present": present_att,
        "pct": attendance_pct,
        "label": f"{present_att}/{total_att}",
    }


def get_enrollment_month_debt(enrollment, target_month: date | None = None) -> int:
    current_month = month_start(target_month)
    tm = (
        TuitionMonth.objects.filter(
            enrollment=enrollment,
            month=current_month,
            is_deleted=False,
        ).first()
    )
    if not tm:
        tm = ensure_tuition_month(enrollment, current_month)
    fee_field = tuition_month_fee_field()
    fee = int(getattr(tm, fee_field, 0) or 0)
    paid = int(
        tm.allocations.filter(is_deleted=False).aggregate(s=Sum("amount"))["s"]
        or 0
    )
    return max(fee - paid, 0)


def get_center_capacity_alert_rows(center):
    rows = []
    groups = active_groups_for_center(center).annotate(
        active_students=Count(
            "enrollments",
            filter=Q(
                enrollments__is_active=True,
                enrollments__is_deleted=False,
            ),
            distinct=True,
        )
    )
    for group in groups:
        capacity = int(getattr(group, "max_students", 0) or 0)
        if capacity <= 0:
            continue
        active_students = int(group.active_students or 0)
        fill_pct = round(active_students * 100 / capacity, 1) if capacity else 0
        if fill_pct >= 80:
            rows.append(
                {
                    "group": group,
                    "active_students": active_students,
                    "capacity": capacity,
                    "fill_pct": fill_pct,
                }
            )
    rows.sort(key=lambda row: (-row["fill_pct"], -row["active_students"], row["group"].nom))
    return rows
