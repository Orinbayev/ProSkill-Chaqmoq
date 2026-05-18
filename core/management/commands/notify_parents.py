from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.dashboard_metrics import attendance_present_filter
from education.models import Attendance, Enrollment
from telegram_bot.parent_notify import notify_low_attendance, notify_payment_due


class Command(BaseCommand):
    help = "Ota-onalarga to'lov yoki davomat bo'yicha Telegram eslatma yuboradi."

    def add_arguments(self, parser):
        parser.add_argument("--type", dest="notify_type", choices=["payment", "attendance"], required=True)

    def handle(self, *args, **options):
        notify_type = options["notify_type"]
        if notify_type not in {"payment", "attendance"}:
            raise CommandError("--type payment yoki attendance bo'lishi kerak.")

        enrollments = Enrollment.objects.filter(
            is_active=True,
            is_deleted=False,
            student__is_archived=False,
            group__is_archived=False,
            group__is_deleted=False,
        ).select_related("student", "group", "center")

        sent_count = 0
        if notify_type == "payment":
            for enrollment in enrollments:
                if notify_payment_due(enrollment):
                    sent_count += 1
            self.stdout.write(self.style.SUCCESS(f"To'lov eslatmalari yuborildi: {sent_count}"))
            return

        date_to = timezone.localdate()
        date_from = date_to - timedelta(days=6)
        present_filter = attendance_present_filter()
        for enrollment in enrollments:
            att_qs = Attendance.objects.filter(
                group=enrollment.group,
                student=enrollment.student,
                date__range=(date_from, date_to),
            )
            total = att_qs.count()
            if total <= 0:
                continue
            attended = att_qs.filter(present_filter).count()
            if notify_low_attendance(enrollment, attended, total):
                sent_count += 1

        self.stdout.write(self.style.SUCCESS(f"Davomat eslatmalari yuborildi: {sent_count}"))
