from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.db.models import F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from education.models import Enrollment, Payment, PaymentAllocation, TuitionMonth
from education.services.tuition import parse_month_str, tuition_month_fee_field


@dataclass
class CenterResetSummary:
    active_enrollment_count: int
    payment_count: int
    allocation_count: int
    tuition_month_count: int
    target_month_tuition_count: int
    payment_sum: int
    expected_total_debt: int
    zero_fee_enrollments: list[dict]


@dataclass
class CenterResetVerification:
    remaining_payments: int
    remaining_allocations: int
    target_month_tuition_count: int
    debtor_count: int
    total_debt: int
    active_enrollment_count: int
    expected_total_debt: int


def parse_target_month(month_str: str) -> date:
    parsed = parse_month_str(month_str)
    if not parsed:
        raise ValueError(f"Noto'g'ri oy formati: {month_str!r}. YYYY-MM ko'rinishida yozing.")
    return parsed


def _center_enrollments(center, *, active_only: bool):
    qs = Enrollment.objects.filter(
        is_deleted=False,
    ).filter(
        Q(center=center) | Q(center__isnull=True, group__center=center)
    )
    if active_only:
        qs = qs.filter(
            is_active=True,
            student__is_archived=False,
            group__is_archived=False,
        )
    return qs.select_related("student", "group")


def _payments_for_center(center):
    return Payment.objects.filter(
        Q(center=center)
        | Q(center__isnull=True, group__center=center)
        | Q(center__isnull=True, student__center=center)
        | Q(center__isnull=True, enrollment__center=center)
        | Q(center__isnull=True, enrollment__center__isnull=True, enrollment__group__center=center)
    )


def _allocations_for_center(center):
    return PaymentAllocation.objects.filter(
        Q(center=center)
        | Q(center__isnull=True, payment__center=center)
        | Q(center__isnull=True, payment__center__isnull=True, payment__group__center=center)
        | Q(center__isnull=True, payment__center__isnull=True, payment__student__center=center)
        | Q(center__isnull=True, payment__center__isnull=True, payment__enrollment__center=center)
        | Q(center__isnull=True, tuition_month__center=center)
        | Q(center__isnull=True, tuition_month__center__isnull=True, tuition_month__enrollment__center=center)
        | Q(center__isnull=True, tuition_month__center__isnull=True, tuition_month__enrollment__center__isnull=True, tuition_month__enrollment__group__center=center)
    )


def _tuition_months_for_center(center):
    return TuitionMonth.objects.filter(
        Q(center=center)
        | Q(center__isnull=True, enrollment__center=center)
        | Q(center__isnull=True, enrollment__center__isnull=True, enrollment__group__center=center)
    )


def _resolve_fee_amount(enrollment) -> int:
    if enrollment.student_payable_amount not in (None, "", 0):
        return int(enrollment.student_payable_amount)
    if getattr(enrollment, "kurs_narhi", None):
        return int(enrollment.kurs_narhi or 0)
    group = getattr(enrollment, "group", None)
    if group:
        return int(getattr(group, "kurs_narxi", 0) or getattr(group, "kurs_narhi", 0) or 0)
    return 0


def collect_center_reset_summary(center, target_month: date) -> CenterResetSummary:
    active_enrollments = list(_center_enrollments(center, active_only=True))
    payments_qs = _payments_for_center(center)
    allocations_qs = _allocations_for_center(center)
    tuition_qs = _tuition_months_for_center(center)

    zero_fee_enrollments = []
    expected_total_debt = 0
    for enrollment in active_enrollments:
        fee = _resolve_fee_amount(enrollment)
        if fee <= 0:
            zero_fee_enrollments.append(
                {
                    "enrollment_id": enrollment.id,
                    "student": enrollment.student.get_full_name(),
                    "group": enrollment.group.nom,
                }
            )
        expected_total_debt += fee

    return CenterResetSummary(
        active_enrollment_count=len(active_enrollments),
        payment_count=payments_qs.count(),
        allocation_count=allocations_qs.count(),
        tuition_month_count=tuition_qs.count(),
        target_month_tuition_count=tuition_qs.filter(month=target_month).count(),
        payment_sum=int(payments_qs.aggregate(s=Sum("summa"))["s"] or 0),
        expected_total_debt=expected_total_debt,
        zero_fee_enrollments=zero_fee_enrollments,
    )


