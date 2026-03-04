import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chaqmoq.settings')
django.setup()

from accounts.models import User
from education.models import Enrollment

mismatched = 0
unarchived = 0

for e in Enrollment.objects.all():
    student = e.student
    group = e.group
    changed = False

    if student and group:
        if student.center_id != group.center_id:
            # Assing the student to the group's center
            print(f"Fixing center for student {student.get_full_name()} (ID: {student.id}): Center {student.center_id} -> {group.center_id}")
            student.center_id = group.center_id
            changed = True
            mismatched += 1
        
        # If student is in a group (which means they are active in that group), but their user profile is archived
        if student.is_archived and not e.is_archived:
            print(f"Unarchiving student {student.get_full_name()} (ID: {student.id}) as they have active enrollment.")
            student.is_archived = False
            changed = True
            unarchived += 1
        
        if changed:
            student.save()

print(f"Fixed centers for {mismatched} students. Unarchived {unarchived} students.")
