from education.models import CenterExpense
from store.models import Expense
from accounts.models import Center
from django.db.models import Sum, Count
from datetime import date

c = Center.objects.get(slug='proskill')
d_from = date(2026, 6, 1)
d_to   = date(2026, 6, 30)

print("\n=== IYUN XARAJATLAR (CenterExpense) ===")
ce_qs = CenterExpense.objects.filter(center=c, date__range=(d_from, d_to), is_deleted=False)
ce_total = ce_qs.aggregate(s=Sum('amount'))['s'] or 0
print(f"Soni: {ce_qs.count()} ta  |  Jami: {ce_total:,} so'm")
for r in ce_qs.values('category__name').annotate(s=Sum('amount'), n=Count('id')).order_by('-s')[:15]:
    print(f"  {r['n']:>4} ta  {(r['category__name'] or 'Boshqa'):<35} {r['s'] or 0:>12,}")

print("\n=== IYUN XARAJATLAR (legacy Expense) ===")
exp_qs = Expense.objects.filter(sana__date__range=(d_from, d_to))
try:
    exp_qs = exp_qs.filter(worker__center=c)
except:
    pass
exp_total = exp_qs.aggregate(s=Sum('summa'))['s'] or 0
print(f"Soni: {exp_qs.count()} ta  |  Jami: {exp_total:,} so'm")

print(f"\nJAMI XARAJAT: {ce_total + exp_total:,} so'm")

print("\n=== APREL TO'LOVLAR TAHLILI ===")
from education.models import Payment
from django.db.models import Q
apr = Payment.objects.filter(center=c, paid_date__year=2026, paid_date__month=4, is_deleted=False)
print(f"Aprel to'lovlar: {apr.count()} ta, jami: {apr.aggregate(s=Sum('summa'))['s'] or 0:,} so'm")
print("Bular — real (staff tomonidan kiritilgan) tarixiy to'lovlar.")
print("Bulk skriptimiz FAQAT iyun 22 va iyun 1 sanali to'lovlar yaratdi.")
print("\nAprel to'lovlarning sanasi bo'yicha:")
for r in apr.values('paid_date').annotate(n=Count('id'), s=Sum('summa')).order_by('paid_date')[:10]:
    print(f"  {r['paid_date']}  |  {r['n']:>4} ta  |  {r['s'] or 0:>12,}")
