"""
teacherowski markazidagi iyun muammosini tashxislaydi:
To'lovlarda ham, Qarzdorlarda ham bor bo'lgan o'quvchilar.
"""
from education.models import Enrollment, TuitionMonth, Payment, PaymentAllocation
from accounts.models import Center
from django.db.models import Sum
from datetime import date

c    = Center.objects.get(slug='teacherowski')
june = date(2026, 6, 1)

print(f"\n{'='*70}")
print(f"  TEACHEROWSKI — IYUN MUAMMOSI TASHXISI")
print(f"{'='*70}\n")

# Faol enrollmentlar
enrollments = Enrollment.objects.filter(
    group__center=c,
    is_active=True,
    is_deleted=False,
    student__is_archived=False,
    group__is_archived=False,
).select_related('student', 'group')

print(f"Faol enrollmentlar: {enrollments.count()} ta\n")

both   = []  # To'lovlarda ham, Qarzdorlarda ham
pay_only  = []  # Faqat To'lovlarda
debt_only = []  # Faqat Qarzdorlarda
ok     = []  # Muammo yo'q

for enr in enrollments:
    tm = TuitionMonth.objects.filter(
        enrollment=enr, month=june, is_deleted=False
    ).first()

    # To'lovlar bo'limida bormi?
    pay_sum = Payment.objects.filter(
        enrollment=enr,
        paid_date__year=june.year,
        paid_date__month=june.month,
        is_deleted=False,
    ).aggregate(s=Sum('summa'))['s'] or 0

    # TM bo'yicha to'langan miqdor (allocation orqali)
    if tm:
        alloc_sum = PaymentAllocation.objects.filter(
            tuition_month=tm,
            payment__is_deleted=False,
        ).aggregate(s=Sum('amount'))['s'] or 0
        debt = max(0, tm.fee_amount - alloc_sum)
        fee  = tm.fee_amount
    else:
        alloc_sum = 0
        debt = 0
        fee  = 0

    name = f"{enr.student.familya} {enr.student.ism}"

    if pay_sum > 0 and debt > 0:
        both.append((name, enr.group.nom, fee, pay_sum, alloc_sum, debt))
    elif pay_sum > 0 and debt == 0:
        ok.append(name)
    elif pay_sum == 0 and debt > 0:
        debt_only.append((name, enr.group.nom, fee, debt))

print(f"{'─'*70}")
print(f"  TO'LOVLARDA HAM, QARZDORLARDA HAM BOR: {len(both)} ta")
print(f"{'─'*70}")
if both:
    print(f"  {'O\'quvchi':<28} {'Guruh':<22} {'TM fee':>9} {'Pay':>10} {'Alloc':>9} {'Qarz':>9}")
    print(f"  {'─'*92}")
    for name, grp, fee, pay, alloc, debt in both[:30]:
        print(f"  {name:<28} {grp:<22} {fee:>9,} {pay:>10,} {alloc:>9,} {debt:>9,}")

print(f"\n{'─'*70}")
print(f"  FAQAT QARZDORLARDA (to'lovsiz): {len(debt_only)} ta")
print(f"{'─'*70}")
for name, grp, fee, debt in debt_only[:20]:
    print(f"  {name:<28} {grp:<22} {debt:>9,}")

print(f"\n{'─'*70}")
print(f"  XULOSA")
print(f"{'─'*70}")
print(f"  Ikkalasida bor   : {len(both):>4} ta  ← TUZATISH KERAK (allocation yetishmaydi)")
print(f"  Faqat qarz       : {len(debt_only):>4} ta")
print(f"  To'g'ri (ok)     : {len(ok):>4} ta")
print(f"  Faqat to'lov     : {len(pay_only):>4} ta")
print()
