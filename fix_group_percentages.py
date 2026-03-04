import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from education.models import Group, Enrollment

def fix_all():
    print("Fixing mismatch group percentages...")
    groups = Group.objects.all()
    fixed_groups = 0
    fixed_enrollments = 0
    
    for g in groups:
        if g.oqituvchi and hasattr(g.oqituvchi, 'oqituvchi_foizi'):
            teacher_foiz = g.oqituvchi.oqituvchi_foizi
            if teacher_foiz is not None and g.oqituvchi_foiz != teacher_foiz:
                print(f"Fixing Group '{g.nom}': {g.oqituvchi_foiz}% -> {teacher_foiz}%")
                g.oqituvchi_foiz = teacher_foiz
                g.save(update_fields=['oqituvchi_foiz'])
                fixed_groups += 1

                # Update enrollments in this group to match the group's new teacher_foiz
                enrollments = Enrollment.objects.filter(group=g)
                for enr in enrollments:
                    if enr.oqituvchi_foiz != teacher_foiz:
                        enr.oqituvchi_foiz = teacher_foiz
                        enr.save(update_fields=['oqituvchi_foiz'])
                        fixed_enrollments += 1
                        
    print(f"Fixed {fixed_groups} groups and {fixed_enrollments} associated enrollments.")

if __name__ == '__main__':
    fix_all()
