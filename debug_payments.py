import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from education.models import Payment
from django.db.models import Sum

count = Payment.objects.count()
total_sum = Payment.objects.aggregate(Sum('summa'))['summa__sum'] or 0
max_payments = Payment.objects.order_by('-summa').values('id', 'student__ism', 'group__nom', 'summa')[:10]

print(f"Total Payments: {count}")
print(f"Global Sum: {total_sum}")
print("Top 10 Payments:")
for p in max_payments:
    print(p)
