"""
fix_debt_bugs.py — Mart/Aprel qarz muammosi va Iyun noto'g'ri
allocation muammosini tuzatuvchi skript.

MUAMMOLAR (kod tahlilidan):
1. reset_june_debts.py o'chirilgan TuitionMonth'lar (cleanup_non_june_months)
   keyingi to'lov kiritishda ensure_tuition_month tomonidan qayta tiklanib,
   eski fee bilan debt ko'rsatib chiqardi.

2. Yangi payment kiritishda ensure_all_tuition_months_since_start →
   find_earliest_unpaid_month tiklanib qolgan eski oyni "birinchi to'lanmagan"
   deb topdi → Iyun to'lovi noto'g'ri oylarga allocation qilindi.

TUZATISH TARTIBI:
  A. Hali o'chirilgan cleanup TuitionMonth'larni "manual_cleared" ga o'tkazish
     (ularni qayta tiklash bloklash uchun — kelajakka yo'naltirilgan fix).
  B. Allaqachon tiklanib qolgan muammoli oylar bor enrollment'lar uchun
     reallocate_enrollment() ishlatib to'lovlarni qayta taqsimlash.
  C. Iyun to'lovi noto'g'ri joylashgan bo'lsa hisobot.

ISHLATISH:
    python fix_debt_bugs.py [center_slug]
    # center_slug berilmasa barcha markazlar uchun ishlaydi

MUHIM:
    - Skript barcha o'zgarishlarni topib ko'rsatadi, tasdiqlashni so'raydi.
    - Faqat "yes" kiritilganda o'zgarish saqlanadi.
"""

import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from datetime import date
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone

from accounts.models import Center
from education.models import (
    TuitionMonth, PaymentAllocation, Payment, Enrollment
)
from education.services.tuition import (
    tuition_month_fee_field,
    reallocate_enrollment,
    month_first_day,
)


JUNE_2026 = date(2026, 6, 1)
CLEANUP_REASONS = [
    "cleanup_non_june_months",
    "cleanup_inactive_or_archived_enrollments_for_june",
    "move_future_allocations_to_credit_balance",
]


def _paid_for_tm(tm):
    return (
        PaymentAllocation.objects.filter(tuition_month=tm, is_deleted=False)
        .aggregate(s=Sum("amount"))["s"] or 0
    )


