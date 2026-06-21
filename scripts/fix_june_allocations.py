"""
Iyun TM i to'liq PaymentAllocation ga ega bo'lmagan o'quvchilarni topadi va tuzatadi.
Natija: Qarzdorlar bo'sh, To'lovlar to'liq.
"""
from education.models import Enrollment, TuitionMonth, Payment, PaymentAllocation
from accounts.models import Center
from django.db import transaction
from datetime import date

c    = Center.objects.get(slug='proskill')
june = date(2026, 6, 1)

enrollments = Enrollment.objects.filter(
    group__center=c,
    is_active=True,
    is_deleted=False,
    student__is_archived=False,
    group__is_archived=False,
).select_related('student', 'group', 'group__center')

fixed   = 0
already = 0
no_pay  = 0

print(f"\nIyun TM allocation tekshiruvi...\n")

for enr in enrollments:
    tm = TuitionMonth.objects.filter(
        enrollment=enr, month=june, is_deleted=False
    ).first()
    if not tm or tm.fee_amount == 0:
        continue

    # Mavjud allocations summasini hisoblash
    paid_sum = sum(
        a.amount for a in PaymentAllocation.objects.filter(
            tuition_month=tm,
            payment__is_deleted=False,
        )
    )

    if paid_sum >= tm.fee_amount:
        already += 1
        continue  # To'liq to'langan — yaxshi

    remaining = tm.fee_amount - paid_sum
    name = f"{enr.student.familya} {enr.student.ism}"

    # Allokatsiya qilinmagan payment topish (iyun oyida, eng katta summa)
    pay = Payment.objects.filter(
        enrollment=enr,
        paid_date__year=june.year,
        paid_date__month=june.month,
        is_deleted=False,
        summa__gte=remaining,
    ).order_by('-paid_date', '-id').first()

    if not pay:
        # Bugungi to'lovni ham tekshir
        pay = Payment.objects.filter(
            enrollment=enr,
            is_deleted=False,
            summa__gte=remaining,
        ).order_by('-paid_date', '-id').first()

    if not pay:
        print(f"  ⚠️  {name} ({enr.group.nom}): payment topilmadi, qarz={remaining:,}")
        no_pay += 1
        continue

    try:
        with transaction.atomic():
            PaymentAllocation.objects.create(
                payment=pay,
                tuition_month=tm,
                amount=remaining,
            )
            print(f"  ✅ {name} ({enr.group.nom}): {remaining:,} so'm allocation yaratildi")
            fixed += 1
    except Exception as ex:
        print(f"  ❌ {name} ({enr.group.nom}): {ex}")

print(f"\n{'='*60}")
print(f"  Tuzatildi    : {fixed:>4} ta (allocation yaratildi)")
print(f"  Allaqachon   : {already:>4} ta (to'liq to'langan edi)")
print(f"  Payment yo'q : {no_pay:>4} ta (qo'lda ko'rib chiqish kerak)")
print(f"{'='*60}\n")
