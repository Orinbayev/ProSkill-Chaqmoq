"""
python manage.py backup_and_send
   --center slug1,slug2   (ixtiyoriy: faqat ushbu markazlar)
   --dry-run              (ixtiyoriy: backup yaratadi, lekin Telegram ga yubormaydi)
   --no-full              (ixtiyoriy: to'liq PostgreSQL dump o'tkazib yuboriladi)
"""

import sys

from django.core.management.base import BaseCommand

from core.services.db_backup_service import (
    backup_and_send_all_centers,
    export_center_snapshot,
    send_file_to_telegram,
)
from accounts.models import Center
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Barcha aktiv markazlar uchun backup yaratadi va Telegram guruhga yuboradi. "
        "Render Cron Job va qo'lda test uchun."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--center",
            type=str,
            default="",
            help="Vergul bilan ajratilgan markaz slug'lari (bo'sh = barcha aktiv markazlar)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Backup yaratadi lekin Telegram ga YUBORMAYDI",
        )
        parser.add_argument(
            "--no-full",
            action="store_true",
            default=False,
            help="To'liq PostgreSQL dump o'tkazib yuboriladi",
        )

    def handle(self, *args, **options):
        center_slugs = [s.strip() for s in options["center"].split(",") if s.strip()]
        dry_run = options["dry_run"]
        no_full = options["no_full"]

        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  DRY-RUN rejimi: Telegram ga yuborilmaydi"))

        # ── Faqat belgilangan markazlar uchun ──────────────────────────────
        if center_slugs:
            self._run_for_centers(center_slugs, dry_run)
            return

        # ── Barcha markazlar uchun standart job ────────────────────────────
        if dry_run or no_full:
            # Oddiy run emas – qo'lda boshqaramiz
            centers = list(
                Center.objects.filter(status=Center.STATUS_ACTIVE).order_by("id")
            )
            self.stdout.write(f"Aktiv markazlar: {len(centers)} ta")
            date_str = timezone.localdate().isoformat()
            sent = 0
            failed = 0
            for center in centers:
                try:
                    path = export_center_snapshot(center)
                    self.stdout.write(f"  📦 Yaratildi: {path.name}")
                    if not dry_run:
                        caption = (
                            f"📦 Markaz backup\n"
                            f"🏢 {center.name} ({center.slug})\n"
                            f"📅 {date_str}\n"
                            f"📁 {path.name}"
                        )
                        send_file_to_telegram(path, caption=caption)
                        self.stdout.write(self.style.SUCCESS(f"  ✅ Yuborildi: {path.name}"))
                        sent += 1
                    else:
                        self.stdout.write(f"  [dry-run] Yuborilmadi: {path.name}")
                except Exception as exc:
                    failed += 1
                    self.stderr.write(self.style.ERROR(f"  ❌ XATO [{center.slug}]: {exc}"))
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nYakunlandi: sent={sent} failed={failed} (dry_run={dry_run})"
                )
            )
            return

        # ── To'liq standart run ────────────────────────────────────────────
        summary = backup_and_send_all_centers()
        if summary["failed"] > 0:
            error_detail = (
                summary.get("fatal_error")
                or ", ".join(summary.get("failed_centers", []))
                or "noma'lum xato"
            )
            self.stderr.write(
                self.style.ERROR(
                    f"❌ {summary['failed']} ta xato: {error_detail}"
                )
            )
            sys.exit(1)

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Backup tugadi: "
                f"total={summary['total']} "
                f"backed_up={summary['backed_up']} "
                f"sent={summary['sent']} "
                f"full_sent={summary.get('full_sent', 0)} "
                f"skipped={summary['skipped']} "
                f"failed={summary['failed']}"
            )
        )

    def _run_for_centers(self, slugs: list[str], dry_run: bool) -> None:
        date_str = timezone.localdate().isoformat()
        for slug in slugs:
            try:
                center = Center.objects.get(slug=slug)
            except Center.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Markaz topilmadi: {slug}"))
                continue
            try:
                path = export_center_snapshot(center)
                self.stdout.write(f"📦 Yaratildi: {path.name}")
                if not dry_run:
                    caption = (
                        f"📦 Markaz backup\n"
                        f"🏢 {center.name} ({center.slug})\n"
                        f"📅 {date_str}\n"
                        f"📁 {path.name}"
                    )
                    send_file_to_telegram(path, caption=caption)
                    self.stdout.write(self.style.SUCCESS(f"✅ Yuborildi: {path.name}"))
                else:
                    self.stdout.write(f"[dry-run] Yuborilmadi: {path.name}")
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"❌ XATO [{slug}]: {exc}"))
