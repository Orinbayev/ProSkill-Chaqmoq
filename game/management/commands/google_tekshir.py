"""Google sozlamalarini tekshiradi.

Ishlatish:
    python manage.py google_tekshir

Client ID'larni qo'ygandan keyin shu buyruqni ishga tushiring — hammasi
joyidami yoki qayerda xato borligini aytadi. Ilovani qayta yig'ishdan oldin
shu tekshiruvdan o'tkazish vaqtni tejaydi.
"""

from __future__ import annotations

import re

from django.conf import settings
from django.core.management.base import BaseCommand

from game.google_auth import ruxsat_etilgan_client_idlar

# Google client ID'lari doim shu ko'rinishda: <raqamlar>-<harf/raqam>.apps.googleusercontent.com
NAQSH = re.compile(r"^\d+-[a-z0-9]+\.apps\.googleusercontent\.com$")


class Command(BaseCommand):
    help = "Google orqali ro'yxatdan o'tish sozlamalarini tekshiradi."

    def handle(self, *args, **options):
        idlar = ruxsat_etilgan_client_idlar()

        self.stdout.write(self.style.MIGRATE_HEADING("Google sozlamalari"))
        self.stdout.write("")

        if not idlar:
            self.stdout.write(self.style.ERROR("  ✗ GOOGLE_OAUTH_CLIENT_IDS bo'sh"))
            self.stdout.write("")
            self.stdout.write(
                "    Ilovada Google tugmasi ko'rinmaydi — o'rniga\n"
                "    «hozircha sozlanmagan» xabari chiqadi.\n"
            )
            self.stdout.write("    Qadamlar: GOOGLE_SETUP.md")
            return

        xato_bor = False
        for i, client_id in enumerate(idlar, start=1):
            if NAQSH.match(client_id):
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ {i}. {self._qisqa(client_id)}")
                )
            else:
                xato_bor = True
                self.stdout.write(
                    self.style.ERROR(f"  ✗ {i}. {client_id} — ko'rinishi noto'g'ri")
                )
                self.stdout.write(
                    "       Kutilgan: 123456789-abc123.apps.googleusercontent.com"
                )

        self.stdout.write("")

        if len(idlar) < 3:
            self.stdout.write(
                self.style.WARNING(
                    f"  ! Faqat {len(idlar)} ta ID topildi. Odatda 3 ta kerak:\n"
                    "    Web (server tekshiruvi), iOS va Android."
                )
            )
            self.stdout.write("")

        # Telegram — tarif so'rovlari shu hisobga boradi.
        telegram = str(getattr(settings, "GAME_SUPPORT_TELEGRAM", "") or "").strip()
        if telegram:
            self.stdout.write(f"  Telegram (tarif so'rovlari): @{telegram.lstrip('@')}")
        else:
            self.stdout.write(
                self.style.WARNING("  ! GAME_SUPPORT_TELEGRAM bo'sh — "
                                   "to'lov so'rovi hech kimga bormaydi")
            )

        self.stdout.write("")
        if xato_bor:
            self.stdout.write(self.style.ERROR("Xatoliklar bor — yuqoriga qarang."))
        else:
            self.stdout.write(self.style.SUCCESS("Sozlamalar joyida."))
            self.stdout.write(
                "\nIlovani shu ID bilan yig'ing:\n"
                f"  --dart-define=GOOGLE_SERVER_CLIENT_ID={idlar[0]}"
            )

    @staticmethod
    def _qisqa(client_id: str) -> str:
        """Uzun ID'ni logda to'liq ko'rsatmaymiz — boshi yetarli."""
        bosh = client_id.split("-", 1)[0]
        return f"{bosh}-…apps.googleusercontent.com"
