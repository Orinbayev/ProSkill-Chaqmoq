"""
kurs_narhi=0 lekin TuitionMonth da fee > 0 bo'lgan o'quvchilarni topadi,
TM ni 0 ga tuzatadi va To'lovlar bo'limida ko'rinishi uchun 0 so'm Payment yaratadi.
"""
from education.models import Enrollment, TuitionMonth, Payment
from accounts.models import Center
from django.utils import timezone
from datetime import date

c = Center.objects.get(slug='proskill')
m = date(2026, 6, 1)

# kurs_narhi=0 lekin guruh narxi > 0 bo'lgan faol enrollmentlar
qs = Enrollment.objects.filter(
    group__center=c,
    is_active=True,
    is_deleted=False,
    student__is_archived=False,
    group__is_archived=False,
    kurs_narhi=0,
    group__kurs_narxi__gt=0,
    student_payable_amount__isnull=True,
).select_related('student', 'group', 'group__center')

print(f"\nProSkill — kurs_narhi=0 bo'lgan o'quvchilar: {qs.count()} ta\n")
print(f"{'#':<4} {'Guruh':<25} {'O\'quvchi':<28} {'TM fee':>10} {'Holat'}")
print('-' * 80)

to_fix = []
for e in qs.order_by('group__nom', 'student__familya'):
    tm = TuitionMonth.objects.filter(
        enrollment=e, month=m, is_deleted=False
    ).first()
    tm_fee = tm.fee_amount if tm else 0
    name = f"{e.student.familya or ''} {e.student.ism or ''}".strip()
    if tm and tm_fee > 0:
        to_fix.append((e, tm))
        print(f"{len(to_fix):<4} {e.group.nom:<25} {name:<28} {tm_fee:>10,}  ← tuzatiladi")
    else:
        status = "TM yo'q" if not tm else "allaqachon 0"
        print(f"{'—':<4} {e.group.nom:<25} {name:<28} {tm_fee:>10,}  ({status})")

print('-' * 80)
print(f"\nTuzatilishi kerak: {len(to_fix)} ta\n")

if not to_fix:
    print("Hamma yaxshi — tuzatish kerak emas.")
else:
    print("Tuzatmoqda...\n")
    fixed_tm = 0
    fixed_pay = 0

    for e, tm in to_fix:
        name = f"{e.student.familya or ''} {e.student.ism or ''}".strip()

        # 1. TM fee ni 0 ga tuzat
        old_fee = tm.fee_amount
        tm.fee_amount = 0
        tm.save(update_fields=['fee_amount'])
        fixed_tm += 1

        # 2. To'lovlar bo'limida ko'rinishi uchun 0 so'm Payment
        exists = Payment.objects.filter(
            enrollment=e,
            paid_date__year=m.year,
            paid_date__month=m.month,
            summa=0,
            is_deleted=False,
        ).exists()
        if not exists:
            center = e.center or (e.group.center if e.group else None)
            Payment.objects.create(
                enrollment=e,
                student=e.student,
                group=e.group,
                center=center,
                summa=0,
                cash_amount=0,
                paid_date=m,
                note="Bepul o'quvchi (kurs_narhi=0)",
                payment_type='cash',
            )
            fixed_pay += 1
            print(f"  ✅ {name} ({e.group.nom}): {old_fee:,} → 0  | 0 so'm Payment yaratildi")
        else:
            print(f"  ✅ {name} ({e.group.nom}): {old_fee:,} → 0  | Payment allaqachon bor")

    print(f"\n{'='*50}")
    print(f"  TM tuzatildi   : {fixed_tm} ta")
    print(f"  Payment yaratildi: {fixed_pay} ta")
    print(f"  Ular endi Qarzdorlardan chiqib, To'lovlarda ko'rinadi.")
    print(f"{'='*50}\n")
