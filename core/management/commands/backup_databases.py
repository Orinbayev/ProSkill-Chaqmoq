import sys

from django.core.management.base import BaseCommand

from core.services.db_backup_service import create_database_backups


class Command(BaseCommand):
    help = "Global DB va har bir markaz backup faylini backups/ papkasiga yaratadi."

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
            help="Global database backupni o'tkazib yuboradi.",
        )
        parser.add_argument(
            "--no-centers",
            action="store_true",
            default=False,
            help="Markaz backup fayllarini o'tkazib yuboradi.",
        )

    def handle(self, *args, **options):
        center_slugs = [s.strip() for s in options["center"].split(",") if s.strip()]
        summary = create_database_backups(
            center_slugs=center_slugs or None,
            include_global=not options["no_global"],
            include_centers=not options["no_centers"],
        )

        for item in summary.get("artifacts", []):
            size_kb = int((item.get("size") or 0) / 1024)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Yaratildi: {item['name']} ({size_kb} KB) [{item.get('scope')}/{item.get('kind')}]"
                )
            )

        if summary.get("errors"):
            for error in summary["errors"]:
                self.stderr.write(self.style.ERROR(f"❌ {error}"))

        self.stdout.write(
            self.style.SUCCESS(
                "Backup yakunlandi: "
                f"files={len(summary.get('files', []))} "
                f"backed_up={summary.get('backed_up', 0)} "
                f"failed={summary.get('failed', 0)}"
            )
        )

        if summary.get("failed"):
            sys.exit(1)
