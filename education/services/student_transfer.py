from __future__ import annotations

from datetime import date, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from education.models import (
    Attendance,
    Enrollment,
    PaymentAllocation,
    StudentGroupHistory,
    StudentGroupTransfer,
    TuitionMonth,
)
from education.services.enrollment_service import EnrollmentService
from education.services.tuition import (
    calculate_student_month_billing,
    effective_student_payable_amount,
    expected_lessons_in_period,
    full_course_amount,
    get_month_paid,
    month_first_day,
    month_last_day,
    tuition_month_fee,
    tuition_month_fee_field,
)


TRANSFER_ALLOWED_ROLES = {"admin", "director", "manager"}


def user_can_transfer_student(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and (getattr(user, "is_superuser", False) or getattr(user, "role", None) in TRANSFER_ALLOWED_ROLES)
    )


def _fee_for_period(enrollment: Enrollment, start: date, end: date) -> int:
    if start > end:
        return 0
    lesson_count = expected_lessons_in_period(enrollment, start, end)
    billing = calculate_student_month_billing(
        effective_student_payable_amount(enrollment),
        getattr(enrollment, "monthly_lessons", 0) or getattr(enrollment.group, "oy_dars_soni", 0) or 12,
        lesson_count,
        getattr(enrollment, "oqituvchi_foiz", 0) or 0,
    )
    return int(billing["student_debt"] or 0)


def _attendance_financials_for_period(enrollment: Enrollment, start: date, end: date) -> dict:
    if start > end:
        return {
            "billable_lessons": 0,
            "student_debt": 0,
            "teacher_share": 0,
            "center_share": 0,
            "turnover": 0,
        }

    billable_lessons = (
        Attendance.objects.filter(
            group=enrollment.group,
            student=enrollment.student,
            date__gte=start,
            date__lte=end,
        )
        .filter(
            Q(status="present")
            | Q(status="absent_unexcused")
            | Q(present=True)
            | Q(forced=True)
        )
        .count()
    )
    if billable_lessons <= 0:
        return {
            "billable_lessons": 0,
            "student_debt": 0,
            "teacher_share": 0,
            "center_share": 0,
            "turnover": 0,
        }

    monthly_lessons = (
        getattr(enrollment, "monthly_lessons", 0)
        or getattr(enrollment.group, "oy_dars_soni", 0)
        or 12
    )
    teacher_percent = getattr(enrollment, "oqituvchi_foiz", 0) or 0
    debt_billing = calculate_student_month_billing(
        effective_student_payable_amount(enrollment),
        monthly_lessons,
        billable_lessons,
        teacher_percent,
    )
    turnover_billing = calculate_student_month_billing(
        full_course_amount(enrollment),
        monthly_lessons,
        billable_lessons,
        teacher_percent,
    )
    return {
        "billable_lessons": int(billable_lessons),
        "student_debt": int(debt_billing["student_debt"] or 0),
        "teacher_share": int(turnover_billing["teacher_amount"] or 0),
        "center_share": int(turnover_billing["center_amount"] or 0),
        "turnover": int(turnover_billing["student_debt"] or 0),
    }


def _payment_state(enrollment: Enrollment, month: date) -> dict:
    tm = TuitionMonth.objects.filter(enrollment=enrollment, month=month).first()
    paid = get_month_paid(tm) if tm else 0
    return {
        "enrollment_id": enrollment.id,
        "group_id": enrollment.group_id,
        "month": month.isoformat(),
        "fee_amount": tuition_month_fee(tm) if tm else 0,
        "paid_amount": int(paid or 0),
        "debt_amount": max(0, (tuition_month_fee(tm) if tm else 0) - int(paid or 0)),
    }


