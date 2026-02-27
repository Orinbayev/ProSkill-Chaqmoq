import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from education.services.expected_income_service import calculate_expected_income
from education.models import TeacherExpectedIncomeSnapshot
from django.utils import timezone

User = get_user_model()
u = User.objects.filter(role='teacher').first()

# Clear previous snapshots for a clean test
TeacherExpectedIncomeSnapshot.objects.all().delete()

# 1. Test current month (should create snapshot)
res_current = calculate_expected_income(u)
print("--- Current month result ---")
print("Expected income:", res_current['expected_income'], "| Active students:", res_current['active_students'])

snap = TeacherExpectedIncomeSnapshot.objects.filter(teacher=u).first()
if snap:
    print(f"Snapshot created automatically for current month: Year={snap.year}, Month={snap.month}, Income={snap.expected_income}")
else:
    print("WARNING: Snapshot was not created!")

# 2. Test past month without snapshot
res_past_no_snap = calculate_expected_income(u, year=2026, month=1)
print("\n--- Past month result (NO snapshot) ---")
print("It uses current enrollments because there's no snapshot:", res_past_no_snap['expected_income'])

# 3. Create a manual snapshot for past month (e.g. they were saved previously)
TeacherExpectedIncomeSnapshot.objects.create(
    teacher=u, year=2026, month=1, expected_income=500000, active_students=2, income_per_student=250000
)

# 4. Test past month WITH snapshot
res_past_snap = calculate_expected_income(u, year=2026, month=1)
print("\n--- Past month result (WITH snapshot) ---")
print("It should use snapshot values: Income=", res_past_snap['expected_income'], " Students=", res_past_snap['active_students'])
