from __future__ import annotations

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from accounts.auth_helpers import (
    authenticate_login_identifier,
    find_login_users,
    mask_login_identifier,
    normalized_phone_candidate,
)
from accounts.models import Center


class Command(BaseCommand):
    help = "Mobil login uchun runtime config va foydalanuvchi diagnostikasini ko'rsatadi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--identifier",
            required=True,
            help="Email, telefon yoki login identifikatori",
        )
        parser.add_argument(
            "--password",
            help="Ixtiyoriy. Berilsa authenticate/check_password sinovi o'tadi",
        )
        parser.add_argument("--center-slug", help="Ixtiyoriy markaz slug'i")

    def handle(self, *args, **options):
        identifier = str(options["identifier"]).strip()
        password = str(options.get("password") or "")
        center_slug = str(options.get("center_slug") or "").strip()

        center = None
        if center_slug:
            center = Center.objects.filter(slug=center_slug, is_deleted=False).first()
            if center is None:
                raise CommandError(f"Markaz topilmadi: {center_slug}")

        db_settings = connection.settings_dict
        self.stdout.write(self.style.MIGRATE_HEADING("Runtime"))
        self.stdout.write(f"  DJANGO_SETTINGS_MODULE: {settings.SETTINGS_MODULE}")
        self.stdout.write(f"  MODE: {getattr(settings, 'MODE', 'n/a')}")
        self.stdout.write(f"  DEBUG: {settings.DEBUG}")
        self.stdout.write(f"  RENDER env: {'yes' if os.getenv('RENDER') else 'no'}")
        self.stdout.write(
            f"  DATABASE_URL env: {'set' if os.getenv('DATABASE_URL') else 'missing'}",
        )
        self.stdout.write(f"  DB ENGINE: {db_settings.get('ENGINE')}")
        self.stdout.write(f"  DB NAME: {db_settings.get('NAME')}")
        self.stdout.write(f"  DB HOST: {db_settings.get('HOST') or '-'}")
        self.stdout.write(
            f"  Normalized phone: {normalized_phone_candidate(identifier) or '-'}",
        )
        self.stdout.write(f"  Masked identifier: {mask_login_identifier(identifier)}")
        self.stdout.write(f"  Center slug: {center.slug if center else '-'}")

        candidates = list(find_login_users(identifier, center=center, active_only=False))
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Candidates"))
        self.stdout.write(f"  Topilgan userlar soni: {len(candidates)}")
        if not candidates:
            self.stdout.write(self.style.WARNING("  Mos user topilmadi."))
        for index, user in enumerate(candidates, start=1):
            self.stdout.write(
                f"  {index}. id={user.id} email={user.email} "
                f"phone={user.phone_number or user.telefon1 or '-'} "
                f"role={user.role or '-'} active={user.is_active} "
                f"center={getattr(user.center, 'slug', '-') or '-'} "
                f"usable_password={user.has_usable_password()}",
            )

        if not password:
            return

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Auth checks"))
        authenticated_user = authenticate_login_identifier(
            identifier,
            password,
            center=center,
        )
        self.stdout.write(
            f"  authenticate_login_identifier: "
            f"{authenticated_user.email if authenticated_user else 'FAILED'}",
        )
        for index, user in enumerate(candidates, start=1):
            self.stdout.write(
                f"  {index}. check_password={user.check_password(password)} "
                f"is_active={user.is_active}",
            )
