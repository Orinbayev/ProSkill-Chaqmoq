"""
Management command: reset_center_to_april_debt

Berilgan center uchun active payment/allocation yozuvlarini soft-delete qilib,
faqat bitta oy bo'yicha qarz holatini qayta quradi.

Misol:
    python3 manage.py reset_center_to_april_debt --center-slug=test --month=2026-04
    python3 manage.py reset_center_to_april_debt --center-slug=test --month=2026-04 --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Center
from education.services.reset_center_debt_service import (
    collect_center_reset_summary,
    parse_target_month,
    reset_center_to_single_month_debt,
    verify_center_single_month_debt,
)


class Command(BaseCommand):
    help = (
        "Berilgan center uchun barcha active to'lovlarni tozalab, "
        "faqat ko'rsatilgan oy uchun debtor holatini qayta quradi."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--center-slug",
            required=True,
            help="Center slug. Masalan: test",
        )
        parser.add_argument(
            "--month",
            default="2026-04",
            help="Maqsad oy. Format: YYYY-MM. Default: 2026-04",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Hech narsa o'zgartirmaydi, faqat summary va kutilayotgan natijani chiqaradi.",
        )

    def handle(self, *args, **options):
        slug = (options["center_slug"] or "").strip()
        dry_run = bool(options["dry_run"])

        if not slug:
            raise CommandError("--center-slug majburiy.")

        try:
            target_month = parse_target_month(options["month"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        try:
            center = Center.objects.get(slug=slug)
        except Center.DoesNotExist as exc:
            available = ", ".join(Center.objects.order_by("slug").values_list("slug", flat=True))
            raise CommandError(
                f"Center topilmadi: {slug!r}. Mavjud sluglar: {available or 'yoq'}"
            ) from exc

        summary = collect_center_reset_summary(center, target_month)

        self.stdout.write("")
        self.stdout.write("=" * 72)
        self.stdout.write(
            self.style.WARNING(
                f"DESTRUCTIVE RESET: {center.name} (slug={center.slug}, id={center.id})"
            )
        )
        self.stdout.write(f"Maqsad oy: {target_month.isoformat()} ({target_month:%B %Y})")
        self.stdout.write(
            "Backup tavsiya etiladi: "
            "python3 manage.py dumpdata education.Payment education.PaymentAllocation "
            f"education.TuitionMonth --indent=2 > backup_before_reset_{center.slug}.json"
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Rejim: DRY-RUN"))
        self.stdout.write("-" * 72)
        self.stdout.write("Boshlang'ich summary:")
        self.stdout.write(f"  Active enrollments : {summary.active_enrollment_count}")
        self.stdout.write(f"  Active payments    : {summary.payment_count}")
        self.stdout.write(f"  Active allocations : {summary.allocation_count}")
        self.stdout.write(f"  Active tuition mons: {summary.tuition_month_count}")
        self.stdout.write(f"  Target month TMs   : {summary.target_month_tuition_count}")
        self.stdout.write(f"  Active payment sum : {summary.payment_sum:,} so'm")
        self.stdout.write(f"  Expected total debt: {summary.expected_total_debt:,} so'm")

        if summary.zero_fee_enrollments:
            self.stdout.write(self.style.ERROR("Fee 0 bo'lib qolgan enrollmentlar topildi:"))
            for row in summary.zero_fee_enrollments[:20]:
                self.stdout.write(
                    f"  - enrollment #{row['enrollment_id']}: "
                    f"{row['student']} [{row['group']}]"
                )
            raise CommandError(
                "Fee 0 bo'lgan enrollmentlar bor. Avval ularning oylik summasini to'g'rilang."
            )

        if dry_run:
            self.stdout.write("-" * 72)
            self.stdout.write("DRY-RUN natijasi:")
            self.stdout.write("  Payments/allocations active hisobdan chiqariladi.")
            self.stdout.write("  Enrollment.jami_tolangan = 0 qilinadi.")
            self.stdout.write(
                f"  Har bir active enrollment uchun {target_month.isoformat()} TuitionMonth qoldiriladi."
            )
            self.stdout.write("  Boshqa oylar debt/pay ta'siridan chiqariladi.")
            self.stdout.write("=" * 72)
            return

        with transaction.atomic():
            result = reset_center_to_single_month_debt(center, target_month)
            verification = verify_center_single_month_debt(center, target_month)

            self.stdout.write("-" * 72)
            self.stdout.write("Amalga oshirilgan o'zgarishlar:")
            self.stdout.write(f"  Soft-deleted payments    : {result['payments_deleted']}")
            self.stdout.write(f"  Soft-deleted allocations : {result['allocations_deleted']}")
            self.stdout.write(f"  Soft-deleted tuition mons: {result['tuition_months_deleted']}")
            self.stdout.write(f"  Target month created     : {result['target_month_created']}")
            self.stdout.write(f"  Target month restored    : {result['target_month_restored']}")
            self.stdout.write(f"  Target month updated     : {result['target_month_updated']}")

            self.stdout.write("-" * 72)
            self.stdout.write("Verification:")
            self.stdout.write(
                f"  {'OK' if verification.remaining_payments == 0 else 'FAIL'} active payments    : "
                f"{verification.remaining_payments} (kerak: 0)"
            )
            self.stdout.write(
                f"  {'OK' if verification.remaining_allocations == 0 else 'FAIL'} active allocations : "
                f"{verification.remaining_allocations} (kerak: 0)"
            )
            self.stdout.write(
                f"  {'OK' if verification.target_month_tuition_count == verification.active_enrollment_count else 'FAIL'} "
                f"target month TMs   : {verification.target_month_tuition_count} "
                f"(active enrollment: {verification.active_enrollment_count})"
            )
            self.stdout.write(
                f"  {'OK' if verification.debtor_count == verification.active_enrollment_count else 'FAIL'} "
                f"debtor count       : {verification.debtor_count} "
                f"(active enrollment: {verification.active_enrollment_count})"
            )
            self.stdout.write(
                f"  {'OK' if verification.total_debt == verification.expected_total_debt else 'FAIL'} "
                f"total debt         : {verification.total_debt:,} so'm "
                f"(expected: {verification.expected_total_debt:,} so'm)"
            )

            if (
                verification.remaining_payments != 0
                or verification.remaining_allocations != 0
                or verification.debtor_count != verification.active_enrollment_count
                or verification.total_debt != verification.expected_total_debt
            ):
                raise CommandError("Verification muvaffaqiyatsiz tugadi. Transaction rollback qilindi.")

        self.stdout.write("-" * 72)
        self.stdout.write(self.style.SUCCESS("Reset muvaffaqiyatli yakunlandi."))
        self.stdout.write(f"Tekshirish URLlari: /{center.slug}/talim/tolovlar/ va /{center.slug}/talim/qarzdorlar/")
        self.stdout.write("=" * 72)
