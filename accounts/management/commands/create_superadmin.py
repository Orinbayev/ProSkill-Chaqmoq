from django.core.management.base import BaseCommand
from accounts.models import User


class Command(BaseCommand):
    help = "Superadmin yaratadi yoki mavjudini yangilaydi (is_staff, is_superuser, parol)"

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Superadmin email")
        parser.add_argument("--password", required=True, help="Superadmin parol")
        parser.add_argument("--ism", default="Super", help="Ism (ixtiyoriy)")
        parser.add_argument("--familya", default="Admin", help="Familya (ixtiyoriy)")

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "ism": options["ism"],
                "familya": options["familya"],
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )

        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        action = "Yaratildi" if created else "Yangilandi"
        self.stdout.write(self.style.SUCCESS(
            f"{action}: {email} → /admin/ ga kirishingiz mumkin"
        ))
