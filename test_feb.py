import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from education.models import StudentGroupHistory, Group, Attendance
from education.services.historical_finance_service import HistoricalFinanceService
from django.contrib.auth import get_user_model
User = get_user_model()

def check_feb():
    # Find a teacher with some income
    teachers = User.objects.filter(role='teacher')
    found = False
    for t in teachers:
        res = HistoricalFinanceService.calculate_teacher_salary(t, 2026, 2)
        if res['salary'] > 0:
            name = t.ism or t.username or str(t.id)
            print(f"Teacher {name} (ID: {t.id}) Feb Total: {res['salary']}")
            print(f"Daily Breakdown: {res['daily_breakdown']}")
            found = True
            break
    if not found:
        print("No teacher with Feb income found.")

if __name__ == "__main__":
    check_feb()
