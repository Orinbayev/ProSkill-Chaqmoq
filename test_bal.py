import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from chaqmoq.models import LightningHistory
from education.models import Student
from django.db.models import Sum
from django.db.models.functions import Coalesce

# create a dummy record to see if the sum works
u_qs = Student.objects.all()[:2]
if u_qs.exists():
    s = u_qs[0]
    print("Testing with student:", s.user_id)
    LightningHistory.objects.get_or_create(student=s, points=3, reason="test", source="attendance")
    
    student_ids = [s.user_id]
    
    bal_qs = (
        LightningHistory.objects
        .filter(student__user_id__in=student_ids)
        .values("student__user_id")
        .annotate(s=Coalesce(Sum("points"), 0))
    )
    print("bal_qs list:", list(bal_qs))
    bal_map = {b["student__user_id"]: b["s"] for b in bal_qs}
    print("bal_map:", bal_map)
