import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from accounts.models import User
from education.models import Group, Enrollment, Attendance
from education.services.historical_finance_service import HistoricalFinanceService

ts = User.objects.filter(role='teacher')
for t in ts:
    print(f"--- {t.first_name} ---")
    res = HistoricalFinanceService.get_yearly_teacher_stats(t, 2026)
    new_val = res[2]['salary']
    
    m_salary_old = 0
    calculated_new = 0
    
    # We will simulate exactly what old code did vs new code.
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
                m_salary_old += teacher_part * les
    
    # How does new code calculate this?
    from datetime import date
    from django.db.models import Q
    start_bound = date(2026, 3, 1)
    end_bound = date(2026, 4, 1)
    all_atts = Attendance.objects.filter(
        Q(teacher=t) | Q(group__oqituvchi=t),
        date__gte=start_bound,
        date__lt=end_bound,
        present=True
    ).select_related('group')
    
    for att in all_atts:
         is_lead = (att.group.oqituvchi_id == t.id)
         if not is_lead and att.teacher_id != t.id: continue
         
         from education.models import StudentGroupHistory
         h = StudentGroupHistory.objects.filter(
             student=att.student, group=att.group, start_date__lte=att.date
         ).filter(Q(end_date__isnull=True) | Q(end_date__gte=att.date)).order_by('-start_date').first()
         
         if h:
             oy = h.group.oy_dars_soni or 12
             share = (h.kurs_narxi * h.oqituvchi_foiz / 100) / oy
         else:
             oy = att.group.oy_dars_soni or 12
             share = (att.group.kurs_narxi * att.group.oqituvchi_foiz / 100) / oy
         
         calculated_new += share
         
         # Now let's see if this student is in enrollments
         enr = Enrollment.objects.filter(group=att.group, student=att.student).first()
         if enr:
             e_kurs = enr.kurs_narhi or 0
             e_foiz = (enr.oqituvchi_foiz or 0) / 100
             e_oy = att.group.oy_dars_soni or 12
             e_share = (e_kurs * e_foiz) / e_oy
             if e_share != share:
                 print(f"DIFF: {att.student.first_name} | Old logic share: {e_share} vs New logic share: {share} (h={bool(h)})")
         else:
              print(f"MISSING ENR: {att.student.first_name} has {share} but NOT IN ENROLLMENTS!")
              
    print(f"OLD: {m_salary_old:.0f} | NEW: {calculated_new:.0f} (from func: {new_val})")
