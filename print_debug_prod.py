import os
import django
from datetime import date
from django.db.models import Sum

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import Center, User
from education.models import Enrollment, TuitionMonth

def print_debug():
    # Only for PROSKILL
    proskill_centers = Center.objects.filter(name__icontains='proskill')
    my_center = max(proskill_centers, key=lambda c: User.objects.filter(role='student', is_archived=False, center=c).count()) if proskill_centers else None
    
    if not my_center:
        return
        
    s = User.objects.filter(role='student', is_archived=False, center=my_center, first_name__icontains='Azizbek').first()
    if not s:
        print("Azizbek not found")
        return
        
    print(f"Student: {s.first_name} {s.last_name}")
    
    active_enr = Enrollment.objects.filter(student=s, is_active=True)
    print(f"Active Enrollments: {active_enr.count()}")
    for e in active_enr:
        print(f" E id={e.id}, group={getattr(e.group, 'nom', None)}, price={e.kurs_narhi}, created_at={e.created_at}")
        tms = TuitionMonth.objects.filter(enrollment=e)
        print(f" TuitionMonths for e={e.id}: {[(tm.month, tm.fee_amount) for tm in tms]}")

if __name__ == '__main__':
    print_debug()
