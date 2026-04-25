"""
python manage.py test_backup_send

Tez diagnostika buyrug'i:
  1. Bot token mavjudligini tekshiradi
  2. Telegram API ga ping yuboradi (getMe)
  3. Birinchi aktiv markaz uchun backup yaratadi
  4. Telegram guruhga yuboradi
  5. Har bir qadam haqida aniq log chiqaradi

Foydalanish:
  python manage.py test_backup_send
  python manage.py test_backup_send --center proskill
  python manage.py test_backup_send --check-only   (faqat token/group tekshiradi)
"""

import json
import sys

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Center
from core.services.db_backup_service import (
    _get_bot_token,
    _get_group_id,
    export_center_snapshot,
    get_backup_schedule_label,
    send_file_to_telegram,
)


class Command(BaseCommand):
    help = "Backup tizimini diagnostika qiladi va test yuborma bajaradi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--center",
            type=str,
            default="",
            help="Test uchun markaz slug'i (bo'sh = birinchi aktiv markaz)",
        )
        parser.add_argument(
            "--check-only",
            action="store_true",
            default=False,
            help="Faqat token/group tekshiradi, backup yaratmaydi",
        )

    def handle(self, *args, **options):
        center_slug = options["center"].strip()
        check_only = options["check_only"]

        self.stdout.write("\n" + "=" * 55)
        self.stdout.write("🔍  BACKUP DIAGNOSTIKA TEST")
        self.stdout.write("=" * 55)

        # ── 1. Token tekshirish ────────────────────────────────────────────
        self.stdout.write("\n[1] Token tekshirish...")
        token = _get_bot_token()
        if not token:
            self.stderr.write(self.style.ERROR(
                "❌ BACKUP_BOT_TOKEN (yoki TELEGRAM_BOT_TOKEN/BOT_TOKEN) topilmadi!\n"
                "   Render Dashboard → Environment Variables ga qo'shing."
            ))
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS("✅ Token mavjud."))

        # ── 2. Group ID tekshirish ─────────────────────────────────────────
        self.stdout.write("\n[2] Group ID tekshirish...")
        group_id = _get_group_id()
        if not group_id:
            self.stderr.write(self.style.ERROR(
                "❌ TELEGRAM_BACKUP_CHAT_ID topilmadi!\n"
                "   Render Dashboard yoki .env ichiga qo'shing."
            ))
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS(f"✅ Group ID: {group_id}"))

        # ── 3. Telegram API – getMe ────────────────────────────────────────
        self.stdout.write("\n[3] Telegram Bot getMe tekshirish...")
        bot_info = {}
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/getMe",
                timeout=15,
            )
            data = resp.json()
            if data.get("ok"):
                bot_info = data["result"]
                self.stdout.write(self.style.SUCCESS(
                    f"✅ Bot ishlayapti: @{bot_info.get('username')} "
                    f"(id={bot_info.get('id')})"
                ))
            else:
                self.stderr.write(self.style.ERROR(
                    f"❌ getMe xatosi: {data.get('description')}\n"
                    "   Token noto'g'ri yoki eskirgan bo'lishi mumkin."
                ))
                sys.exit(1)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"❌ Tarmoq xatosi: {exc}"))
            sys.exit(1)

        # ── 4. Telegram – getChat (group mavjudligi) ───────────────────────
        self.stdout.write("\n[4] Telegram guruh tekshirish...")
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/getChat",
                params={"chat_id": str(group_id)},
                timeout=15,
            )
            data = resp.json()
            if data.get("ok"):
                chat = data["result"]
                self.stdout.write(self.style.SUCCESS(
                    f"✅ Guruh topildi: {chat.get('title', chat.get('username', group_id))} "
                    f"(type={chat.get('type')})"
                ))
            else:
                bot_username = bot_info.get("username") or "noma'lum"
                self.stderr.write(self.style.ERROR(
                    f"❌ getChat xatosi: {data.get('description')}\n"
                    f"   Hozirgi bot: @{bot_username}\n"
                    "   Bot guruhda bo'lmasligi mumkin yoki BACKUP_BOT_TOKEN/BACKUP_GROUP_ID noto'g'ri."
                ))
                sys.exit(1)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"❌ getChat tarmoq xatosi: {exc}"))
            sys.exit(1)

        if check_only:
            self.stdout.write(self.style.SUCCESS("\n✅ --check-only: token/group tekshiruvi tugadi."))
            return

        # ── 5. Aktiv markazni tanlash ──────────────────────────────────────
        self.stdout.write("\n[5] Test markaz tanlash...")
        if center_slug:
            try:
                center = Center.objects.get(slug=center_slug)
            except Center.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"❌ Markaz topilmadi: {center_slug}"))
                sys.exit(1)
        else:
            center = Center.objects.filter(status=Center.STATUS_ACTIVE).first()
            if not center:
                self.stderr.write(self.style.ERROR("❌ Hech qanday aktiv markaz topilmadi!"))
                sys.exit(1)
        self.stdout.write(self.style.SUCCESS(
            f"✅ Test markaz: {center.name} (slug={center.slug})"
        ))

        # ── 6. Backup yaratish ─────────────────────────────────────────────
        self.stdout.write("\n[6] Backup yaratish...")
        try:
            path = export_center_snapshot(center)
            size_kb = path.stat().st_size / 1024
            self.stdout.write(self.style.SUCCESS(
                f"✅ Backup yaratildi: {path.name} ({size_kb:.1f} KB)"
            ))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"❌ Backup yaratish xatosi: {exc}"))
            sys.exit(1)

        # ── 7. Telegram ga yuborish ────────────────────────────────────────
        self.stdout.write("\n[7] Telegram ga yuborish...")
        try:
            date_str = timezone.localdate().isoformat()
            caption = (
                f"🧪 TEST BACKUP\n"
                f"🏢 Markaz: {center.name} ({center.slug})\n"
                f"📅 Sana: {date_str}\n"
                f"📁 Fayl: {path.name}"
            )
            send_file_to_telegram(path, caption=caption)
            self.stdout.write(self.style.SUCCESS(
                f"✅ Telegram ga muvaffaqiyatli yuborildi!"
            ))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"❌ Telegram yuborish xatosi: {exc}"))
            sys.exit(1)

        # ── Yakuniy ────────────────────────────────────────────────────────
        self.stdout.write("\n" + "=" * 55)
        self.stdout.write(self.style.SUCCESS(
            "✅ BARCHA TESTLAR MUVAFFAQIYATLI O'TDI!\n"
            f"   Scheduler har kuni {get_backup_schedule_label()} da ishlaydi."
        ))
        self.stdout.write("=" * 55 + "\n")