def _attendance_summary(enrollment: Enrollment, start_date: date, end_date: date) -> dict:
    summary = {
        "group_id": enrollment.group_id,
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat() if start_date <= end_date else None,
        "total": 0,
        "present": 0,
        "absent_excused": 0,
        "absent_unexcused": 0,
    }
    if start_date > end_date:
        return summary

    qs = Attendance.objects.filter(
        group=enrollment.group,
        student=enrollment.student,
        date__gte=start_date,
        date__lte=end_date,
    )
    by_status = {
        row["status"]: row["count"]
        for row in qs.values("status").annotate(count=Count("id"))
    }
    summary.update({
        "total": qs.count(),
        "present": qs.filter(status="present").count(),
        "absent_excused": by_status.get("absent_excused", 0),
        "absent_unexcused": by_status.get("absent_unexcused", 0),
    })
    return summary


def _move_surplus_allocations(*, old_tm: TuitionMonth, new_tm: TuitionMonth) -> int:
    old_fee = tuition_month_fee(old_tm)
    old_paid = get_month_paid(old_tm)
    new_fee = tuition_month_fee(new_tm)
    new_paid = get_month_paid(new_tm)
    surplus = max(0, int(old_paid or 0) - int(old_fee or 0))
    need = max(0, int(new_fee or 0) - int(new_paid or 0))
    amount_to_move = min(surplus, need)
    if amount_to_move <= 0:
        return 0

    remaining = amount_to_move
    allocations = (
        PaymentAllocation.objects
        .select_for_update()
        .filter(tuition_month=old_tm, amount__gt=0)
        .select_related("payment")
        .order_by("-id")
    )
    for allocation in allocations:
        if remaining <= 0:
            break
        take = min(int(allocation.amount or 0), remaining)
        if take <= 0:
            continue
        allocation.amount = int(allocation.amount or 0) - take
        allocation.save(update_fields=["amount"])
        PaymentAllocation.objects.create(
            center=new_tm.center or old_tm.center,
            payment=allocation.payment,
            tuition_month=new_tm,
            amount=take,
        )
        remaining -= take

    PaymentAllocation.objects.filter(tuition_month=old_tm, amount=0).delete()
    return amount_to_move - remaining


