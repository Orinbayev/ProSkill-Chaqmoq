from django.core.management.base import BaseCommand
from django.utils import timezone

from chaqmoq.models import Ledger, LightningHistory, Rule
from education.models import Student


class Command(BaseCommand):
    help = "Legacy Ledger yozuvlarini LightningHistory ga ko'chiradi (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--center-id", type=int, default=None, help="Faqat bitta center uchun")
        parser.add_argument("--dry-run", action="store_true", help="Yozmaydi, faqat hisoblaydi")

    def _map_source(self, ledger_obj: Ledger) -> str:
        if ledger_obj.rule and ledger_obj.rule.tur == Rule.ATTENDANCE_BONUS:
            return "bonus"
        if ledger_obj.rule and ledger_obj.rule.tur == Rule.ATTENDANCE_PENALTY:
            return "penalty"
        return "manual"

    def handle(self, *args, **options):
        center_id = options.get("center_id")
        dry_run = bool(options.get("dry_run"))

        ledgers = Ledger.objects.select_related("student", "beruvchi", "rule")
        if center_id:
            ledgers = ledgers.filter(student__center_id=center_id)

        total = 0
        created = 0
        skipped = 0

        for l in ledgers.iterator(chunk_size=1000):
            total += 1

            student_user = l.student
            student_model, _ = Student.objects.get_or_create(
                user=student_user,
                defaults={"center": getattr(student_user, "center", None)},
            )

            source = self._map_source(l)
            reason = l.rule_nom or (l.rule.nom if l.rule_id else "Manual change")

            event_dt = getattr(l, "created_at", None) or l.sana or timezone.now()
            if timezone.is_naive(event_dt):
                event_dt = timezone.make_aware(event_dt, timezone.get_current_timezone())

            exists = LightningHistory.objects.filter(
                student=student_model,
                points=l.ball,
                reason=reason,
                source=source,
                teacher=l.beruvchi,
                created_at=event_dt,
            ).exists()
            if exists:
                skipped += 1
                continue

            if dry_run:
                created += 1
                continue

            obj = LightningHistory.objects.create(
                student=student_model,
                points=l.ball,
                reason=reason,
                source=source,
                teacher=l.beruvchi,
            )
            # Auto_now_add sababli timestampni alohida update qilamiz.
            LightningHistory.objects.filter(pk=obj.pk).update(created_at=event_dt)
            created += 1

        mode = "DRY-RUN" if dry_run else "DONE"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: total={total}, created={created}, skipped={skipped}, center_id={center_id or 'ALL'}"
            )
        )