def run_fix(center=None):
    fee_field = tuition_month_fee_field()
    now = timezone.now()

    # ─── Markaz filtrini aniqlash ────────────────────────────────────────────
    tm_center_q = Q()
    enr_center_q = Q()
    if center:
        tm_center_q = Q(enrollment__center=center) | Q(enrollment__group__center=center)
        enr_center_q = (
            Q(center=center)
            | Q(center__isnull=True, group__center=center)
            | Q(center__isnull=True, student__center=center)
        )

    print("=" * 70)
    print("BOSHLANDI: Qarz muammolarini tuzatish skripti")
    if center:
        print(f"  Markaz: {center.name}")
    else:
        print("  Markaz: BARCHA MARKAZLAR")
    print("=" * 70)

    # ================================================================
    # TAHLIL A: Hali is_deleted=True bo'lgan cleanup TuitionMonth'lar
    # ================================================================
    print("\n[A] Hali o'chirilgan cleanup TuitionMonth'larni tekshirish...")
    still_deleted_qs = TuitionMonth.all_objects.filter(
        is_deleted=True,
        deleted_reason__in=CLEANUP_REASONS,
    ).filter(tm_center_q)

    # "reset_*" prefikslilari
    reset_deleted_qs = TuitionMonth.all_objects.filter(
        is_deleted=True,
        deleted_reason__startswith="reset_",
    ).filter(tm_center_q)

    n_a = still_deleted_qs.count() + reset_deleted_qs.count()
    print(f"   cleanup_* sababli, hali is_deleted=True: {still_deleted_qs.count()} ta")
    print(f"   reset_* sababli, hali is_deleted=True:   {reset_deleted_qs.count()} ta")
    print(f"   ⟹ Bularni 'manual_cleared' ga o'tkazamiz (jami: {n_a} ta)")

    # ================================================================
    # TAHLIL B: Tiklanib qolgan cleanup oylar (is_deleted=False)
    # ================================================================
    print("\n[B] Tiklanib qolgan cleanup TuitionMonth'larni tekshirish...")
    restored_qs = TuitionMonth.all_objects.filter(
        is_deleted=False,
        deleted_reason__in=CLEANUP_REASONS,
    ).filter(tm_center_q).select_related(
        "enrollment", "enrollment__group", "enrollment__student"
    )

    problem_enr_ids = set()
    debtor_report = []
    for tm in restored_qs:
        paid = _paid_for_tm(tm)
        fee = int(getattr(tm, fee_field, 0) or 0)
        debt = max(0, fee - paid)
        if debt > 0:
            enr = tm.enrollment
            st = enr.student
            grp = enr.group
            debtor_report.append({
                "enr": enr,
                "month": tm.month,
                "fee": fee,
                "paid": paid,
                "debt": debt,
                "student": st.get_full_name() if st else "?",
                "group": grp.nom if grp else "?",
            })
            problem_enr_ids.add(enr.id)

    if not debtor_report:
        print("   ✅ Muammo yo'q (barcha tiklanib qolgan oylar debt=0).")
    else:
        print(f"   ⚠️  {len(debtor_report)} ta TuitionMonth'da debt>0:")
        for r in debtor_report:
            print(
                f"      - {r['month']} | {r['student']} | {r['group']} | "
                f"fee={r['fee']:,} paid={r['paid']:,} debt={r['debt']:,}"
            )
        print(
            f"\n   ⟹ {len(problem_enr_ids)} ta enrollment uchun reallocate_enrollment()"
            " ishga tushiriladi (to'lovlarni qayta taqsimlash)."
        )

    # ================================================================
    # TAHLIL C: Iyun to'lovlari allocation tekshiruvi
    # ================================================================
    print("\n[C] Iyun to'lovlari allocation tekshiruvi...")
    if center:
        june_pay_qs = Payment.objects.filter(
            Q(center=center) | Q(group__center=center) | Q(enrollment__center=center),
            paid_date__year=2026,
            paid_date__month=6,
            is_deleted=False,
            enrollment__isnull=False,
        )
    else:
        june_pay_qs = Payment.objects.filter(
            paid_date__year=2026,
            paid_date__month=6,
            is_deleted=False,
            enrollment__isnull=False,
        )

    june_wrong = []
    for p in june_pay_qs.select_related("student", "enrollment"):
        june_alloc = (
            PaymentAllocation.objects.filter(
                payment=p, tuition_month__month=JUNE_2026, is_deleted=False
            ).aggregate(s=Sum("amount"))["s"] or 0
        )
        wrong_qs = PaymentAllocation.objects.filter(
            payment=p, is_deleted=False
        ).exclude(tuition_month__month=JUNE_2026)
        wrong_total = wrong_qs.aggregate(s=Sum("amount"))["s"] or 0

        if wrong_total > 0:
            june_wrong.append({
                "payment": p,
                "june_alloc": june_alloc,
                "wrong_total": wrong_total,
                "wrong_qs": wrong_qs,
            })
            problem_enr_ids.add(p.enrollment_id)

    if not june_wrong:
        print("   ✅ Barcha Iyun to'lovlari to'g'ri allocation qilingan.")
    else:
        print(f"   ⚠️  {len(june_wrong)} ta Iyun to'lovi noto'g'ri oylarga allocation qilingan:")
        for item in june_wrong:
            p = item["payment"]
            st = p.student.get_full_name() if p.student else "?"
            print(
                f"      Payment#{p.id} | {st} | summa={p.summa:,} | "
                f"june_alloc={item['june_alloc']:,} | noto'g'ri={item['wrong_total']:,}"
            )
            for a in item["wrong_qs"]:
                print(f"        → {a.tuition_month.month} oyiga {a.amount:,} so'm")

    # ================================================================
    # Agar hech muammo yo'q bo'lsa
    # ================================================================
    if n_a == 0 and not debtor_report and not june_wrong:
        print("\n✅ Hech qanday muammo topilmadi. Hech narsa o'zgartirilmadi.")
        return

    # ================================================================
    # Tasdiqlash
    # ================================================================
    print()
    print(f"Jami o'zgartirilishi kerak bo'lgan enrollment'lar: {len(problem_enr_ids)} ta")
    confirm = input("Tuzatishni boshlashni xohlaysizmi? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y", "ha", "h"):
        print("Bekor qilindi. Hech narsa o'zgarmadi.")
        return

    with transaction.atomic():
        # ── A: cleanup TuitionMonth'larni manual_cleared ga o'tkazish ────────
        n_a1 = still_deleted_qs.update(deleted_reason="manual_cleared")
        n_a2 = reset_deleted_qs.update(deleted_reason="manual_cleared")
        print(f"\n[A] {n_a1 + n_a2} ta TuitionMonth manual_cleared ga o'tkazildi.")

        # ── B: Muammoli enrollment'lar uchun reallocate_enrollment ───────────
        if problem_enr_ids:
            problem_enrs = Enrollment.objects.filter(
                id__in=problem_enr_ids
            ).select_related("student", "group", "center")

            reallocated = 0
            errors = []
            for enr in problem_enrs:
                try:
                    reallocate_enrollment(enr)
                    reallocated += 1
                    st = enr.student.get_full_name() if enr.student else "?"
                    print(f"   ✅ Reallocated: {st} | {enr.group.nom if enr.group else '?'}")
                except Exception as exc:
                    errors.append((enr, str(exc)))

            print(f"\n[B+C] {reallocated} ta enrollment qayta taqsimlandi.")
            if errors:
                print(f"   ⚠️  {len(errors)} ta xatolik:")
                for enr, err in errors:
                    st = enr.student.get_full_name() if enr.student else "?"
                    print(f"      - {st}: {err}")

        print("\n✅ Barcha o'zgarishlar saqlandi (committed).")

    # ── Cache tozalash ────────────────────────────────────────────────────────
    try:
        from django.core.cache import cache
        cache.clear()
        print("⚡ Cache tozalandi.")
    except Exception:
        pass

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
