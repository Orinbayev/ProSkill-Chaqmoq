"""
Joriy to'lovlar to'g'rimi? — TM fee summasi bilan taqqoslash
"""
from education.models import Enrollment, TuitionMonth, Payment, PaymentAllocation
from accounts.models import Center
from django.db.models import Sum
from datetime import date

c    = Center.objects.get(slug='proskill')
june = date(2026, 6, 1)

# 1. Iyun TM lari jami (haqiqiy to'lanishi kerak bo'lgan summa)
tm_total = TuitionMonth.objects.filter(
    enrollment__group__center=c,
    enrollment__is_active=True,
    enrollment__is_deleted=False,
    enrollment__student__is_archived=False,
    month=june,
    is_deleted=False,
).aggregate(s=Sum('fee_amount'))['s'] or 0

# 2. Iyun to'lovlari jami (hozir To'lovlar bo'limida borlar)
pay_total = Payment.objects.filter(
    center=c,
    paid_date__year=2026,
    paid_date__month=6,
    is_deleted=False,
).aggregate(s=Sum('summa'))['s'] or 0

# 3. Ortiqcha (kurs narxi guruh narxidan katta) to'lovlar
from django.db.models import F
suspects = []
for enr in Enrollment.objects.filter(
    group__center=c,
    is_active=True,
    is_deleted=False,
    student__is_archived=False,
    group__is_archived=False,
).select_related('student', 'group'):
    group_price = int(getattr(enr.group, 'kurs_narxi', 0) or 0)
    kurs = enr.kurs_narhi or 0
    tm = TuitionMonth.objects.filter(enrollment=enr, month=june, is_deleted=False).first()
    if tm and tm.fee_amount > group_price and kurs > group_price:
        extra = tm.fee_amount - group_price
        name = f"{enr.student.familya} {enr.student.ism}"
        suspects.append((name, enr.group.nom, group_price, tm.fee_amount, extra))

suspects.sort(key=lambda x: -x[4])

print(f"\n{'='*65}")
print(f"  Iyun TM lar jami (to'lanishi kerak) : {tm_total:>15,} so'm")
print(f"  Iyun to'lovlar jami (hozir DB da)   : {pay_total:>15,} so'm")
print(f"  Farq                                 : {pay_total - tm_total:>+15,} so'm")
print(f"{'='*65}")

if suspects:
    print(f"\nKurs narxi guruh narxidan KATTA bo'lgan o'quvchilar:")
    print(f"  {'O\'quvchi':<28} {'Guruh':<26} {'Guruh':>8} {'TM fee':>10} {'Ortiqcha':>10}")
    print('  ' + '─'*85)
    total_extra = 0
    for name, grp, gp, tm_fee, extra in suspects[:20]:
        print(f"  {name:<28} {grp:<26} {gp:>8,} {tm_fee:>10,} {extra:>+10,}")
        total_extra += extra
    print('  ' + '─'*85)
    print(f"  Jami ortiqcha: {total_extra:>10,} so'm — agar bularni guruh narxiga tushirsangiz,")
    print(f"  To'lovlar jami: {pay_total - total_extra:>12,} so'm ga tushadi")
print()
