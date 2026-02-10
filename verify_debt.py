from django.utils import timezone
from education.models import Enrollment, TuitionMonth, PaymentAllocation
from django.db.models import Sum
from education.services.tuition import ensure_tuition_month

try:
    # Test for Enrollment ID 284 (or substitute if needed)
    e = Enrollment.objects.get(id=284)
    today = timezone.localdate()
    cur_month = today.replace(day=1)

    print(f"--- Verification for Student: {e.student.get_full_name()} ---")

    # 1. Ensure months exist
    for i in range(-1, 2): # Last month, current, next
        m = (cur_month + timezone.timedelta(days=i*31)).replace(day=1)
        ensure_tuition_month(e, m)
        print(f"Ensured TuitionMonth for: {m}")

    # 2. Check totals up to cur_month
    tms = TuitionMonth.objects.filter(enrollment=e, month__lte=cur_month)
    total_fee = tms.aggregate(s=Sum('fee_amount'))['s'] or 0
    total_paid = PaymentAllocation.objects.filter(tuition_month__in=tms).aggregate(s=Sum('amount'))['s'] or 0
    debt = total_fee - total_paid

    print(f"Total Fee (up to now): {total_fee}")
    print(f"Total Paid (up to now): {total_paid}")
    print(f"Calculated Debt: {debt}")
    
    if debt < 0:
        print("Note: Overpayment detected.")
    
    print("Verification successful!")

except Enrollment.DoesNotExist:
    print("Error: Enrollment ID 284 not found. Please check existing IDs.")
except Exception as e:
    print(f"Error occurred: {e}")
