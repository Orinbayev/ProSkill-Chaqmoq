"""Chiqarilgan o'quvchining noto'g'ri oyga yozilgan qarzini to'g'ri oyga ko'chirish.

Muammo: o'quvchi (mas.) iyunda to'liq o'qib, oy oxirida guruhdan chiqarilgan.
Uning haqiqiy IYUN qarzi noto'g'ri IYUL TuitionMonth'iga yozilib qolgan (yoki
iyun umuman yaratilmagan). Qarzdorlarda iyun filterlaganda hech narsa chiqmaydi.

Bu modul: chiqarilgan enrollment uchun `last_billable_date`dan KEYINGI oyga
yozilgan, TO'LANMAGAN (paid=0) qarzni topib, uni to'g'ri oyga ko'chiradi.

XAVFSIZLIK:
  - Faqat paid=0 (to'lovsiz) TuitionMonth ko'chiriladi — pulga tegilmaydi.
  - Ko'chirish reversible: eski TM soft-delete (reason='cleanup_relocated_...'),
    yangi/to'g'ri oy TM protected reason bilan (recalc uni o'chirmaydi).
  - Transaction ichida. dry-run default — apply=True bo'lmaguncha yozmaydi.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from django.db import transaction
from django.db.models import Sum

from education.models import (
    Enrollment, TuitionMonth, PaymentAllocation, Attendance,
)
from education.services.tuition import (
    tuition_month_fee_field, enrollment_last_billable_date,
    enrollment_is_removed, month_first_day, reconcile_tuition_month,
    _billable_attendance_q,
)

FF = tuition_month_fee_field()


@dataclass
class Proposal:
    enrollment_id: int
    student_name: str
    group_name: str
    source_month: date          # noto'g'ri oy (mas. iyul)
    source_fee: int
    target_month: date          # to'g'ri oy (mas. iyun)
    target_existing_fee: int
    action: str                 # 'move' | 'zero_phantom' | 'skip_paid' | 'skip_unknown'
    note: str = ""


def _paid_for(tm: TuitionMonth) -> int:
    return int(
        PaymentAllocation.objects.filter(
            tuition_month=tm, payment__is_deleted=False,
        ).aggregate(s=Sum("amount"))["s"] or 0
    )


def _resolve_target_month(enr: Enrollment) -> Optional[date]:
    """O'quvchi haqiqatda o'qigan OXIRGI oy (qarz shu oyga tegishli)."""
    lb = enrollment_last_billable_date(enr)
    if lb:
        return month_first_day(lb)
    # last_lesson_date/history yo'q — oxirgi davomat oyidan aniqlaymiz
    last_att = (
        Attendance.objects.filter(student=enr.student, group=enr.group)
        .order_by("-date").values_list("date", flat=True).first()
    )
    if last_att:
        return month_first_day(last_att)
    start = getattr(enr, "joined_at", None) or getattr(enr, "created_at", None)
    if start:
        return month_first_day(start.date() if hasattr(start, "date") else start)
    return None


def build_proposals(enr: Enrollment) -> list[Proposal]:
    """Bitta chiqarilgan enrollment uchun ko'chirish takliflarini tuzadi."""
    if not enrollment_is_removed(enr):
        return []
    target = _resolve_target_month(enr)
    sname = f"{enr.student.familya} {enr.student.ism}"
    gname = getattr(enr.group, "nom", "?")

    props: list[Proposal] = []
    fee_gt0 = TuitionMonth.objects.filter(
        enrollment=enr, is_deleted=False, **{f"{FF}__gt": 0},
    ).order_by("month")

    for tm in fee_gt0:
        m = month_first_day(tm.month)
        if target is not None and m <= target:
            continue  # to'g'ri oy(lar) — tegmaymiz
        fee = int(getattr(tm, FF, 0) or 0)
        paid = _paid_for(tm)
        if paid > 0:
            props.append(Proposal(
                enr.id, sname, gname, m, fee, target or m, 0, "skip_paid",
                note=f"paid={paid} — pulga tegmaymiz, qo'lda tekshiring"))
            continue
        if target is None:
            props.append(Proposal(
                enr.id, sname, gname, m, fee, m, 0, "skip_unknown",
                note="to'g'ri oyni aniqlab bo'lmadi (last_lesson_date/davomat yo'q)"))
            continue
        tgt_tm = TuitionMonth.objects.filter(
            enrollment=enr, month=target, is_deleted=False).first()
        tgt_fee = int(getattr(tgt_tm, FF, 0) or 0) if tgt_tm else 0
        if tgt_fee > 0:
            props.append(Proposal(
                enr.id, sname, gname, m, fee, target, tgt_fee, "zero_phantom",
                note="to'g'ri oyda allaqachon qarz bor — noto'g'ri oy fantom, 0 qilamiz"))
        else:
            props.append(Proposal(
                enr.id, sname, gname, m, fee, target, tgt_fee, "move",
                note="qarz to'g'ri oyga ko'chiriladi"))
    return props


