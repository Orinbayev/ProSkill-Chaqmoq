from accounts.models import Center
from education.models import TuitionMonth
from datetime import date
from django.utils import timezone

c = Center.objects.get(slug='proskill')

qs = TuitionMonth.objects.filter(
    enrollment__group__center=c,
    enrollment__is_active=False,
    month=date(2026, 6, 1),
    is_deleted=False,
)

print('Topildi:', qs.count(), 'ta')
n = qs.update(
    is_deleted=True,
    deleted_at=timezone.now(),
    deleted_reason='Guruhdan chiqarilgan, iyun qarz notogri yozilgan',
)
print('Ochirildi:', n, 'ta')
