import sys

from django.core.management.base import BaseCommand, CommandError

from core.services.db_backup_service import (
    _get_bot_token,
    _get_group_id,
    _telegram_api_request,
    get_backup_schedule_label,
    validate_telegram_destination,
)


class Command(BaseCommand):
    help = "Telegram backup bot sozlamalarini tekshiradi va /db commandni tayyorlaydi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--mode",
            choices=["polling", "webhook", "check"],
            default="polling",
            help="polling: webhookni o'chiradi; webhook: webhook-url talab qiladi; check: faqat tekshiradi.",
        )
        parser.add_argument(
            "--webhook-url",
            type=str,
            default="",
            help="Webhook endpoint URL. Faqat --mode webhook uchun kerak.",
        )

    def handle(self, *args, **options):
        token = _get_bot_token()
        chat_id = _get_group_id()
        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN env topilmadi")
        if not chat_id:
            raise CommandError("TELEGRAM_BACKUP_CHAT_ID env topilmadi")

        try:
            info = validate_telegram_destination(token=token, group_id=chat_id)
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        bot = info["bot"]
        chat = info["chat"]

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Bot OK: @{bot.get('username')} | chat={chat.get('title') or chat_id}"
            )
        )

        _telegram_api_request(
            "setMyCommands",
            token=token,
            commands='[{"command":"db","description":"Database backuplarni yuborish"}]',
        )
        self.stdout.write(self.style.SUCCESS("✅ /db command setMyCommands orqali ro'yxatga olindi"))

        webhook_info = _telegram_api_request(
            "getWebhookInfo",
            token=token,
            http_method="get",
        )
        current_webhook = webhook_info.get("url") or ""
        if current_webhook:
            self.stdout.write(f"Joriy webhook: {current_webhook}")
        else:
            self.stdout.write("Joriy webhook: yo'q")

        mode = options["mode"]
        if mode == "polling":
            _telegram_api_request("deleteWebhook", token=token, drop_pending_updates=False)
            self.stdout.write(self.style.SUCCESS("✅ Polling mode tayyor: webhook o'chirildi"))
            self.stdout.write("Production polling service: python3 -u telegram_bot/bot.py")
        elif mode == "webhook":
            webhook_url = options["webhook_url"].strip()
            if not webhook_url:
                raise CommandError("--mode webhook uchun --webhook-url kerak")
            _telegram_api_request("setWebhook", token=token, url=webhook_url)
            self.stdout.write(self.style.SUCCESS(f"✅ Webhook o'rnatildi: {webhook_url}"))
        elif mode == "check":
            self.stdout.write(self.style.SUCCESS("✅ Check mode: sozlamalar tekshirildi"))
        else:
            self.stderr.write(self.style.ERROR(f"Noma'lum mode: {mode}"))
            sys.exit(1)

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Backup schedule: har kuni {get_backup_schedule_label()}"
            )
        )
