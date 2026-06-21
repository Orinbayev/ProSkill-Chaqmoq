"""
Barcha proskill o'quvchilari uchun:
  — Iyungacha bo'lgan eski TuitionMonth larni o'chiradi
  — Bugun yozilgan noto'g'ri katta Payment ni o'chiradi
  — Faqat iyun oyining to'g'ri summasini Payment qilib yozadi

DRY_RUN = True  → faqat ko'rish (hech narsa o'zgarmaydi)
DRY_RUN = False → haqiqiy o'zgartirish
"""
from education.models import Enrollment, TuitionMonth, Payment, PaymentAllocation
from accounts.models import Center
from django.db import transaction
from datetime import date

DRY_RUN = False   # True=ko'rish, False=haqiqiy yozuv

c    = Center.objects.get(slug='proskill')
today = date(2026, 6, 22)
june  = date(2026, 6, 1)

print(f"\n{'='*65}")
print(f"  REJIM: {'🔍 DRY RUN (hech narsa o\'zgarmaydi)' if DRY_RUN else '⚠️  HAQIQIY YOZUV'}")
print(f"{'='*65}\n")

enrollments = Enrollment.objects.filter(
    group__center=c,
    is_active=True,
    is_deleted=False,
    student__is_archived=False,
    group__is_archived=False,
).select_related('student', 'group', 'group__center').order_by('group__nom', 'student__familya')

fixed   = 0
skipped = 0
errors  = 0

for enr in enrollments:
    old_tms = list(TuitionMonth.objects.filter(
        enrollment=enr,
        month__lt=june,
        is_deleted=False,
        fee_amount__gt=0,
    ))

    if not old_tms:
        skipped += 1
        continue  # Faqat iyun TM bor — to'g'ri, o'tkazib yubor

    june_tm = TuitionMonth.objects.filter(
        enrollment=enr, month=june, is_deleted=False
    ).first()
    if not june_tm:
        skipped += 1
        continue

    june_fee = june_tm.fee_amount
    name     = f"{enr.student.familya} {enr.student.ism}"
    old_sum  = sum(t.fee_amount for t in old_tms)

    # Haqiqiy eski to'lovlar bormi (bugungi bulk payment emas)?
    old_has_real_pay = any(
        PaymentAllocation.objects.filter(
            tuition_month=tm,
            payment__is_deleted=False,
        ).exclude(
            payment__note="Eski qarz — to'lov bo'limiga o'tkazildi"
        ).exists()
        for tm in old_tms
    )

    label = f"  {name:<30} {enr.group.nom:<28}"
    if old_has_real_pay:
        print(f"{label} ⚠️  haqiqiy eski to'lov bor — o'tkazildi")
        skipped += 1
        continue

    print(f"{label} {len(old_tms)} eski TM ({old_sum:,}) → iyun: {june_fee:,}")

    if DRY_RUN:
        fixed += 1
        continue

    try:
        with transaction.atomic():
            # 1. Eski oylar TM larini soft-delete
            for tm in old_tms:
                tm.is_deleted    = True
                tm.deleted_reason = "cleanup_pre_june_debt"
                tm.save(update_fields=['is_deleted', 'deleted_reason'])

            # 2. Bugungi noto'g'ri bulk payment ni soft-delete
            for p in Payment.objects.filter(
                enrollment=enr,
                paid_date=today,
                note="Eski qarz — to'lov bo'limiga o'tkazildi",
                is_deleted=False,
            ):
                p.is_deleted     = True
                p.deleted_reason = "bulk_pay_corrected"
                p.save(update_fields=['is_deleted', 'deleted_reason'])

            # 3. Iyun uchun to'g'ri Payment + PaymentAllocation yarat
            if june_fee > 0 and not Payment.objects.filter(
                enrollment=enr,
                paid_date__year=june.year,
                paid_date__month=june.month,
                summa=june_fee,
                is_deleted=False,
                note="Iyun to'lovi (tuzatildi)",
            ).exists():
                center = enr.center or (enr.group.center if enr.group else None)
                new_pay = Payment.objects.create(
                    enrollment=enr,
                    student=enr.student,
                    group=enr.group,
                    center=center,
                    summa=june_fee,
                    cash_amount=june_fee,
                    paid_date=june,
                    note="Iyun to'lovi (tuzatildi)",
                    payment_type='cash',
                )
                PaymentAllocation.objects.create(
                    payment=new_pay,
                    tuition_month=june_tm,
                    amount=june_fee,
                )
        fixed += 1
    except Exception as ex:
        print(f"  ❌ XATO: {name} — {ex}")
        errors += 1

print(f"\n{'='*65}")
print(f"  {'Ko\'riladi' if DRY_RUN else 'Tuzatildi'} : {fixed:>4} ta enrollment")
print(f"  O'tkazildi  : {skipped:>4} ta (faqat iyun TM yoki eski to'lov bor)")
print(f"  Xato        : {errors:>4} ta")
print(f"{'='*65}\n")