@transaction.atomic
def apply_proposal(p: Proposal) -> str:
    enr = Enrollment.all_objects.get(id=p.enrollment_id)
    src = TuitionMonth.objects.filter(
        enrollment=enr, month=p.source_month, is_deleted=False).first()
    if not src:
        return "source yo'q — o'tkazib yuborildi"
    if _paid_for(src) > 0:
        return "paid>0 — xavfsizlik uchun tegmadik"

    if p.action == "move":
        tgt, _created = TuitionMonth.all_objects.get_or_create(
            enrollment=enr, month=p.target_month,
            defaults={"center": enr.center or getattr(enr.group, "center", None),
                      FF: p.source_fee},
        )
        if tgt.is_deleted:
            tgt.is_deleted = False
            tgt.deleted_at = None
        setattr(tgt, FF, p.source_fee)
        tgt.center = tgt.center or enr.center or getattr(enr.group, "center", None)
        # protected reason — recalc va ensure_tuition_month buni o'chirmaydi
        tgt.deleted_reason = f"user_edit_relocated_from_{p.source_month:%Y-%m}"
        tgt.save()
        src.delete(reason=f"cleanup_relocated_to_{p.target_month:%Y-%m}")
        return f"MOVED {p.source_fee} {p.source_month:%Y-%m} → {p.target_month:%Y-%m}"

    if p.action == "zero_phantom":
        src.delete(reason=f"cleanup_phantom_after_{p.target_month:%Y-%m}")
        return f"ZEROED phantom {p.source_month:%Y-%m} (fee {p.source_fee})"

    return f"SKIP ({p.action})"


# ─────────────────────────────────────────────────────────────────────────────
# DAVOMATGA QARAB TIKLASH (asosiy yechim — davomat YOZILGAN bo'lsa)
# ─────────────────────────────────────────────────────────────────────────────
# Chiqarilgan o'quvchi guruhda o'qib (davomat qilingan) chiqarilgan bo'lsa, uning
# qarzi HAQIQIY davomat oyiga (mas. iyun) tegishli. Lekin ko'p holatda o'sha oy
# uchun TuitionMonth umuman yaratilmagan yoki qarz noto'g'ri oyga (iyul) yozilib
# qolgan → to'lov modalida to'g'ri oy ko'rinmaydi.
#
# reconcile_removed_enrollment: har davomat bo'lgan oy uchun TuitionMonth'ni
# haqiqiy davomatga qarab yaratadi/yangilaydi; davomatsiz (fantom) fee>0 paid=0
# oylarni soft-delete qiladi. Shunda to'g'ri oy(lar) to'lov modalida chiqadi.


def _billable_attendance_months(enr: Enrollment) -> list[date]:
    """O'quvchining shu guruhdagi davomat bo'lgan oylari (last_billable'gacha)."""
    qs = Attendance.objects.filter(
        student=enr.student, group=enr.group,
    ).filter(_billable_attendance_q())
    lb = enrollment_last_billable_date(enr)
    if lb is not None:
        qs = qs.filter(date__lte=lb)
    months = {month_first_day(d) for d in qs.values_list("date", flat=True)}
    return sorted(months)


@transaction.atomic
def reconcile_removed_enrollment(enr: Enrollment, apply: bool = False) -> dict:
    """Bitta chiqarilgan enrollment'ni davomatga qarab tiklaydi.

    Qaytaradi: {'reconciled': [(oy, fee)], 'phantoms': [(oy, fee)], 'skipped_paid': [...]}
    apply=False bo'lsa — hech narsa yozmaydi (rollback).
    """
    report = {"reconciled": [], "phantoms": [], "skipped_paid": []}
    if not enrollment_is_removed(enr):
        return report

    bmonths = _billable_attendance_months(enr)
    bset = set(bmonths)

    # 1) Davomat bo'lgan oylar → TuitionMonth reconcile (haqiqiy fee).
    for m in bmonths:
        if apply:
            tm = reconcile_tuition_month(enr, m)
            fee = int(getattr(tm, FF, 0) or 0)
        else:
            # dry-run: nima bo'lishini hisoblaymiz (yozmaymiz)
            from education.services.tuition import attendance_based_fee as _abf
            fee = int(_abf(enr, m) or 0)
        report["reconciled"].append((m, fee))

    # 2) Davomatsiz (fantom) fee>0, paid=0 oylar → soft-delete.
    stored = TuitionMonth.objects.filter(
        enrollment=enr, is_deleted=False, **{f"{FF}__gt": 0},
    ).order_by("month")
    for tm in stored:
        m = month_first_day(tm.month)
        if m in bset:
            continue  # haqiqiy oy — tegmaymiz
        fee = int(getattr(tm, FF, 0) or 0)
        paid = _paid_for(tm)
        if paid > 0:
            report["skipped_paid"].append((m, fee, paid))
            continue
        report["phantoms"].append((m, fee))
        if apply:
            tm.delete(reason="cleanup_phantom_no_attendance")

    if not apply:
        transaction.set_rollback(True)
    return report
