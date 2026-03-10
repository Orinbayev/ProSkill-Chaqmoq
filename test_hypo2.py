import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from accounts.models import User
from education.models import Group, Enrollment, Attendance
from education.services.historical_finance_service import HistoricalFinanceService

t = User.objects.filter(first_name__icontains='Davlatnazar').first()

if t:
     res = HistoricalFinanceService.get_yearly_teacher_stats(t, 2026)
     print(f"NEW: {res[2]['salary']}")
     
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
                 teacher_part = (kurs * foiz) / lessons_per_month
                 
                 print(f"OLD: {enr.student.first_name} | {les} x {(teacher_part):.0f} (kurs={kurs}, foiz={foiz*100}) = {teacher_part*les:.0f}")
                 m_salary_old += teacher_part * les
                 
     print(f"OLD total: {m_salary_old}")
