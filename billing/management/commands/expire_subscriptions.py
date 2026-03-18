from django.core.management.base import BaseCommand
from django.utils import timezone

from billing.models import Subscription


class Command(BaseCommand):
    help = "Deactivate expired user subscriptions (cron-ready)."

    def handle(self, *args, **options):
        today = timezone.localdate()
        expired_qs = Subscription.objects.filter(is_active=True, end_date__lt=today)
        expired_count = expired_qs.count()
        expired_qs.update(is_active=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Expired subscriptions deactivated: {expired_count}"
            )
        )
