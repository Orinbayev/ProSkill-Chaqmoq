"""
Iyun TM fee_amount guruh narxidan katta bo'lgan o'quvchilarni topadi.
"""
from education.models import Enrollment, TuitionMonth, Payment
from accounts.models import Center
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

print(f"\n{'Guruh':<28} {'O\'quvchi':<28} {'Guruh narxi':>12} {'TM fee':>12} {'kurs_narhi':>12} {'student_pay':>12}")
print('─' * 108)

wrong = 0
for enr in enrollments.order_by('group__nom', 'student__familya'):
    tm = TuitionMonth.objects.filter(
        enrollment=enr, month=june, is_deleted=False
    ).first()
    if not tm:
        continue

    group_price = int(getattr(enr.group, 'kurs_narxi', 0) or 0)
    tm_fee      = tm.fee_amount
    kurs_narhi  = enr.kurs_narhi
    stu_pay     = enr.student_payable_amount

    if tm_fee != group_price and tm_fee > 0:
        name = f"{enr.student.familya} {enr.student.ism}"
        wrong += 1
        print(f"{enr.group.nom:<28} {name:<28} {group_price:>12,} {tm_fee:>12,} {kurs_narhi:>12,} {str(stu_pay):>12}")

print('─' * 108)
print(f"\nTM fee guruh narxidan farqli: {wrong} ta\n")
