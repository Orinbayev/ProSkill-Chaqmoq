from education.models import Enrollment, TuitionMonth
from accounts.models import Center
from django.db.models import Sum
from datetime import date

c = Center.objects.get(slug='proskill')
m = date(2026, 6, 1)

qs = (
    Enrollment.objects
    .filter(
        group__center=c,
        is_active=True,
        is_deleted=False,
        student__is_archived=False,
        group__is_archived=False,
        student_payable_amount__isnull=False,
    )
    .select_related('student', 'group')
    .order_by('student_payable_amount', 'group__nom')
)

print(f"\nProSkill — maxsus narx belgilangan o'quvchilar: {qs.count()} ta\n")
print(f"{'Guruh':<25} {'O\'quvchi':<28} {'Belgilangan':>12} {'TM fee':>10} {'Qarz':>10}")
print('-' * 90)

total_wrong = 0
for e in qs:
    tm = TuitionMonth.objects.filter(
        enrollment=e, month=m, is_deleted=False
    ).first()
    tm_fee = tm.fee_amount if tm else None
    paid = 0
    if tm:
        paid = int(
            TuitionMonth.objects.filter(id=tm.id)
            .values_list(
                'allocations__amount', flat=True
            ).exclude(allocations__payment__is_deleted=True)
            .aggregate(s=Sum('allocations__amount'))['s'] or 0
        )
    debt = max(0, (tm_fee or 0) - paid) if tm_fee is not None else 0

    name = f"{e.student.familya or ''} {e.student.ism or ''}".strip()
    group = e.group.nom if e.group else '?'
    belgilangan = e.student_payable_amount

    mismatch = ''
    if tm_fee is not None and tm_fee != belgilangan:
        mismatch = '  ⚠️ FARQ BOR'
        total_wrong += 1

    print(
        f"{group:<25} {name:<28} {belgilangan:>12,} "
        f"{tm_fee if tm_fee is not None else 'YOQ':>10} "
        f"{debt:>10,}{mismatch}"
    )

print('-' * 90)
print(f"\nTM fee != belgilangan narx: {total_wrong} ta  ← bular qarz chiqarishi mumkin\n")
