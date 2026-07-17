import os
import django
from datetime import date

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import transaction
import django.db.models as models
from django.utils import timezone
from accounts.models import Center, User
from education.models import TuitionMonth, Enrollment, PaymentAllocation, Payment
from django.db.models import Sum, Q

def run():
    center = Center.objects.filter(slug="proskill").first()
    if not center:
        print("Center 'proskill' not found")
        return
        
    print(f"Target Center: {center.name} (ID: {center.id})")
    
    # Let's run the exact same queries as the dashboard to see what it sees
    from core.dashboard_views import _bulk_monthly_turnover, _six_month_range, _bulk_monthly_expenses
    
    today = timezone.localdate()
    # If today is June 2026, let's get the six month range
    six_months_meta = list(_six_month_range(today))
    six_months_pairs = [(ms, me) for ms, me, _ in six_months_meta]
    
    print("\n--- Running bulk monthly turnover (Same as Dashboard Chart) ---")
    bulk_turnover = _bulk_monthly_turnover(center, six_months_pairs)
    for ms, me, lbl in six_months_meta:
        key = (ms.year, ms.month)
        print(f" Month: {lbl} ({ms} to {me}) -> Turnover: {bulk_turnover.get(key, 0):,} UZS")
        
    print("\n--- Running bulk monthly expenses (Same as Dashboard Chart) ---")
    bulk_expenses = _bulk_monthly_expenses(center, six_months_pairs)
    for ms, me, lbl in six_months_meta:
        key = (ms.year, ms.month)
        print(f" Month: {lbl} ({ms} to {me}) -> Expenses: {bulk_expenses.get(key, 0):,} UZS")

    # Let's trace June 2026 allocations in detail
    june_start = date(2026, 6, 1)
    june_end = date(2026, 6, 30)
    
    from core.dashboard_views import _payment_allocations_for_center, _payments_for_center
    
    june_allocs = _payment_allocations_for_center(center).filter(
        tuition_month__month=june_start
    )
    print(f"\n--- June 2026 Allocation Details ---")
    print(f"Total active allocations pointing to June 2026: {june_allocs.count()}")
    print(f"Sum of active allocations pointing to June 2026: {june_allocs.aggregate(s=Sum('amount'))['s'] or 0:,} UZS")
    
    # Group allocations by payment date month
    allocs_by_payment_month = {}
    for al in june_allocs.select_related("payment"):
        pm = al.payment.paid_date.replace(day=1)
        allocs_by_payment_month[pm] = allocs_by_payment_month.get(pm, 0) + al.amount
        
    print("\nBreakdown of June 2026 allocations by payment date:")
    for pm, amt in sorted(allocs_by_payment_month.items()):
        print(f" - Payment Month {pm.strftime('%B %Y')}: {amt:,} UZS")
        
    # Check if there are unallocated payments in June
    unalloc_june = _payments_for_center(center).filter(
        paid_date__range=(june_start, june_end),
        allocations__isnull=True
    )
    print(f"\nUnallocated payments in June 2026: {unalloc_june.count()}")
    print(f"Sum of unallocated payments in June 2026: {unalloc_june.aggregate(s=Sum('summa'))['s'] or 0:,} UZS")
    
    # Print first 5 payments in June 2026
    all_june_payments = _payments_for_center(center).filter(
        paid_date__range=(june_start, june_end)
    )
    print(f"\nTotal payments registered with paid_date in June 2026: {all_june_payments.count()}")
    print(f"Sum of payments registered with paid_date in June 2026: {all_june_payments.aggregate(s=Sum('summa'))['s'] or 0:,} UZS")
    for p in all_june_payments[:5]:
        print(f" - Payment ID: {p.id} | Student: {p.student.get_full_name()} | Summa: {p.summa:,} UZS | Date: {p.paid_date}")

if __name__ == "__main__":
    run()
