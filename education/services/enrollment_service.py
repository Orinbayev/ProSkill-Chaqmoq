from django.utils import timezone
from education.models import (
    Enrollment, StudentGroupHistory, Group
)
from django.db import transaction

class EnrollmentService:
    @staticmethod
    @transaction.atomic
    def enroll_student(student, group, kurs_narxi=None, oqituvchi_foiz=None):
        """Enrolls a student in a group and creates a history record."""
        # Use provided rates or fall back to group defaults
        narx = kurs_narxi if kurs_narxi is not None else group.kurs_narxi
        foiz = oqituvchi_foiz if oqituvchi_foiz is not None else group.oqituvchi_foiz
        
        # Use all_objects to check if a soft-deleted enrollment exists (Fix for IntegrityError)
        enrollment = Enrollment.all_objects.filter(student=student, group=group).first()
        created = False
        
        if enrollment:
            # Resurrect if it was deleted
            if getattr(enrollment, 'is_deleted', False):
                enrollment.restore()
        else:
            enrollment = Enrollment.objects.create(
                student=student,
                group=group,
                kurs_narhi=narx,
                oqituvchi_foiz=foiz,
                center=group.center,
                is_active=True
            )
            created = True
        
        if not created and not enrollment.is_active:
            enrollment.is_active = True
            enrollment.kurs_narhi = narx
            enrollment.oqituvchi_foiz = foiz
            enrollment.save()
        
        # Create history record
        StudentGroupHistory.objects.create(
            student=student,
            group=group,
            center=group.center,
            start_date=timezone.localdate(),
            kurs_narxi=narx,
            oqituvchi_foiz=foiz
        )
        
        return enrollment

    @staticmethod
    @transaction.atomic
    def remove_student(student, group):
        """Removes student from group and closes the history record."""
        enrollment = Enrollment.objects.filter(student=student, group=group, is_active=True).first()
        if enrollment:
            enrollment.is_active = False
            enrollment.save()
            
        # Close the latest open history record
        history = StudentGroupHistory.objects.filter(
            student=student, 
            group=group, 
            end_date__isnull=True
        ).first()
        
        if history:
            history.end_date = timezone.localdate()
            history.save()

    @staticmethod
    @transaction.atomic
    def transfer_student(student, from_group, to_group):
        """Transfers a student from one group to another."""
        EnrollmentService.remove_student(student, from_group)
        return EnrollmentService.enroll_student(student, to_group)
