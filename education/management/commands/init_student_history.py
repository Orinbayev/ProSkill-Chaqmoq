from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date
from education.models import Enrollment, StudentGroupHistory

class Command(BaseCommand):
    help = 'Initializes StudentGroupHistory for existing active enrollments'

    def handle(self, *args, **options):
        enrollments = Enrollment.objects.filter(is_active=True)
        count = 0
        for enr in enrollments:
            # Use January 1st of current year as a safe historical starting point for existing enrollments
            safe_start_date = date(2026, 1, 1)
            
            if not StudentGroupHistory.objects.filter(student=enr.student, group=enr.group).exists():
                StudentGroupHistory.objects.create(
                    student=enr.student,
                    group=enr.group,
                    center=enr.center,
                    start_date=safe_start_date,
                    kurs_narxi=enr.kurs_narhi,
                    oqituvchi_foiz=enr.oqituvchi_foiz
                )
                count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {count} StudentGroupHistory records'))
