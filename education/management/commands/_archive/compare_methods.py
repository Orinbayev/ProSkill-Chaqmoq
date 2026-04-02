from django.core.management.base import BaseCommand
from accounts.models import User
from education.services.historical_finance_service import HistoricalFinanceService

class Command(BaseCommand):
    def handle(self, *args, **options):
        # Find Davlatnazar Bekchanov
        teacher = User.objects.filter(first_name__icontains='Davlatnazar').first()
        if not teacher:
            self.stdout.write("Teacher not found!")
            return
            
        self.stdout.write(f"Teacher: {teacher.get_full_name()} ({teacher.id})")
        
        # Method 1
        res1 = HistoricalFinanceService.calculate_teacher_salary(teacher, 2026, 3)
        self.stdout.write(f"Method 1 (calculate_teacher_salary): {res1['salary']}")
        self.stdout.write(f"Method 1 Details: {res1['details']}")
        
        # Method 2
        res2 = HistoricalFinanceService.get_yearly_teacher_stats(teacher, 2026)
        self.stdout.write(f"Method 2 (get_yearly_teacher_stats) for March: {res2[2]['salary']}")
