"""
Barcha filiallarning noto'g'ri subscriptionlarini o'chiradi.

Ishlatish:
  python manage.py fix_branch_subscriptions
"""
from django.core.management.base import BaseCommand
from accounts.models import Center
from billing.models import CenterSubscription


class Command(BaseCommand):
    help = "Filiallardagi noto'g'ri subscriptionlarni o'chiradi"

    def handle(self, *args, **options):
        branches = Center.objects.filter(
            parent_center__isnull=False,
            is_deleted=False,
        )
        self.stdout.write(f"Filiallar: {branches.count()} ta")

        total_deleted = 0
        for branch in branches:
            own_subs = CenterSubscription.objects.filter(center=branch)
            count = own_subs.count()
            if count:
                own_subs.delete()
                total_deleted += count
                self.stdout.write(
                    f"  ✓ {branch.name} (ID={branch.id}): "
                    f"{count} ta subscription o'chirildi → "
                    f"endi '{branch.parent_center.name}' tarifidan foydalanadi"
                )

        if total_deleted == 0:
            self.stdout.write("Tuzatish kerak bo'lgan narsa topilmadi.")
        else:
            self.stdout.write(f"\nJami {total_deleted} ta subscription o'chirildi.")
        self.stdout.write("Tayyor!")
