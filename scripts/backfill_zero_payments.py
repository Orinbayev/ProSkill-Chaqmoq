"""
student_payable_amount=0 bo'lgan mavjud o'quvchilar uchun
To'lovlar bo'limida ko'rinishi uchun 0 so'm Payment yaratadi.
"""
from education.models import Enrollment, Payment
from accounts.models import Center
from datetime import date

c = Center.objects.get(slug='proskill')
m = date(2026, 6, 1)

qs = Enrollment.objects.filter(
    group__center=c,
    is_active=True,
    is_deleted=False,
    student__is_archived=False,
    group__is_archived=False,
    student_payable_amount=0,
).select_related('student', 'group', 'group__center')

print(f"student_payable_amount=0 bo'lgan o'quvchilar: {qs.count()} ta\n")

created = 0
skipped = 0
for e in qs:
    exists = Payment.objects.filter(
        enrollment=e,
        paid_date__year=m.year,
        paid_date__month=m.month,
        summa=0,
        is_deleted=False,
    ).exists()
    if exists:
        skipped += 1
        continue
    center = e.center or (e.group.center if e.group else None)
    Payment.objects.create(
        enrollment=e,
        student=e.student,
        group=e.group,
        center=center,
        summa=0,
        cash_amount=0,
        paid_date=m,
        note="Bepul o'quvchi",
        payment_type='cash',
    )
    name = f"{e.student.familya or ''} {e.student.ism or ''}".strip()
    print(f"  ✅ {name} ({e.group.nom}) — 0 so'm Payment yaratildi")
    created += 1

print(f"\nYaratildi: {created} ta | O'tkazildi: {skipped} ta (allaqachon bor)")
