"""
fix_debt_bugs.py — Mart/Aprel qarz muammosini va Iyun noto'g'ri
allocation muammosini tuzatuvchi skript.

MUAMMOLAR:
1. reset_june_debts.py o'chirilgan TuitionMonth'lar keyingi to'lov kiritishda
   qayta tiklanib, eski fee bilan debt ko'rsatib chiqardi.
2. Iyun to'lovi Iyun TuitionMonth'iga emas, tiklanib qolgan eski (Mart/Aprel/May)
   TuitionMonth'larga allocation qilinib ketdi.

TUZATISH:
1. Hali is_deleted=True bo'lgan "cleanup_*" va "reset_*" TuitionMonth'larni
   "manual_cleared"ga o'tkazamiz (ensure_tuition_month ularni qayta tiklamas uchun).
2. Iyun to'lovi noto'g'ri oylarga allocation qilingan bo'lsa — o'chirib,
   Iyun TuitionMonth'iga qayta allocation qilamiz.
3. is_deleted=False bo'lib qolgan "cleanup_*" TuitionMonth'larning debt
   holatini tekshirib chiqamiz.

ISHLATISH:
    python fix_debt_bugs.py [center_slug]
    # center_slug berilmasa barcha markazlar uchun ishlaydi
"""

import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from datetime import date
from django.db import transaction
from django.db.models import Sum, Q, F
from django.utils import timezone

from accounts.models import Center
from education.models import (
    TuitionMonth, PaymentAllocation, Payment, Enrollment
)
from education.services.tuition import (
    tuition_month_fee_field,
    _allocate_amount_forward,
    month_first_day,
)


