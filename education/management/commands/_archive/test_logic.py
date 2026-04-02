from django.core.management.base import BaseCommand
from accounts.models import User
from education.models import Group, Enrollment, Attendance
from education.services.historical_finance_service import HistoricalFinanceService

class Command(BaseCommand):
    def handle(self, *args, **options):
        # We need to test the logic
        # 1. First get all teachers with some attendance recorded
        teachers = User.objects.filter(role='teacher')
        
        for t in teachers:
             res = HistoricalFinanceService.get_yearly_teacher_stats(t, 2026)
             val = res[2]['salary']
             
             m_salary_old = 0
             for group in t.group_set.all():
                 for enr in group.enrollments.all():
                     kurs = enr.kurs_narhi or 0
                     foiz = (enr.oqituvchi_foiz or 0) / 100
                     les = Attendance.objects.filter(
                         group=group, student=enr.student, date__year=2026, date__month=3
                     ).filter(present=True).count()
                     if les > 0:
                         lessons_per_month = group.oy_dars_soni or 12
                         teacher_part = kurs * foiz / lessons_per_month
                         m_salary_old += teacher_part * les
             
             if m_salary_old > 0 or val > 0:
                 self.stdout.write(f"Teacher: {t.get_full_name()} | OLD: {m_salary_old} | NEW: {val}")
