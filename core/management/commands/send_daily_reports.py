from django.core.management.base import BaseCommand

from accounts.models import Center
from telegram_bot.reports import send_daily_report


class Command(BaseCommand):
    help = "Faol markazlar direktorlari uchun kunlik Telegram hisobot yuboradi."

    def handle(self, *args, **options):
        sent_count = 0
        for center in Center.objects.filter(status=Center.STATUS_ACTIVE, is_deleted=False):
            if not center.director_telegram_id:
                continue
            if send_daily_report(center):
                sent_count += 1
                self.stdout.write(self.style.SUCCESS(f"Hisobot yuborildi: {center.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Hisobot yuborilmadi: {center.name}"))
        self.stdout.write(self.style.SUCCESS(f"Jami yuborilgan hisobotlar: {sent_count}"))