def run_fix(center=None):
    fee_field = tuition_month_fee_field()
    now = timezone.now()
    june = date(2026, 6, 1)

    # ─── FILTR ──────────────────────────────────────────────────────────────
    center_filter = Q()
    if center:
        center_filter = (
            Q(enrollment__center=center)
            | Q(enrollment__group__center=center)
        )

    print("=" * 70)
    print("BOSHLANDI: Qarz muammolarini tuzatish")
    if center:
        print(f"  Markaz: {center.name}")
    print("=" * 70)

    # ================================================================
    # QADAM 1: Hali o'chirilgan "cleanup_*"/"reset_*" TuitionMonth'larni
    #          "manual_cleared"ga o'tkazamiz — ular qayta tiklanmasin.
    # ================================================================
    print("\n[1] Hali o'chirilgan cleanup TuitionMonth'larni manual_cleared ga o'tkazish...")
    cleanup_deleted = TuitionMonth.all_objects.filter(
        is_deleted=True,
        deleted_reason__in=[
            "cleanup_non_june_months",
            "cleanup_inactive_or_archived_enrollments_for_june",
            "move_future_allocations_to_credit_balance",
        ],
    ).filter(center_filter)

    # "reset_*" prefiksli sabablar
    reset_deleted = TuitionMonth.all_objects.filter(
        is_deleted=True,
        deleted_reason__startswith="reset_",
    ).filter(center_filter)

    n1 = cleanup_deleted.count() + reset_deleted.count()
    cleanup_deleted.update(deleted_reason="manual_cleared")
    reset_deleted.update(deleted_reason="manual_cleared")
    print(f"   ✅ {n1} ta TuitionMonth manual_cleared ga o'tkazildi.")

    # ================================================================
    # QADAM 2: Tiklanib qolgan "cleanup_*" TuitionMonth'larni tekshiramiz.
    #          Agar debt > 0 bo'lsa — muammo mavjud.
    # ================================================================
    print("\n[2] Tiklanib qolgan cleanup TuitionMonth'larni tekshirish...")
    restored_cleanup = TuitionMonth.all_objects.filter(
        is_deleted=False,
        deleted_reason__in=[
            "cleanup_non_june_months",
            "cleanup_inactive_or_archived_enrollments_for_june",
        ],
    ).filter(center_filter).select_related(
        "enrollment", "enrollment__group", "enrollment__student"
    )

    problem_tms = []
    for tm in restored_cleanup:
        paid = (
            PaymentAllocation.objects.filter(
                tuition_month=tm, is_deleted=False
            ).aggregate(s=Sum("amount"))["s"]
            or 0
        )
        fee = int(getattr(tm, fee_field, 0) or 0)
        debt = max(0, fee - paid)
        if debt > 0:
            problem_tms.append((tm, fee, paid, debt))

    if not problem_tms:
        print("   ✅ Muammo topilmadi (barcha tiklanib qolgan oylar debt=0).")
    else:
        print(f"   ⚠️  {len(problem_tms)} ta TuitionMonth'da debt > 0 muammo bor:")
        for tm, fee, paid, debt in problem_tms:
            st = tm.enrollment.student
            grp = tm.enrollment.group
            print(
                f"      - {tm.month} | {st.get_full_name()} | {grp.nom} | "
                f"fee={fee:,} paid={paid:,} debt={debt:,}"
            )

    # ================================================================
    # QADAM 3: Iyun to'lovlari noto'g'ri oylarga allocation qilinganmi?
    # ================================================================
    print("\n[3] Iyun to'lovlari allocation tekshiruvi...")
    if center:
        june_payments = Payment.objects.filter(
            Q(center=center) | Q(group__center=center) | Q(enrollment__center=center),
            paid_date__year=2026,
            paid_date__month=6,
            is_deleted=False,
            enrollment__isnull=False,
        ).select_related("enrollment", "enrollment__group", "student")
    else:
        june_payments = Payment.objects.filter(
            paid_date__year=2026,
            paid_date__month=6,
            is_deleted=False,
            enrollment__isnull=False,
        ).select_related("enrollment", "enrollment__group", "student")

    misallocated = []
    for p in june_payments:
        # Bu to'lovning june allocationsini topamiz
        june_alloc = PaymentAllocation.objects.filter(
            payment=p,
            tuition_month__month=june,
            is_deleted=False,
        ).aggregate(s=Sum("amount"))["s"] or 0

        # Boshqa oylarga ketgan allocation
        wrong_alloc = PaymentAllocation.objects.filter(
            payment=p,
            is_deleted=False,
        ).exclude(tuition_month__month=june)

        wrong_total = (
            wrong_alloc.aggregate(s=Sum("amount"))["s"] or 0
        )

        if wrong_total > 0 and june_alloc < p.summa:
            misallocated.append((p, wrong_alloc, wrong_total, june_alloc))

    if not misallocated:
        print("   ✅ Iyun to'lovlari to'g'ri allocation qilingan.")
    else:
        print(f"   ⚠️  {len(misallocated)} ta Iyun to'lovi noto'g'ri allocation:")
        for p, wrong_alloc, wrong_total, june_alloc in misallocated:
            st = p.student
            print(
                f"      - Payment#{p.id} | {st.get_full_name()} | summa={p.summa:,} | "
                f"june_alloc={june_alloc:,} | noto'g'ri_oylarga={wrong_total:,}"
            )
            for a in wrong_alloc:
                print(f"        → {a.tuition_month.month} oyiga {a.amount:,} so'm")

    if not misallocated and not problem_tms:
        print("\n✅ Hech qanday muammo topilmadi. Hech narsa o'zgartirilmadi.")
        return

    # ================================================================
    # QADAM 4: Tuzatishni tasdiqlash
    # ================================================================
    print()
    confirm = input("Tuzatishni boshlashni xohlaysizmi? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y", "ha", "h"):
        print("Bekor qilindi.")
        return

    with transaction.atomic():
        fixed_count = 0

        # 4a: Noto'g'ri allocation qilingan Iyun to'lovlarini tuzatamiz
        for p, wrong_alloc, wrong_total, june_alloc in misallocated:
            enr = p.enrollment

            # 1) Noto'g'ri allocation'larni o'chiramiz (soft-delete)
            for a in wrong_alloc.filter(is_deleted=False):
                a.is_deleted = True
                a.deleted_at = now
                a.deleted_reason = "realloc_fix_to_june"
                a.save(update_fields=["is_deleted", "deleted_at", "deleted_reason"])

            # 2) June TuitionMonth'ini topamiz yoki yaratamiz
            june_tm = TuitionMonth.objects.filter(
                enrollment=enr, month=june, is_deleted=False
            ).first()

            if june_tm is None:
                # Manual_cleared bo'lgan bo'lishi mumkin — restore etmaymiz
                # Boshqa holatda yaratamiz
                june_fee = int(getattr(enr, "effective_student_payable_amount", 0) or 0)
                if june_fee <= 0:
                    june_fee = int(getattr(enr, "full_course_amount", 0) or 0)
                if june_fee <= 0:
                    grp = enr.group
                    june_fee = int(getattr(grp, "kurs_narxi", 0) or 0)
                june_tm, _ = TuitionMonth.objects.get_or_create(
                    enrollment=enr,
                    month=june,
                    defaults={
                        "center": getattr(enr, "center", None),
                        fee_field: june_fee,
                    },
                )

            # 3) June TuitionMonth'iga to'g'ri allocation yozamiz
            june_fee = int(getattr(june_tm, fee_field, 0) or 0)
            already_paid = (
                PaymentAllocation.objects.filter(
                    tuition_month=june_tm, is_deleted=False
                ).aggregate(s=Sum("amount"))["s"]
                or 0
            )
            owed = max(0, june_fee - already_paid)
            to_allocate = min(p.summa, owed)

            if to_allocate > 0:
                PaymentAllocation.objects.create(
                    center=p.center or getattr(enr, "center", None),
                    payment=p,
                    tuition_month=june_tm,
                    amount=to_allocate,
                )
                print(
                    f"   ✅ Payment#{p.id} ({p.student.get_full_name()}) "
                    f"→ Iyun 2026'ga {to_allocate:,} so'm allocation yozildi."
                )

            # 4) Ortiqcha pul credit_balance ga
            leftover = p.summa - to_allocate
            if leftover > 0:
                Enrollment.objects.filter(pk=enr.pk).update(
                    credit_balance=F("credit_balance") + leftover
                )
                print(f"      (Ortiqcha {leftover:,} so'm credit_balance ga o'tkazildi)")

            fixed_count += 1

        # 4b: Debt muammosi bor tiklanib qolgan TuitionMonth'larni manual_cleared ga o'tkazamiz
        #     (Ularning to'lovlari allaqachon boshqa oylarga yozilgan)
        for tm, fee, paid, debt in problem_tms:
            TuitionMonth.objects.filter(pk=tm.pk).update(
                is_deleted=True,
                deleted_at=now,
                deleted_reason="manual_cleared",
            )
            PaymentAllocation.objects.filter(
                tuition_month=tm, is_deleted=False
            ).update(
                is_deleted=True,
                deleted_at=now,
                deleted_reason="manual_cleared_cleanup",
            )
            st = tm.enrollment.student
            print(
                f"   ✅ {tm.month} | {st.get_full_name()} — "
                f"noto'g'ri qarz manual_cleared ga o'tkazildi."
            )
            fixed_count += 1

        print(f"\n✅ JAMI {fixed_count} ta muammo tuzatildi. Tranzaksiya saqlandi.")

    print("=" * 70)
    print("YAKUNLANDI")
    print("=" * 70)


if __name__ == "__main__":
    center_slug = sys.argv[1].strip() if len(sys.argv) > 1 else None
    center = None
    if center_slug:
        center = Center.objects.filter(slug=center_slug).first()
        if not center:
            print(f"❌ '{center_slug}' slugli markaz topilmadi!")
            sys.exit(1)
    run_fix(center)
