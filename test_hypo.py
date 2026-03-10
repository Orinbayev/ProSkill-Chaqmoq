from education.models import Attendance, StudentGroupHistory, Enrollment
from django.db.models import Count

def check_fallbacks():
    # Only for March 2026
    atts = Attendance.objects.filter(present=True, date__year=2026, date__month=3).select_related('student', 'group')
    
    total = 0
    missing_h = 0
    diff = 0
    for att in atts:
        total += 1
        h = StudentGroupHistory.objects.filter(student=att.student, group=att.group, start_date__lte=att.date).filter(end_date__isnull=True).first()
        if not h:
            missing_h += 1
            # What is the enr val vs group val?
            enr = Enrollment.all_objects.filter(student=att.student, group=att.group).first() if hasattr(Enrollment, 'all_objects') else Enrollment.objects.filter(student=att.student, group=att.group).first()
            if enr:
                 grp_p = att.group.kurs_narxi or 0
                 enr_p = enr.kurs_narhi or 0
                 if grp_p != enr_p:
                     diff += 1
                     print(f"Mismatch: Group is {grp_p}, but Enr is {enr_p}")

    print(f"Total: {total}, Missing History: {missing_h}, Enr Differs: {diff}")
    
check_fallbacks()
