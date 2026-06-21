from education.models import Enrollment, TuitionMonth
from accounts.models import Center
from datetime import date

c = Center.objects.get(slug='proskill')
m = date(2026, 6, 1)

# student_payable_amount=0 lekin TuitionMonth fee farqli bo'lganlar
qs = Enrollment.objects.filter(
    group__center=c,
    is_active=True,
    is_deleted=False,
    student__is_archived=False,
    group__is_archived=False,
    student_payable_amount=0,
)

print(f"\nTuzatilishi kerak bo'lgan enrollment: {qs.count()} ta\n")

fixed = 0
for e in qs:
    tms = TuitionMonth.objects.filter(
        enrollment=e,
        month=m,
        is_deleted=False,
    ).exclude(fee_amount=0)

    count = tms.count()
    if count == 0:
        continue

    name = f"{e.student.familya or ''} {e.student.ism or ''}".strip()
    old_fee = tms.first().fee_amount
    tms.update(fee_amount=0)
    print(f"  ✅ {name} ({e.group.nom}): {old_fee:,} → 0 so'm")
    fixed += 1

print(f"\nJami tuzatildi: {fixed} ta TuitionMonth\n")
