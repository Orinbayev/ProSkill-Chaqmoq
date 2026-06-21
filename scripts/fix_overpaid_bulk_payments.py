"""
Bulk payment iyun TM fee dan ortiq bo'lgan enrollmentlarni tuzatadi:
  1. Ortiqcha bulk payment ni soft-delete
  2. Eski oy TM larini soft-delete
  3. Faqat iyun summasini Payment + PaymentAllocation qilib yozadi
"""
from education.models import Enrollment, TuitionMonth, Payment, PaymentAllocation
from accounts.models import Center
from django.db import transaction
from datetime import date

c     = Center.objects.get(slug='proskill')
today = date(2026, 6, 22)
june  = date(2026, 6, 1)

BULK_NOTE = "Eski qarz — to'lov bo'limiga o'tkazildi"

enrollments = Enrollment.objects.filter(
    group__center=c,
    is_deleted=False,
    student__is_archived=False,
    group__is_archived=False,
).select_related('student', 'group', 'group__center')

fixed   = 0
ok      = 0
no_june = 0

print(f"\n{'Guruh':<28} {'O\'quvchi':<28} {'Bulk':>10} {'June fee':>10} {'Holat'}")
print('─' * 90)

for enr in enrollments.order_by('group__nom', 'student__familya'):
    june_tm = TuitionMonth.objects.filter(
        enrollment=enr, month=june, is_deleted=False
    ).first()

    if not june_tm:
        no_june += 1
        continue

    june_fee = june_tm.fee_amount

    # Bugungi bulk payment(lar)
    bulk_pays = list(Payment.objects.filter(
        enrollment=enr,
        note=BULK_NOTE,
        is_deleted=False,
    ))

    bulk_total = sum(p.summa for p in bulk_pays)

    if bulk_total == 0:
        ok += 1
        continue

    name = f"{enr.student.familya} {enr.student.ism}"

    if bulk_total <= june_fee:
        # To'g'ri yoki kam — allocation tekshir
        ok += 1
        continue

    # bulk_total > june_fee — tuzatish kerak
    print(f"  {enr.group.nom:<26} {name:<28} {bulk_total:>10,} {june_fee:>10,}  ← tuzatiladi")

    try:
        with transaction.atomic():
            # 1. Eski TM larni soft-delete (iyungacha)
            old_tms = TuitionMonth.objects.filter(
                enrollment=enr,
                month__lt=june,
                is_deleted=False,
            )
            old_count = old_tms.count()
            old_tms.update(is_deleted=True, deleted_reason="cleanup_pre_june_debt")

            # 2. Bulk payment larni soft-delete
            for p in bulk_pays:
                p.is_deleted    = True
                p.deleted_reason = "bulk_pay_corrected"
                p.save(update_fields=['is_deleted', 'deleted_reason'])

            # 3. Iyun uchun to'g'ri Payment + Allocation yarat
            already = Payment.objects.filter(
                enrollment=enr,
                paid_date__year=june.year,
                paid_date__month=june.month,
                summa=june_fee,
                is_deleted=False,
                note="Iyun to'lovi (tuzatildi)",
            ).exists()

            if not already and june_fee > 0:
                center  = enr.center or (enr.group.center if enr.group else None)
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
                # June TM allocation
                alloc_exists = PaymentAllocation.objects.filter(
                    payment=new_pay, tuition_month=june_tm
                ).exists()
                if not alloc_exists:
                    PaymentAllocation.objects.create(
                        payment=new_pay,
                        tuition_month=june_tm,
                        amount=june_fee,
                    )

        fixed += 1

    except Exception as ex:
        name = f"{enr.student.familya} {enr.student.ism}"
        print(f"  ❌ {name} ({enr.group.nom}): {ex}")

print('─' * 90)
print(f"\n  Tuzatildi : {fixed:>4} ta  (ortiqcha bulk payment → faqat iyun)")
print(f"  To'g'ri   : {ok:>4} ta  (bulk == june fee, o'zgartirilmadi)")
print(f"  June TM yo'q: {no_june:>3} ta")
print()
