import os
import django
import sys
from datetime import date

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from accounts.models import User, Center
from education.models import Enrollment, Group, TuitionMonth, Payment, PaymentAllocation
from django.db.models import Sum, Q

def run_diagnose():
    print("=== STARTING DIAGNOSTIC ENGINE ===")
    
    # 1. Find the target center
    center = Center.objects.filter(slug="proskill").first() or Center.objects.filter(slug="proskill-center").first()
    if not center:
        print("Center not found")
        return
        
    print(f"Target Center: {center.name} (ID: {center.id}, Slug: {center.slug})")

    # 2. Find target student (Abdulaziz Abdullayev)
    student = User.objects.filter(
        center=center, 
        role="student", 
        ism__icontains="Abdulaziz", 
        familya__icontains="Abdullayev"
    ).first()
    
    if student:
        print(f"\nStudent: {student.get_full_name()} (ID: {student.id}, Email: {student.email})")

        # List all enrollments for this student
        enrollments = Enrollment.objects.filter(student=student, is_deleted=False)
        print(f"\nEnrollments ({enrollments.count()} total):")
        for enr in enrollments:
            print(f" - Enrollment ID: {enr.id} | Group: {enr.group.nom} (Price: {enr.group.kurs_narxi}, custom price: {enr.student_payable_amount}) | Active: {enr.is_active}")
            
            # List TuitionMonths for this enrollment
            tms = TuitionMonth.all_objects.filter(enrollment=enr).order_by("month")
            print("   TuitionMonths:")
            for tm in tms:
                alloc_sum = PaymentAllocation.objects.filter(tuition_month=tm, is_deleted=False).aggregate(s=Sum("amount"))["s"] or 0
                print(f"     * Month: {tm.month} | Fee: {tm.fee_amount} | Paid: {alloc_sum} | Deleted: {tm.is_deleted} (Reason: {getattr(tm, 'deleted_reason', '')})")

        # List all payments for this student
        payments = Payment.objects.filter(
            Q(student=student) | Q(enrollment__student=student)
        ).filter(is_deleted=False).order_by("id")
        
        print(f"\nPayments ({payments.count()} total):")
        for p in payments:
            alloc_sum = PaymentAllocation.objects.filter(payment=p, is_deleted=False).aggregate(s=Sum("amount"))["s"] or 0
            print(f" - Payment ID: {p.id} | Summa: {p.summa} | Group: {p.group.nom if p.group else 'None'} | Date: {getattr(p, 'paid_at', getattr(p, 'sana', 'None'))} | Total Allocated: {alloc_sum}")
            
            # List allocations for this payment
            allocs = PaymentAllocation.objects.filter(payment=p, is_deleted=False)
            for al in allocs:
                print(f"     * Allocated to: {al.tuition_month.month} ({al.tuition_month.enrollment.group.nom}) -> {al.amount} so'm")
    else:
        print("Student Abdulaziz Abdullayev not found")

    # 3. List all payments in June 2026 for this center
    print("\n=== SYSTEM INVENTORY: JUNE 2026 PAYMENTS ===")
    june_payments = Payment.objects.filter(
        Q(center=center) | Q(enrollment__center=center) | Q(group__center=center)
    ).filter(is_deleted=False).order_by("id")
    
    june_only = []
    for p in june_payments:
        p_date = getattr(p, "paid_at", None) or getattr(p, "sana", None) or getattr(p, "paid_date", None)
        if p_date:
            if hasattr(p_date, "date"):
                p_date = p_date.date()
            if p_date.year == 2026 and p_date.month == 6:
                june_only.append(p)
                
    print(f"Total payments made in June 2026: {len(june_only)}")
    for p in june_only[:30]:  # Limit to first 30 for readability
        alloc_sum = PaymentAllocation.objects.filter(payment=p, is_deleted=False).aggregate(s=Sum("amount"))["s"] or 0
        print(f" - ID: {p.id} | Student: {p.student.get_full_name()} | Summa: {p.summa} | Date: {getattr(p, 'paid_at', getattr(p, 'sana', 'None'))} | Allocated: {alloc_sum}")
        allocs = PaymentAllocation.objects.filter(payment=p, is_deleted=False)
        for al in allocs:
            print(f"     * Allocated to: {al.tuition_month.month} ({al.tuition_month.enrollment.group.nom}) -> {al.amount} so'm")

if __name__ == "__main__":
    run_diagnose()
