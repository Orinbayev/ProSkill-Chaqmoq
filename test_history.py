from education.models import Group, Enrollment, Attendance, StudentGroupHistory
import django
django.setup()
atts = Attendance.objects.filter(present=True, date__year=2026, date__month=3)
missing = 0
found = 0
for att in atts:
    h = StudentGroupHistory.objects.filter(student=att.student, group=att.group, start_date__lte=att.date).filter(end_date__isnull=True).first()
    if h: found += 1
    else: missing += 1
print(f"Missing history for attendances: {missing}, Found: {found}")
