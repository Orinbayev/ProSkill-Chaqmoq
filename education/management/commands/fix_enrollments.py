from django.core.management.base import BaseCommand
from accounts.models import User, Center
from education.models import Group, Enrollment

class Command(BaseCommand):
    help = 'Fixes missing enrollments for students'

    def handle(self, *args, **options):
        self.stdout.write("--- FIXING ENROLLMENTS ---")
        
        students = User.objects.filter(role='student')
        self.stdout.write(f"Total students found: {students.count()}")
        
        created_count = 0
        
        for student in students:
            if Enrollment.objects.filter(student=student).exists():
               continue
               
            center = student.center
            if not center:
                center = Center.objects.first()
                if not center:
                    self.stdout.write("No centers found! Creating default center...")
                    center = Center.objects.create(name="Default Center", slug="default-center")
                
                student.center = center
                student.save(update_fields=['center'])
                
            group = Group.objects.filter(center=center).first()
            if not group:
                self.stdout.write(f"--> Creating 'General Group' for {center.name}...")
                group = Group.objects.create(
                    nom="General Group",
                    center=center,
                    kurs_narxi=500000,
                    oqituvchi_foiz=40,
                    oy_dars_soni=12
                )
                
            Enrollment.objects.create(
                student=student,
                group=group,
                center=center,
                kurs_narhi=group.kurs_narxi,
                oqituvchi_foiz=group.oqituvchi_foiz,
                is_active=True
            )
            self.stdout.write(f"--> Enrollment created: {student.get_full_name()} -> {group.nom}")
            created_count += 1
            
        self.stdout.write(f"Done! Created {created_count} new enrollments.")
