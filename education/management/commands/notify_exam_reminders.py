from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_date

from education.services.exam_service import scan_and_notify_due_exams


class Command(BaseCommand):
    help = (
        "Imtihon muddati yetgan guruhlar bo'yicha o'qituvchilarga "
        "Telegram/in-app eslatma yuboradi (kunlik cron uchun)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--center-id",
            type=int,
            default=None,
            help="Faqat shu markaz (ixtiyoriy)",
        )
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="Hisob sanasi YYYY-MM-DD (default: bugun)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Dedupe'ni e'tiborsiz qoldirib qayta yuboradi",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Yubormasdan faqat due guruhlarni ko'rsatadi",
        )

    def handle(self, *args, **options):
        on_date = parse_date(options["date"]) if options.get("date") else timezone.localdate()
        if options.get("date") and on_date is None:
            self.stderr.write(self.style.ERROR("Noto'g'ri --date formati. YYYY-MM-DD ishlating."))
            return

        center = None
        center_id = options.get("center_id")
        if center_id:
            from accounts.models import Center

            center = Center.objects.filter(pk=center_id).first()
            if center is None:
                self.stderr.write(self.style.ERROR(f"Center topilmadi: id={center_id}"))
                return

        if options.get("dry_run"):
            from education.models import Group
            from education.services.exam_service import get_exam_reminder_state

            qs = Group.objects.filter(
                is_archived=False,
                is_deleted=False,
                is_closed=False,
                center__exam_settings__exam_system_enabled=True,
            ).select_related("center", "oqituvchi")
            if center is not None:
                qs = qs.filter(center=center)

            due_count = 0
            for group in qs:
                state = get_exam_reminder_state(group=group, on_date=on_date)
                if not state.get("due"):
                    continue
                due_count += 1
                teacher = group.oqituvchi
                teacher_label = (
                    f"{teacher_id(teacher)} tg={bool(getattr(teacher, 'telegram_id', None))}"
                    if teacher
                    else "no-teacher"
                )
                self.stdout.write(
                    f"DUE group={group.id} {group.nom!r} "
                    f"lesson={state.get('lesson_number')} "
                    f"checkpoint={state.get('target_lesson_number')} "
                    f"reason={state.get('reason')} teacher={teacher_label}"
                )
            self.stdout.write(self.style.SUCCESS(f"Dry-run: {due_count} ta due guruh ({on_date})"))
            return

        result = scan_and_notify_due_exams(
            center=center,
            on_date=on_date,
            force=bool(options.get("force")),
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Exam reminders: sent={result['sent']} skipped={result['skipped']} "
                f"errors={result['errors']} date={on_date}"
            )
        )


def teacher_id(teacher) -> str:
    return f"{teacher.id}:{getattr(teacher, 'email', '')}"
