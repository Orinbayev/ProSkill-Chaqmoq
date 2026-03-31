import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.signals  # noqa: F401

        # ── Backup Scheduler ─────────────────────────────────────────────
        # Django dev serveri manage.py runserver ni IKKI MARTA ishlatadi.
        # RUN_MAIN=true faqat asosiy jarayonda bo'ladi – duplicate oldini olish.
        # Gunicorn multi-worker uchun BACKUP_SCHEDULER_ENABLED=true o'rnating
        # faqat bitta worker da (masalan, preload_app=True bilan).
        run_main = os.environ.get("RUN_MAIN")          # dev server inner process
        scheduler_flag = os.environ.get("BACKUP_SCHEDULER_ENABLED", "").lower()
        is_render = os.environ.get("RENDER", "")       # Render.com env

        should_start = (
            # 1. Render production: har doim ishlatsin
            bool(is_render)
            # 2. Lokal dev: faqat inner process da (ikki marta ishlamasi uchun)
            or run_main == "true"
            # 3. Manuel flag: BACKUP_SCHEDULER_ENABLED=true
            or scheduler_flag == "true"
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
