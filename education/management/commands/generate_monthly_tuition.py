from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from education.models import Enrollment
from education.services.tuition import ensure_tuition_month, month_first_day


class Command(BaseCommand):
    help = (
        "Har oyning 1-sanasida har bir faol Enrollment uchun TuitionMonth rekordini "
        "yaratadi (qarzdorlik o'sha sanadanoq to'g'ri ko'rinishi uchun)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-date",
            type=str,
            default="",
            help="YYYY-MM-DD shaklida sana berib test qilish. Bo'sh bo'lsa bugun olinadi.",
        )
        parser.add_argument(
            "--all-active",
            action="store_true",
            help=(
                "Sana 1-kun bo'lmasa ham, hamma faol enrollmentlar uchun joriy oyni "
                "majburiy tekshiradi."
            ),
        )

    def handle(self, *args, **options):
        if options["force_date"]:
            today = datetime.strptime(options["force_date"], "%Y-%m-%d").date()
        else:
            today = timezone.localdate()

        if today.day != 1 and not options["all_active"]:
            self.stdout.write(
                "Bugun oy boshi emas. Rejimlangan ish bajarilmadi. "
                "(--all-active bersangiz baribir ishlaydi.)"
            )
            return

        month = month_first_day(today)
        qs = (
            Enrollment.objects.filter(is_active=True, is_deleted=False)
            .select_related("group", "center")
        )
        created_or_synced = 0
        failed = 0
        for enrollment in qs.iterator(chunk_size=200):
            try:
                ensure_tuition_month(enrollment, month)
                created_or_synced += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    f"  ! enrollment#{enrollment.id} xato: {exc}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"TuitionMonth tayyorlandi: oy={month.isoformat()} "
                f"ok={created_or_synced} fail={failed}"
            )
        )
