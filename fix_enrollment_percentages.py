import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from education.models import Enrollment, Group

def run():
    print("Fixing mismatch percentages in Enrollments...")
    fixed_count = 0
    groups = Group.objects.all()
    
    for group in groups:
        enrollments = Enrollment.objects.filter(group=group)
        for enr in enrollments:
            if enr.oqituvchi_foiz != group.oqituvchi_foiz:
                print(f"Mismatch found: Student {enr.student.get_full_name()} in '{group.nom}' - "
                      f"Enrollment %: {enr.oqituvchi_foiz}, Group %: {group.oqituvchi_foiz}")
                enr.oqituvchi_foiz = group.oqituvchi_foiz
                enr.save(update_fields=['oqituvchi_foiz'])
                fixed_count += 1
                
    print(f"Successfully fixed {fixed_count} mismatching enrollments!")

if __name__ == '__main__':
    run()
