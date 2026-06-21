from education.models import Payment
from accounts.models import Center
from django.db.models import Sum
from datetime import date

c = Center.objects.get(slug='proskill')

t22 = Payment.objects.filter(center=c, paid_date=date(2026,6,22), is_deleted=False).aggregate(s=Sum('summa'))['s'] or 0
t1  = Payment.objects.filter(center=c, paid_date=date(2026,6,1),  is_deleted=False).aggregate(s=Sum('summa'))['s'] or 0
all6 = Payment.objects.filter(center=c, paid_date__year=2026, paid_date__month=6, is_deleted=False).aggregate(s=Sum('summa'))['s'] or 0
n22 = Payment.objects.filter(center=c, paid_date=date(2026,6,22), is_deleted=False).count()
n1  = Payment.objects.filter(center=c, paid_date=date(2026,6,1),  is_deleted=False).count()

print(f"\nJune 22 to'lovlar : {n22:>4} ta  →  {t22:>15,} so'm")
print(f"June 1  to'lovlar : {n1:>4} ta  →  {t1:>15,} so'm")
print(f"Jami iyun (1-30)  :           →  {all6:>15,} so'm\n")
