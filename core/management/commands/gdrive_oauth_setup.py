"""
Google Drive OAuth setup – BIR MARTAGINA ishlatiladi (lokal kompyuter'da).

Ishlatish:
    python manage.py gdrive_oauth_setup ~/Downloads/client_secret_XXXX.json

Qo'lda bajarilgan brauzer oynasida sen Google akkaunting bilan tasdiqlaysan,
va bu buyruq 3 ta sir qaytaradi:

    GDRIVE_OAUTH_CLIENT_ID
    GDRIVE_OAUTH_CLIENT_SECRET
    GDRIVE_OAUTH_REFRESH_TOKEN

Ularni Render Dashboard → Environment Variables ga qo'shasan.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

GDRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class Command(BaseCommand):
    help = (
        "Google Drive OAuth refresh token olish uchun bir martalik sozlash buyrug'i. "
        "Lokal kompyuter'da ishlatiladi (Render Shell'da EMAS — brauzer ochilishi kerak)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "client_secrets_path",
            type=str,
            help="Google Cloud'dan yuklab olgan client_secrets.json yo'li",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=0,
            help="Local server port (0 = avtomatik). Default: avtomatik.",
        )

    def handle(self, *args, **options):
        path = Path(options["client_secrets_path"]).expanduser().resolve()
        if not path.exists():
            raise CommandError(f"Fayl topilmadi: {path}")

        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as exc:
            raise CommandError(
                "google-auth-oauthlib o'rnatilmagan. "
                "Lokal'da: pip install google-auth-oauthlib"
            ) from exc

        try:
            with path.open("r", encoding="utf-8") as f:
                secrets = json.load(f)
        except json.JSONDecodeError as exc:
            raise CommandError(f"client_secrets.json noto'g'ri JSON: {exc}") from exc

        # Faylning "installed" yoki "web" bloki ichidan client_id/secret olamiz.
        container = secrets.get("installed") or secrets.get("web") or {}
        client_id = container.get("client_id", "")
        client_secret = container.get("client_secret", "")
        if not client_id or not client_secret:
            raise CommandError(
                "client_secrets.json ichida 'installed' yoki 'web' bloki topilmadi. "
                "Google Cloud → Credentials → OAuth Client ID (Desktop app) yarating."
            )

        self.stdout.write(self.style.WARNING(
            "Brauzer ochiladi. Google akkauntingizni tanlang va 'Allow' bosing.\n"
            "Agar 'This app isn't verified' deb ogohlantirsa:\n"
            "  'Advanced' → 'Go to <app name> (unsafe)' — bu xavfsiz, chunki sen yaratgan.\n"
        ))

        flow = InstalledAppFlow.from_client_secrets_file(
            str(path), GDRIVE_SCOPES
        )
        # access_type=offline + prompt=consent => refresh_token har doim qaytariladi.
        creds = flow.run_local_server(
            port=options["port"],
            access_type="offline",
            prompt="consent",
            open_browser=True,
        )

        if not creds.refresh_token:
            raise CommandError(
                "Refresh token qaytmadi. Bu odatda OAuth Client qayta ishlatilganda bo'ladi. "
                "Google akkauntdagi 'Third-party apps' ro'yxatidan o'chiring va qaytadan sinab ko'ring."
            )

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("✅ MUVAFFAQIYAT — quyidagilarni Render env vars'ga qo'ying:"))
        self.stdout.write(self.style.SUCCESS("=" * 60 + "\n"))

        self.stdout.write(f"GDRIVE_OAUTH_CLIENT_ID={client_id}")
        self.stdout.write(f"GDRIVE_OAUTH_CLIENT_SECRET={client_secret}")
        self.stdout.write(f"GDRIVE_OAUTH_REFRESH_TOKEN={creds.refresh_token}")

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.WARNING(
            "MUHIM:\n"
            "  1. Eski GDRIVE_SERVICE_ACCOUNT_JSON env var'ni Render'dan O'CHIR.\n"
            "  2. Yuqoridagi 3 ta yangi env var'ni qo'sh.\n"
            "  3. GDRIVE_FOLDER_ID shu o'zicha qoladi (o'zgartirilmaydi).\n"
            "  4. Save Changes — Render avtomatik redeploy qiladi.\n"
            "  5. Test: Render Shell → python manage.py test_gdrive_upload"
        ))
