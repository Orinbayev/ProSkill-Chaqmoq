from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from accounts.auth_helpers import find_login_users
from accounts.models import Center


class Command(BaseCommand):
    help = "Email/telefon/login bo'yicha user parolini xavfsiz reset qiladi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--identifier",
            required=True,
            help="Email, telefon yoki login identifikatori",
        )
        parser.add_argument("--new-password", required=True, help="Yangi parol")
        parser.add_argument("--center-slug", help="Ixtiyoriy markaz slug'i")
        parser.add_argument(
            "--activate",
            action="store_true",
            help="Reset bilan birga is_active=True qiladi",
        )

    def handle(self, *args, **options):
        identifier = str(options["identifier"]).strip()
        new_password = str(options["new_password"])
        center_slug = str(options.get("center_slug") or "").strip()

        center = None
        if center_slug:
            center = Center.objects.filter(slug=center_slug, is_deleted=False).first()
            if center is None:
                raise CommandError(f"Markaz topilmadi: {center_slug}")

        candidates = list(find_login_users(identifier, center=center, active_only=False))
        if not candidates:
            raise CommandError("Mos user topilmadi.")
        if len(candidates) > 1:
            lines = [
                f"id={user.id} email={user.email} center={getattr(user.center, 'slug', '-') or '-'} role={user.role}"
                for user in candidates
            ]
            raise CommandError(
                "Bir nechta user topildi. Aniqlik uchun center slug bilan qayta urinib ko'ring:\n"
                + "\n".join(lines),
            )

        user = candidates[0]
        user.set_password(new_password)
        if options["activate"]:
            user.is_active = True
            user.save(update_fields=["password", "is_active"])
        else:
            user.save(update_fields=["password"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Parol yangilandi: id={user.id} email={user.email} "
                f"role={user.role} center={getattr(user.center, 'slug', '-') or '-'}",
            ),
        )
