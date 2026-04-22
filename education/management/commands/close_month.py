from __future__ import annotations

from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import Center
from education.models import Enrollment
from education.services.historical_finance_service import HistoricalFinanceService
from education.services.tuition import (
    attendance_based_fee,
    get_effective_month_fee,
    month_first_day,
    parse_month_str,
)


class Command(BaseCommand):
    help = (
        "Oyni production tartibida yopadi: active enrollmentlar reconcile qilinadi, "
        "teacher snapshotlar va finance snapshot yaratiladi. "
        "Chaqiriq misoli: python manage.py close_month 2026-04 --center 3"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "month",
            nargs="?",
            default=None,
            help="YYYY-MM formatida oy. Berilmasa — o'tgan oy olinadi.",
        )
        parser.add_argument(
            "--center",
            type=int,
            default=None,
            help="Faqat berilgan center ID uchun ishga tushiriladi.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Hech narsa saqlamay, faqat reconcile preview chiqaradi.",
        )

    def handle(self, *args, **options):
        target = self._resolve_month(options.get("month"))
        center_id = options.get("center")
        dry_run = bool(options.get("dry_run"))

        centers = self._resolve_centers(center_id)
        if not centers:
            raise CommandError("Close qilish uchun center topilmadi.")

        for center in centers:
            enrollments = (
                Enrollment.objects.filter(is_active=True)
                .filter(center=center)
                .select_related("group", "student")
            )
            total = enrollments.count()

            self.stdout.write(
                f"[close_month] Center={center.id} ({center.name}) | oy={target.isoformat()} | "
                f"enrollmentlar={total}"
                + (" | DRY-RUN" if dry_run else "")
            )

            if dry_run:
                self._print_preview(center, enrollments, target)
                continue

            fin_month = HistoricalFinanceService.close_month(center, target.year, target.month, user=None)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[close_month] Yakunlandi: {center.name} | "
                    f"financial_month_id={fin_month.id}"
                )
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN: hech narsa saqlanmadi."))

    def _resolve_centers(self, center_id):
        if center_id:
            center = Center.objects.filter(pk=center_id).first()
            return [center] if center else []

        center_ids = (
            Enrollment.objects.filter(is_active=True, center_id__isnull=False)
            .values_list("center_id", flat=True)
            .distinct()
        )
        return list(Center.objects.filter(id__in=center_ids).order_by("id"))

    def _print_preview(self, center, enrollments, month: date):
        changed = 0
        for enrollment in enrollments.iterator():
            current_fee = get_effective_month_fee(enrollment, month)
            reconciled_fee = attendance_based_fee(enrollment, month)
            if current_fee != reconciled_fee:
                changed += 1
                self.stdout.write(
                    f"  enr#{enrollment.pk} {enrollment.student.get_full_name()} "
                    f"({enrollment.group.nom}) | {current_fee:,} -> {reconciled_fee:,}"
                )
        self.stdout.write(
            f"  center={center.id} bo'yicha tafovutli enrollmentlar: {changed}"
        )

    def _resolve_month(self, raw) -> date:
        if raw:
            parsed = parse_month_str(raw)
            if not parsed:
                raise CommandError(
                    f"Noto'g'ri oy formati: '{raw}'. YYYY-MM kuting (masalan 2026-04)."
                )
            return parsed

        today = timezone.localdate()
        return month_first_day(today.replace(day=1) - timedelta(days=1))
