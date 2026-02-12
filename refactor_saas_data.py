
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import Center, User
from education.models import (
    Group, Enrollment, Payment, Attendance, Dars, GroupStudent, 
    Oquvchi, OylikHisobot, AttendanceHistory, DailyLightningSetting, 
    TeacherIncome, TuitionMonth, PaymentAllocation
)
from store.models import (
    Product, ProductImage, PurchaseRequest, Sale, Comment, 
    ExpenseCategory, Expense, Lead, Manba, Yonalish, LeadStatus
)
from core.models import Notification

def migrate_data():
    print("Starting data migration for SaaS refactor...")
    
    # 1. Get or Create Default Center
    default_center = Center.objects.filter(is_system=True).first()
    if not default_center:
        default_center = Center.objects.first()
    
    if not default_center:
        print("No centers found! Creating a default one...")
        default_center = Center.objects.create(
            name="Chaqmoq Academy",
            slug="chaqmoq",
            is_system=True
        )
    
    print(f"Using Primary Center: {default_center.name} (ID: {default_center.id})")

    # 2. Assign Users
    # Superusers should have a center to work in by default
    superuser = User.objects.filter(is_superuser=True).first()
    if superuser and not superuser.center:
        superuser.center = default_center
        superuser.role = 'director' # Assign role as requested
        superuser.save()
        print(f"Assigned superuser {superuser.email} to center {default_center.name}")

    User.objects.filter(center__isnull=True).update(center=default_center)
    print(f"Updated orphan users.")

    # 3. Education Models
    print("Updating Education models...")
    
    # Group already has center usually, but let's ensure
    Group.objects.filter(center__isnull=True).update(center=default_center)
    
    Enrollment.objects.filter(center__isnull=True).update(center=default_center)
    # Refine Enrollment center from group
    for enr in Enrollment.objects.filter(center__isnull=False):
        if enr.group and enr.group.center and enr.center != enr.group.center:
            enr.center = enr.group.center
            enr.save()

    Payment.objects.filter(center__isnull=True).update(center=default_center)
    for pay in Payment.objects.filter(center__isnull=False):
        if pay.group and pay.group.center and pay.center != pay.group.center:
            pay.center = pay.group.center
            pay.save()

    Attendance.objects.filter(center__isnull=True).update(center=default_center)
    for att in Attendance.objects.filter(center__isnull=False):
        if att.group and att.group.center and att.center != att.group.center:
            att.center = att.group.center
            att.save()

    # Models we just added center to
    Dars.objects.filter(center__isnull=True).update(center=default_center)
    for dars in Dars.objects.all():
        if dars.guruh and dars.guruh.center:
            dars.center = dars.guruh.center
            dars.save()

    GroupStudent.objects.filter(center__isnull=True).update(center=default_center)
    for gs in GroupStudent.objects.all():
        if gs.group and gs.group.center:
            gs.center = gs.group.center
            gs.save()

    Oquvchi.objects.filter(center__isnull=True).update(center=default_center)
    for oq in Oquvchi.objects.all():
        if oq.guruh and oq.guruh.center:
            oq.center = oq.guruh.center
            oq.save()

    OylikHisobot.objects.filter(center__isnull=True).update(center=default_center)
    AttendanceHistory.objects.filter(center__isnull=True).update(center=default_center)
    DailyLightningSetting.objects.filter(center__isnull=True).update(center=default_center)
    TeacherIncome.objects.filter(center__isnull=True).update(center=default_center)
    TuitionMonth.objects.filter(center__isnull=True).update(center=default_center)
    PaymentAllocation.objects.filter(center__isnull=True).update(center=default_center)

    # 4. Store Models
    print("Updating Store models...")
    Product.objects.filter(center__isnull=True).update(center=default_center)
    
    ProductImage.objects.filter(center__isnull=True).update(center=default_center)
    for pi in ProductImage.objects.all():
        if pi.product and pi.product.center:
            pi.center = pi.product.center
            pi.save()

    Comment.objects.filter(center__isnull=True).update(center=default_center)
    for c in Comment.objects.all():
        if c.product and c.product.center:
            c.center = c.product.center
            c.save()

    PurchaseRequest.objects.filter(center__isnull=True).update(center=default_center)
    Sale.objects.filter(center__isnull=True).update(center=default_center)
    ExpenseCategory.objects.filter(center__isnull=True).update(center=default_center)
    Expense.objects.filter(center__isnull=True).update(center=default_center)
    Lead.objects.filter(center__isnull=True).update(center=default_center)
    Manba.objects.filter(center__isnull=True).update(center=default_center)
    Yonalish.objects.filter(center__isnull=True).update(center=default_center)
    LeadStatus.objects.filter(center__isnull=True).update(center=default_center)

    # 5. Core
    Notification.objects.filter(center__isnull=True).update(center=default_center)

    print("Data migration completed successfully!")

if __name__ == "__main__":
    migrate_data()
