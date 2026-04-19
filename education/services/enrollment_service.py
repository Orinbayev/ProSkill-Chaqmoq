from django.utils import timezone
from education.models import (
    Enrollment, StudentGroupHistory, Group
)
from django.db import transaction

class EnrollmentService:
    @staticmethod
    @transaction.atomic
    def enroll_student(student, group, kurs_narxi=None, oqituvchi_foiz=None, student_payable_amount=None, start_date=None):
        """Enrolls a student in a group and creates a history record."""
        # Use provided rates or fall back to group defaults
        narx = kurs_narxi if kurs_narxi is not None else group.kurs_narxi
        foiz = oqituvchi_foiz if oqituvchi_foiz is not None else group.oqituvchi_foiz
        history_start_date = start_date or timezone.localdate()
        
        # Use all_objects to check if a soft-deleted enrollment exists (Fix for IntegrityError)
        enrollment = Enrollment.all_objects.filter(student=student, group=group).first()
        created = False
        reactivated = False
        
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
                student_payable_amount=student_payable_amount,
                center=group.center,
                is_active=True
            )
            created = True

        if not created and not enrollment.is_active:
            enrollment.is_active = True
            enrollment.kurs_narhi = narx
            enrollment.oqituvchi_foiz = foiz
            if student_payable_amount is not None:
                enrollment.student_payable_amount = student_payable_amount
            enrollment.save()
            reactivated = True
        
        open_history = StudentGroupHistory.objects.filter(
            student=student,
            group=group,
            end_date__isnull=True,
        ).order_by("-start_date").first()

        if created or reactivated:
            if open_history:
                open_history.start_date = history_start_date
                open_history.kurs_narxi = narx
                open_history.oqituvchi_foiz = foiz
                open_history.save(update_fields=["start_date", "kurs_narxi", "oqituvchi_foiz"])
            else:
                StudentGroupHistory.objects.create(
                    student=student,
                    group=group,
                    center=group.center,
                    start_date=history_start_date,
                    kurs_narxi=narx,
                    oqituvchi_foiz=foiz
                )
        elif not open_history:
            StudentGroupHistory.objects.create(
                student=student,
                group=group,
                center=group.center,
                start_date=history_start_date,
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
