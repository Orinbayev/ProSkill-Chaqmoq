import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.signals  # noqa: F401
        try:
            core.signals.connect_billing_cache_signals()
        except Exception:
            logger.exception("Billing cache signal ulanmadi")

        # ── Backup Scheduler ─────────────────────────────────────────────
        # Django dev serveri manage.py runserver ni IKKI MARTA ishlatadi.
        # RUN_MAIN=true faqat asosiy jarayonda bo'ladi – duplicate oldini olish.
        # Productionda backup asosan Render Cron orqali 18:00 Asia/Tashkent da yuradi.
        # Web worker ichida scheduler ochish 512MB servisda xotirani oshirib, 502 ga olib kelishi mumkin.
        # Kerak bo'lsa BACKUP_SCHEDULER_ENABLED=true bilan qo'lda yoqing.
        run_main = os.environ.get("RUN_MAIN")          # dev server inner process
        scheduler_flag = os.environ.get("BACKUP_SCHEDULER_ENABLED", "").lower()
        is_render = os.environ.get("RENDER", "")       # Render.com env

        should_start = (
            # 1. Lokal dev: faqat inner process da (ikki marta ishlamasi uchun)
            (not is_render and run_main == "true")
            # 2. Manuel flag: BACKUP_SCHEDULER_ENABLED=true
            or scheduler_flag in {"1", "true", "yes", "on"}
        )

        if should_start:
            try:
                from core.services.db_backup_service import setup_backup_scheduler
                setup_backup_scheduler()
            except Exception:
                # Scheduler xato bo'lsa Django'ni to'xtatmasin
                logger.exception(
                    "Backup scheduler ishga tushmadi (Django davom etadi)"
                )
