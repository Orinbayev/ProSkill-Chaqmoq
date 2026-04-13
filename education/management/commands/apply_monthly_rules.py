from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from chaqmoq.services import check_attendance_penalty, check_attendance_bonus
from education.models import Enrollment

User = get_user_model()

class Command(BaseCommand):
    help = "Har oyning boshida o'tgan oy uchun davomat jarimasi va bonuslarini qo'llaydi."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-date',
            type=str,
            help='Ma\'lum bir sanani ko\'rsatish (YYYY-MM-DD). Test uchun juda qulay.',
        )

    def handle(self, *args, **options):
        # Agar sana berilmagan bo'lsa - bugun olinadi
        if options['force_date']:
            now = timezone.datetime.strptime(options['force_date'], '%Y-%m-%d').date()
        else:
            now = timezone.localdate()
            if now.day != 1:
                self.stdout.write("Bugun oyning 1-sanasi emas. Davomat oylik qoidalari o'tkazib yuborildi.")
                return

        # O'tgan oyning istalgan kuni (masalan, o'tgan oyning oxirgi kuni)
        # 1-sanada ishlayotganimiz uchun 1 kun orqaga qaytsak o'tgan oyga o'tamiz
        reference_date = now.replace(day=1) - timedelta(days=1)
        
        self.stdout.write(f"Processing rules for: {reference_date.strftime('%B %Y')}")
        
        # Faqat faol enrollmentdagi o'quvchilar. Bitta o'quvchi bir nechta guruhda
        # bo'lsa ham oy uchun bir marta tekshiriladi.
        student_ids = (
            Enrollment.objects.filter(is_active=True)
            .values_list("student_id", flat=True)
            .distinct()
        )
        students = User.objects.filter(id__in=student_ids, role='student')
        
        p_count = 0
        b_count = 0
        
        for student in students:
            # Markaz (studentning markazi modeli qanday bo'lsa shunday olinadi)
            center = getattr(student, 'center', None)
            
            # 1. Jarimani tekshirish
            if check_attendance_penalty(student=student, center=center, target_date=reference_date):
                p_count += 1
            
            # 2. Bonusni tekshirish
            if check_attendance_bonus(student=student, center=center, target_date=reference_date):
                b_count += 1
                
        self.stdout.write(self.style.SUCCESS(
            f"Bajarildi! O'tgan oy uchun {p_count} ta jarima va {b_count} ta bonus hisoblandi."
        ))
