from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from education.services.salary_forecast_service import calculate_teacher_salary_forecast, get_days_passed, get_days_in_month

class SalaryForecastTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.teacher = User.objects.create(email="teacher1@example.com", role="teacher", is_active=True)
        
    def test_get_days_in_month(self):
        y, m = 2026, 2
        self.assertEqual(get_days_in_month(y, m), 28)
        
    def test_forecast_0_data(self):
        res = calculate_teacher_salary_forecast(self.teacher, 2026, 2, "run_rate")
        
        self.assertEqual(res['teacher']['name'], self.teacher.get_full_name())
        self.assertEqual(res['real_salary'], 0)
        self.assertEqual(res['mtd_earned'], 0)
        self.assertEqual(res['forecast_salary'], 0)
        self.assertEqual(res['next_month_forecast'], 0)
        self.assertEqual(len(res['sources']), 0)
