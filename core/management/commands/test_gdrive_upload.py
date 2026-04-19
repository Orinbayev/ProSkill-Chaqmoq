"""
Google Drive sozlamalarini tekshirish uchun buyruq.

Ishlatish:
    python manage.py test_gdrive_upload

Kichik sinov fayli yaratib Google Drive'ga yuklaydi.
Muvaffaqiyat bo'lsa Drive'da fayl paydo bo'ladi, link chop etiladi.
Xato bo'lsa – sabab ko'rsatiladi (JSON noto'g'ri, papka ulashilmagan, API yoqilmagan, h.k.).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.services.gdrive_backup import (
    is_gdrive_configured,
    upload_file_to_gdrive,
)


class Command(BaseCommand):
    help = "Google Drive ulanganini tekshirish uchun kichik sinov faylini yuklaydi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--subfolder",
            type=str,
            default="_test",
            help="Drive ichida yaratiladigan test papka nomi (default: _test)",
        )

    def handle(self, *args, **options):
        if not is_gdrive_configured():
            raise CommandError(
                "GDrive sozlanmagan!\n"
                "  GDRIVE_SERVICE_ACCOUNT_JSON va GDRIVE_FOLDER_ID env var'larini tekshiring.\n"
                "  Render Dashboard → Environment Variables.\n"
                "  Qo'llanma: RESTORE_GUIDE.md"
            )

        subfolder = str(options["subfolder"]).strip() or "_test"
        stamp = timezone.now().strftime("%Y-%m-%d_%H-%M-%S")
        content = (
            f"ChaqmoqApp GDrive test fayli\n"
            f"Generated at: {timezone.now().isoformat()}\n"
            f"Agar siz buni Drive'dan ko'rayapsiz — ulanish ishlayapti.\n"
        )

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            prefix=f"gdrive_test_{stamp}_",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            self.stdout.write(f"📤 Yuklanmoqda: {temp_path.name} → {subfolder}/")
            result = upload_file_to_gdrive(temp_path, subfolder_path=[subfolder])
            link = result.get("webViewLink", "(link yo'q)")
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ MUVAFFAQIYAT!\n"
                    f"   Fayl ID: {result.get('id')}\n"
                    f"   Nom:     {result.get('name')}\n"
                    f"   Link:    {link}\n"
                    f"   Papka:   {subfolder}/\n\n"
                    f"Drive'ni ochib, fayl haqiqatan paydo bo'lganini tekshiring."
                )
            )
        except Exception as exc:
            raise CommandError(
                f"❌ GDrive yuklash xatosi: {exc}\n"
                "Tekshirish ro'yxati:\n"
                "  1. GDRIVE_SERVICE_ACCOUNT_JSON to'g'ri JSON (butun fayl ichi, bitta qatorga)?\n"
                "  2. GDRIVE_FOLDER_ID to'g'ri (Drive URL'dagi /folders/<ID>)?\n"
                "  3. Drive papkasi service_account email'iga 'Editor' bilan ulashilganmi?\n"
                "  4. Google Cloud loyihada 'Google Drive API' yoqilganmi?\n"
            ) from exc
        finally:
            temp_path.unlink(missing_ok=True)
