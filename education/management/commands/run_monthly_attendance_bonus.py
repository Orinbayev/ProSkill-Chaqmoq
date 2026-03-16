import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from education.models import Enrollment, Attendance, Student
from chaqmoq.models import LightningHistory, Rule
from django.db.models import Count, Q

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Oy yakunida o'quvchilarga davomat bonusi yoki jarimasini hisoblash"

    def handle(self, *args, **kwargs):
        # 1. O'tgan oyni aniqlaymiz:
        # Masalan, hozir 1-Aprel bo'lsa, davomat Mart oyi uchun hisoblanadi.
        now = timezone.localtime(timezone.now())
        first_day_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day_of_prev_month = first_day_of_this_month - timedelta(days=1)
        prev_month = last_day_of_prev_month.month
        prev_year = last_day_of_prev_month.year

        self.stdout.write(f"Boshlanmoqda... {prev_year}-{prev_month:02d} oyi uchun tahlil.")

        # 2. Barcha aktiv enrollments
        enrollments = Enrollment.objects.filter(is_active=True).select_related('student', 'group', 'group__center')
        
        bonus_count = 0
        penalty_count = 0
        
        for enr in enrollments:
            student_user = enr.student
            group = enr.group
            center = group.center

            student_model, _ = Student.objects.get_or_create(user=student_user)

            # O'sha oydagi davomatlar 
            attendances = Attendance.objects.filter(
                group=group,
                student=student_user,
                date__year=prev_year,
                date__month=prev_month
            )

            # 'present' (KELGAN) bo'lganlar soni (Eski logikani ham inobatga olamiz: present=True)
            present_qs = attendances.filter(Q(status="present") | Q(present=True))
            present_count = present_qs.count()

            # 'absent_unexcused' (SABABSIZ KELMAGAN) soni (forced=True ham sababsiz hisoblanadi)
            unexcused_qs = attendances.filter(Q(status="absent_unexcused") | Q(status="forced") | Q(forced=True))
            unexcused_count = unexcused_qs.count()

            # Qoidalar
            rules = Rule.objects.filter(Q(center=center) | Q(center__isnull=True))
            
            # --- BONUS ---
            # Qoida bo'yicha presence_limit (default 12)
            bonus_rule = rules.filter(tur=Rule.ATTENDANCE_BONUS).first()
            limit_b = bonus_rule.presence_limit if bonus_rule and bonus_rule.presence_limit else 12
            bonus_points = bonus_rule.lightning_bonus if bonus_rule and bonus_rule.lightning_bonus else 10
            
            if present_count >= limit_b:
                # Agar shu oy uchun allaqachon bonus berilmagan bo'lsa
                reason_text = f"{prev_year}-{prev_month:02d} oyi davomati uchun ({present_count} marta)"
                exists = LightningHistory.objects.filter(
                    student=student_model, 
                    source="bonus", 
                    reason=reason_text
                ).exists()
                
                if not exists:
                    LightningHistory.objects.create(
                        student=student_model,
                        points=bonus_points,
                        reason=reason_text,
                        source="bonus"
                    )
                    bonus_count += 1
                    self.stdout.write(f"Bonus yozildi: {student_user.get_full_name()} (+{bonus_points})")

            # --- PENALTY ---
            # Qoida bo'yicha absence_limit (default 3)
            penalty_rule = rules.filter(tur=Rule.ATTENDANCE_PENALTY).first()
            limit_p = penalty_rule.absence_limit if penalty_rule and penalty_rule.absence_limit else 3
            penalty_points = penalty_rule.lightning_penalty if penalty_rule and penalty_rule.lightning_penalty else -50
            if penalty_points > 0:
                penalty_points = -penalty_points  # ensure negative

            if unexcused_count >= limit_p:
                reason_text = f"{prev_year}-{prev_month:02d} oyi sababsiz qoldirish ({unexcused_count} marta)"
                exists = LightningHistory.objects.filter(
                    student=student_model, 
                    source="penalty", 
                    reason=reason_text
                ).exists()
                
                if not exists:
                    LightningHistory.objects.create(
                        student=student_model,
                        points=penalty_points,
                        reason=reason_text,
                        source="penalty"
                    )
                    penalty_count += 1
                    self.stdout.write(f"Jarima yozildi: {student_user.get_full_name()} ({penalty_points})")

        self.stdout.write(self.style.SUCCESS(f"Tugadi. Jami: {bonus_count} bonus, {penalty_count} jarima kiritildi."))