def _upsert_target_month_for_enrollment(*, center, enrollment, target_month: date, fee: int, now):
    tm = TuitionMonth.all_objects.filter(enrollment=enrollment, month=target_month).first()
    fee_field = tuition_month_fee_field()

    if tm:
        tm.center = center
        setattr(tm, fee_field, int(fee))
        tm.is_deleted = False
        tm.deleted_at = None
        tm.deleted_by = None
        tm.deleted_reason = ""
        tm.restored_at = now
        tm.save(
            update_fields=[
                "center",
                fee_field,
                "is_deleted",
                "deleted_at",
                "deleted_by",
                "deleted_reason",
                "restored_at",
            ]
        )
        return "restored"

    TuitionMonth.objects.create(
        center=center,
        enrollment=enrollment,
        month=target_month,
        **{fee_field: int(fee)},
    )
    return "created"


@transaction.atomic
def reset_center_to_single_month_debt(center, target_month: date) -> dict:
    summary = collect_center_reset_summary(center, target_month)
    if summary.active_enrollment_count <= 0:
        return {
            "summary": summary,
            "payments_deleted": 0,
            "allocations_deleted": 0,
            "tuition_months_deleted": 0,
            "target_month_created": 0,
            "target_month_restored": 0,
            "target_month_updated": 0,
        }

    if summary.zero_fee_enrollments:
        names = ", ".join(
            f"#{row['enrollment_id']} {row['student']} [{row['group']}]"
            for row in summary.zero_fee_enrollments[:10]
        )
        raise ValueError(
            "Quyidagi enrollmentlarda fee 0 bo'lib qoldi; ularni debtor qilib bo'lmaydi: "
            + names
        )

    now = timezone.now()

    allocations_deleted = _allocations_for_center(center).update(
        is_deleted=True,
        deleted_at=now,
        deleted_reason=f"reset_center_to_single_month_debt:{target_month.isoformat()}",
    )
    payments_deleted = _payments_for_center(center).update(
        is_deleted=True,
        deleted_at=now,
        deleted_reason=f"reset_center_to_single_month_debt:{target_month.isoformat()}",
    )
    tuition_months_deleted = _tuition_months_for_center(center).update(
        is_deleted=True,
        deleted_at=now,
        deleted_reason=f"reset_center_to_single_month_debt:{target_month.isoformat()}",
    )
    _center_enrollments(center, active_only=False).update(jami_tolangan=0)

    target_month_created = 0
    target_month_restored = 0
    target_month_updated = 0
    for enrollment in _center_enrollments(center, active_only=True):
        fee = _resolve_fee_amount(enrollment)
        action = _upsert_target_month_for_enrollment(
            center=center,
            enrollment=enrollment,
            target_month=target_month,
            fee=fee,
            now=now,
        )
        if action == "created":
            target_month_created += 1
        else:
            target_month_restored += 1
            target_month_updated += 1

    return {
        "summary": summary,
        "payments_deleted": payments_deleted,
        "allocations_deleted": allocations_deleted,
        "tuition_months_deleted": tuition_months_deleted,
        "target_month_created": target_month_created,
        "target_month_restored": target_month_restored,
        "target_month_updated": target_month_updated,
    }


def verify_center_single_month_debt(center, target_month: date) -> CenterResetVerification:
    active_enrollments = _center_enrollments(center, active_only=True)
    active_enrollment_count = active_enrollments.count()
    fee_field = tuition_month_fee_field()

    fee_sub = (
        TuitionMonth.objects.filter(
            enrollment=OuterRef("pk"),
            month=target_month,
        )
        .values("enrollment")
        .annotate(s=Sum(fee_field))
        .values("s")
    )
    paid_sub = (
        PaymentAllocation.objects.filter(
            tuition_month__enrollment=OuterRef("pk"),
            tuition_month__month=target_month,
        )
        .values("tuition_month__enrollment")
        .annotate(s=Sum("amount"))
        .values("s")
    )
    debtor_qs = (
        active_enrollments.annotate(
            f=Coalesce(Subquery(fee_sub), 0),
            p=Coalesce(Subquery(paid_sub), 0),
        )
        .annotate(d=F("f") - F("p"))
        .filter(d__gt=0)
    )
    expected_total_debt = sum(_resolve_fee_amount(enrollment) for enrollment in active_enrollments)
    return CenterResetVerification(
        remaining_payments=_payments_for_center(center).count(),
        remaining_allocations=_allocations_for_center(center).count(),
        target_month_tuition_count=_tuition_months_for_center(center).filter(month=target_month).count(),
        debtor_count=debtor_qs.count(),
        total_debt=int(debtor_qs.aggregate(s=Sum("d"))["s"] or 0),
        active_enrollment_count=active_enrollment_count,
        expected_total_debt=expected_total_debt,
    )
