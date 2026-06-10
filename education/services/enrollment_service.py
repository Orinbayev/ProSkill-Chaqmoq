from django.utils import timezone
from education.models import (
    Enrollment, StudentGroupHistory, Group
)
from education.services.tuition import (
    resolve_lesson_schedule,
    ensure_all_tuition_months_since_start,
)
from django.db import transaction

class EnrollmentService:
    @staticmethod
    @transaction.atomic
    def enroll_student(
        student,
        group,
        kurs_narxi=None,
        oqituvchi_foiz=None,
        student_payable_amount=None,
        start_date=None,
        lesson_pattern=None,
        monthly_lessons=None,
    ):
        """Enrolls a student in a group and creates a history record."""
        # Use provided rates or fall back to group defaults
        narx = kurs_narxi if kurs_narxi is not None else group.kurs_narxi
        foiz = oqituvchi_foiz if oqituvchi_foiz is not None else group.oqituvchi_foiz
        schedule_meta = resolve_lesson_schedule(start_date or timezone.localdate(), lesson_pattern)
        history_start_date = schedule_meta["start_date"]
        resolved_monthly_lessons = int(monthly_lessons or getattr(group, "oy_dars_soni", 0) or 12)
        pattern = schedule_meta["lesson_pattern"]
        # Agar guruhda GroupSchedule bo'lsa, har doim "group" pattern ishlatiladi.
        # "odd"/"even" auto-detect GroupSchedule ni bypass qilib noto'g'ri hisob beradi.
        from education.models import GroupSchedule as _GS
        if pattern not in ("group",) and _GS.objects.filter(group=group).exists():
            pattern = Enrollment.LESSON_PATTERN_GROUP
        
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
                is_active=True,
                joined_at=history_start_date,
                monthly_lessons=resolved_monthly_lessons,
                lesson_pattern=pattern,
            )
            created = True

        if not created and not enrollment.is_active:
            enrollment.is_active = True
            enrollment.kurs_narhi = narx
            enrollment.oqituvchi_foiz = foiz
            enrollment.joined_at = history_start_date
            enrollment.monthly_lessons = resolved_monthly_lessons
            enrollment.lesson_pattern = pattern
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

        # Yangi yoki qayta yoqilgan enrollment uchun: joined_at dan joriy oygacha
        # TuitionMonth'larni yaratamiz — retroactive (o'tgan oyga) ro'yxatga
        # olishda ham qarz to'g'ri ko'rinishi uchun.
        if created or reactivated:
            ensure_all_tuition_months_since_start(enrollment, timezone.localdate())

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
