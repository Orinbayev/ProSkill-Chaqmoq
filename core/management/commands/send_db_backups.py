import sys

from django.core.management.base import BaseCommand

from core.services.db_backup_service import send_database_backups_to_telegram


class Command(BaseCommand):
    help = "Real-time DB backup yaratadi va Telegram backup guruhiga yuboradi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--center",
            type=str,
            default="",
            help="Vergul bilan ajratilgan markaz sluglari. Bo'sh bo'lsa barcha markazlar olinadi.",
        )
        parser.add_argument(
            "--no-global",
            action="store_true",
            default=False,
            help="Global database backupni yubormaydi.",
        )
        parser.add_argument(
            "--no-centers",
            action="store_true",
            default=False,
            help="Markaz backup fayllarini yubormaydi.",
        )
        parser.add_argument(
            "--send-zip",
            action="store_true",
            default=False,
            help="Alohida fayllardan tashqari all_databases_backup_*.zip ham yuboradi.",
        )
        parser.add_argument(
            "--zip-only",
            action="store_true",
            default=False,
            help="Faqat all_databases_backup_*.zip faylini yuboradi.",
        )

    def handle(self, *args, **options):
        center_slugs = [s.strip() for s in options["center"].split(",") if s.strip()]
        summary = send_database_backups_to_telegram(
            center_slugs=center_slugs or None,
            include_global=not options["no_global"],
            include_centers=not options["no_centers"],
            send_zip=options["send_zip"],
            zip_only=options["zip_only"],
        )

        for file_path in summary.get("sent_files", []):
            self.stdout.write(self.style.SUCCESS(f"✅ Telegramga yuborildi: {file_path}"))

        if summary.get("errors"):
            for error in summary["errors"]:
                self.stderr.write(self.style.ERROR(f"❌ {error}"))

        if summary.get("fatal_error"):
            self.stderr.write(self.style.ERROR(f"❌ {summary['fatal_error']}"))

        self.stdout.write(
            self.style.SUCCESS(
                "Send yakunlandi: "
                f"sent={summary.get('sent', 0)} "
                f"files={len(summary.get('files', []))} "
                f"failed={summary.get('failed', 0)}"
            )
        )

        if summary.get("failed"):
            sys.exit(1)