@transaction.atomic
def transfer_student_to_group(student, old_group, new_group, transfer_date, reason, user):
    if not user_can_transfer_student(user):
        raise PermissionDenied("Sizda o'quvchini boshqa guruhga ko'chirish huquqi yo'q.")
    if not transfer_date:
        transfer_date = timezone.localdate()
    if old_group.pk == new_group.pk:
        raise ValidationError("Yangi guruh eski guruh bilan bir xil bo'lishi mumkin emas.")
    if old_group.center_id != new_group.center_id:
        raise ValidationError("Boshqa o'quv markaz guruhiga ko'chirish mumkin emas.")
    if getattr(student, "role", None) != "student" or not getattr(student, "is_active", True) or getattr(student, "is_archived", False):
        raise ValidationError("Faqat aktiv o'quvchini ko'chirish mumkin.")
    if student.center_id and student.center_id != old_group.center_id:
        raise ValidationError("O'quvchi boshqa o'quv markazga tegishli.")

    old_enrollment = (
        Enrollment.objects
        .select_for_update()
        .select_related("group", "student")
        .filter(student=student, group=old_group, center=old_group.center, is_active=True)
        .first()
    )
    if not old_enrollment:
        raise ValidationError("O'quvchi eski guruhning aktiv ro'yxatida topilmadi.")

    duplicate_active = Enrollment.objects.filter(
        student=student,
        group=new_group,
        center=new_group.center,
        is_active=True,
    ).exists()
    if duplicate_active:
        raise ValidationError("O'quvchi yangi guruhda allaqachon aktiv.")

    latest_transfer = StudentGroupTransfer.objects.filter(
        center=old_group.center,
        student=student,
        old_group=old_group,
        new_group=new_group,
        transfer_date=transfer_date,
    ).exists()
    if latest_transfer:
        raise ValidationError("Bu ko'chirish yozuvi allaqachon mavjud.")

    transfer_month = month_first_day(transfer_date)
    old_state_before = _payment_state(old_enrollment, transfer_month)

    month_start = transfer_month
    month_end = month_last_day(transfer_month)
    old_period_start = max(month_start, old_enrollment.joined_at or month_start)
    old_period_end = min(month_end, transfer_date - timedelta(days=1))
    old_period_financials = _attendance_financials_for_period(old_enrollment, old_period_start, old_period_end)
    old_fee = _fee_for_period(old_enrollment, old_period_start, old_period_end)
    if old_period_financials["billable_lessons"] <= 0:
        old_fee = 0
    else:
        old_period_financials["student_debt"] = int(old_fee or 0)
    attendance_state = _attendance_summary(old_enrollment, old_period_start, old_period_end)

    fee_field = tuition_month_fee_field()
    old_tm, _ = TuitionMonth.all_objects.get_or_create(
        enrollment=old_enrollment,
        month=transfer_month,
        defaults={"center": old_enrollment.center, fee_field: old_fee},
    )
    if old_tm.is_deleted:
        old_tm.restore()
    setattr(old_tm, fee_field, old_fee)
    if not old_tm.center_id:
        old_tm.center = old_enrollment.center
    old_tm.save(update_fields=[fee_field, "center"] if old_tm.center_id else [fee_field])

    old_enrollment.is_active = False
    old_enrollment.save(update_fields=["is_active"])
    StudentGroupHistory.objects.filter(
        student=student,
        group=old_group,
        end_date__isnull=True,
    ).update(end_date=transfer_date - timedelta(days=1))

    new_enrollment = EnrollmentService.enroll_student(
        student=student,
        group=new_group,
        kurs_narxi=full_course_amount(old_enrollment) or getattr(new_group, "kurs_narxi", 0) or 0,
        oqituvchi_foiz=getattr(new_group, "oqituvchi_foiz", None),
        student_payable_amount=(
            old_enrollment.student_payable_amount
            if old_enrollment.student_payable_amount is not None
            else None
        ),
        start_date=transfer_date,
        lesson_pattern=getattr(old_enrollment, "lesson_pattern", None),
        monthly_lessons=getattr(new_group, "oy_dars_soni", 0) or getattr(old_enrollment, "monthly_lessons", 0) or 12,
    )

    new_fee = _fee_for_period(new_enrollment, max(transfer_date, month_start), month_end)
    cap = max(effective_student_payable_amount(old_enrollment), effective_student_payable_amount(new_enrollment))
    if cap > 0 and old_fee + new_fee > cap:
        new_fee = max(0, cap - old_fee)

    new_tm, _ = TuitionMonth.all_objects.get_or_create(
        enrollment=new_enrollment,
        month=transfer_month,
        defaults={"center": new_enrollment.center, fee_field: new_fee},
    )
    if new_tm.is_deleted:
        new_tm.restore()
    setattr(new_tm, fee_field, new_fee)
    if not new_tm.center_id:
        new_tm.center = new_enrollment.center
    new_tm.save(update_fields=[fee_field, "center"] if new_tm.center_id else [fee_field])

    moved_amount = _move_surplus_allocations(old_tm=old_tm, new_tm=new_tm)
    old_state_after = _payment_state(old_enrollment, transfer_month)
    new_state_after = _payment_state(new_enrollment, transfer_month)

    archive = StudentGroupTransfer.objects.create(
        center=old_group.center,
        student=student,
        old_group=old_group,
        new_group=new_group,
        transfer_date=transfer_date,
        reason=(reason or "").strip(),
        performed_by=user if getattr(user, "is_authenticated", False) else None,
        old_payment_state={
            "before": old_state_before,
            "after": old_state_after,
            "new_enrollment_after": new_state_after,
            "moved_payment_amount": moved_amount,
            "old_group_financials": {
                "period_start": old_period_start.isoformat(),
                "period_end": old_period_end.isoformat() if old_period_start <= old_period_end else None,
                **old_period_financials,
            },
            "created_at": timezone.now().isoformat(),
        },
        old_attendance_summary=attendance_state,
    )

    return {
        "transfer": archive,
        "old_enrollment": old_enrollment,
        "new_enrollment": new_enrollment,
        "old_tuition_month": old_tm,
        "new_tuition_month": new_tm,
        "moved_payment_amount": moved_amount,
    }
