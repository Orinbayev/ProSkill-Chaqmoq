from django.core.management.base import BaseCommand

from core.services.db_backup_service import backup_and_send_all_centers


class Command(BaseCommand):
    help = "Create PostgreSQL backups for all active centers and send them to Telegram."

    def handle(self, *args, **options):
        summary = backup_and_send_all_centers()
        self.stdout.write(
            self.style.SUCCESS(
                "Backup finished: "
                f"total={summary['total']} "
                f"backed_up={summary['backed_up']} "
                f"sent={summary['sent']} "
                f"combined_sent={summary.get('combined_sent', 0)} "
                f"skipped={summary['skipped']} "
                f"failed={summary['failed']}"
            )
        )
