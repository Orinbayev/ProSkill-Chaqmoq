"""
seed_landing — marketing/landing kontent uchun idempotent seed command.
seed_marketing_data ni chaqiradi, lekin faqat yo'q bo'lgan ma'lumotlarni yaratadi.
Usage:
    python manage.py seed_landing
    python manage.py seed_landing --idempotent  (same thing, alias)
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Landing page uchun default kontentni yaratadi (idempotent — mavjudini o'zgartirmaydi)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--idempotent",
            action="store_true",
            help="Render build command uchun alias flag (xatti-harakat o'zgarmaydi)",
        )

    def handle(self, *args, **options):
        self.stdout.write("Landing seed boshlandi...")
        call_command("seed_marketing_data")
        self.stdout.write(self.style.SUCCESS("Landing seed tugadi. Barcha default kontent tayyor."))
