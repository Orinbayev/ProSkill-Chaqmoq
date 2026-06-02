import os
import sys
from pathlib import Path

# Loyiha bosh papkasini Python yo'liga qo'shamiz
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from accounts.models import Center, User
from education.models import Enrollment, Group, TuitionMonth

print("=== INSPECTING CENTERS AND STUDENTS ===")
for center in Center.objects.filter(is_deleted=False):
    students_count = User.objects.filter(center=center, role='student', is_archived=False).count()
    enrollments_count = Enrollment.objects.filter(is_deleted=False).filter(
        django.db.models.Q(center=center) | django.db.models.Q(center__isnull=True, group__center=center)
    ).count()
    active_enrollments = Enrollment.objects.filter(
        is_deleted=False,
        is_active=True,
        student__is_archived=False,
        group__is_archived=False,
        group__is_deleted=False
    ).filter(
        django.db.models.Q(center=center) | django.db.models.Q(center__isnull=True, group__center=center)
    ).count()
    print(f"Center: {center.name} (Slug: {center.slug}, ID: {center.id})")
    print(f"  Total Students: {students_count}")
    print(f"  Total Enrollments: {enrollments_count}")
    print(f"  Active Enrollments for June: {active_enrollments}")
