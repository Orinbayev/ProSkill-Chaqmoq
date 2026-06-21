"""
Aprel 118M va dashboard muammosini tushuntiradi.
"""
from education.models import Payment, TuitionMonth, PaymentAllocation
from accounts.models import Center
from django.db.models import Sum, Count
from datetime import date

c = Center.objects.get(slug='proskill')

print("\n" + "="*65)
print("  APREL OYI TO'LOVLARI TAHLILI")
print("="*65)

# Aprel oyidagi to'lovlar
april = date(2026, 4, 1)
apr_pays = Payment.objects.filter(
    center=c, paid_date__year=2026, paid_date__month=4, is_deleted=False
)
apr_total = apr_pays.aggregate(s=Sum('summa'))['s'] or 0
print(f"\n  Aprel to'lovlar soni  : {apr_pays.count():>6} ta")
print(f"  Aprel to'lovlar jami  : {apr_total:>15,} so'm")

# Aprel TM lari (TuitionMonth)
apr_tms = TuitionMonth.objects.filter(
    enrollment__group__center=c, month=april, is_deleted=False
)
apr_tm_total = apr_tms.aggregate(s=Sum('fee_amount'))['s'] or 0
print(f"\n  Aprel TM lar soni     : {apr_tms.count():>6} ta")
print(f"  Aprel TM lar jami     : {apr_tm_total:>15,} so'm")

# Aprelga allocation qilingan to'lovlar (payment sana qandayligidan qat'iy nazar)
apr_alloc = PaymentAllocation.objects.filter(
    tuition_month__enrollment__group__center=c,
    tuition_month__month=april,
    tuition_month__is_deleted=False,
    payment__is_deleted=False,
)
apr_alloc_total = apr_alloc.aggregate(s=Sum('amount'))['s'] or 0
print(f"\n  Aprel TM larga allocation : {apr_alloc.count():>4} ta")
print(f"  Allocation jami           : {apr_alloc_total:>15,} so'm")

# Aprel to'lovlar taqsimoti: qaysi payment note bilan?
print(f"\n  Aprel to'lovlar (note bo'yicha):")
for p in apr_pays.values('note').annotate(n=Count('id'), s=Sum('summa')).order_by('-s')[:10]:
    print(f"    {p['n']:>4} ta | {p['s'] or 0:>12,} | {(p['note'] or '')[:50]}")

# Barcha oylar uchun TM allocation jami (To'lovlar korinishi)
print(f"\n{'='*65}")
print("  BARCHA OYLAR TM ALLOCATION JAMI (To'lovlar ko'rinishi)")
print("="*65)
from django.db.models.functions import TruncMonth
rows = (
    PaymentAllocation.objects
    .filter(
        tuition_month__enrollment__group__center=c,
        tuition_month__is_deleted=False,
        payment__is_deleted=False,
    )
    .values('tuition_month__month')
    .annotate(total=Sum('amount'), cnt=Count('id'))
    .order_by('tuition_month__month')
)
for r in rows:
    mo = r['tuition_month__month']
    print(f"  {mo.strftime('%Y-%m')}  |  {r['cnt']:>4} ta  |  {r['total'] or 0:>15,} so'm")

# Dashboard uchun
print(f"\n{'='*65}")
print("  DASHBOARD XARAJAT VA MAOSH TEKSHIRUVI")
print("="*65)
try:
    from finance.models import Expense
    june_exp = Expense.objects.filter(
        center=c, date__year=2026, date__month=6, is_deleted=False
    )
    exp_total = june_exp.aggregate(s=Sum('amount'))['s'] or 0
    print(f"\n  Iyun xarajatlar: {june_exp.count()} ta, jami: {exp_total:,} so'm")
    if exp_total > 10_000_000:
        print(f"\n  Xarajatlar kategoriyasi bo'yicha:")
        for row in june_exp.values('category__name').annotate(s=Sum('amount')).order_by('-s')[:10]:
            print(f"    {(row['category__name'] or 'Boshqa'):<30} {row['s'] or 0:>12,}")
except Exception as e:
    print(f"  Expense model: {e}")

try:
    from finance.models import TeacherSalary
    june_sal = TeacherSalary.objects.filter(
        center=c, month__year=2026, month__month=6, is_deleted=False
    )
    sal_total = june_sal.aggregate(s=Sum('amount'))['s'] or 0
    print(f"\n  Iyun o'q.maoshi: {june_sal.count()} ta, jami: {sal_total:,} so'm")
except Exception as e:
    print(f"  TeacherSalary: {e}")
print()
