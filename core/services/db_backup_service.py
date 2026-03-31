"""
ChaqmoqApp – Markaz DB Backup Service
======================================
Har kuni 16:00 (Asia/Tashkent) da:
  1. Barcha ACTIVE markazlar olinadi
  2. Har biri uchun alohida JSON snapshot yaratiladi
  3. To'liq PostgreSQL dump yaratiladi (pg_dump mavjud bo'lsa)
  4. Har bir fayl Telegram guruhga document sifatida yuboriladi
  5. Yuborilgan/xato bo'lgan markazlar logga aniq yoziladi

MUHIM TUZATISHLAR (v2):
- Async/Event-loop muammo YO'Q: `requests` (sync HTTP) ishlatiladi
- BackgroundScheduler (thread-based) – Django WSGI/Gunicorn bilan mos
- Token/GroupID env var fallback: TELEGRAM_BOT_TOKEN | BOT_TOKEN
- To'liq traceback loglanadi
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import traceback
from pathlib import Path
from typing import Any

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.db import models
from django.utils import timezone

from accounts.models import Center

logger = logging.getLogger(__name__)

_backup_scheduler: BackgroundScheduler | None = None
CENTER_EXPORT_APPS = {"accounts", "core", "billing", "education", "store", "chaqmoq"}


def _get_backup_root() -> Path:
    backup_root = Path(settings.BASE_DIR) / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    return backup_root


def _get_bot_token() -> str:
    """Token: settings.TELEGRAM_BOT_TOKEN → BOT_TOKEN env var."""
    return (
        str(getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
        or str(os.environ.get("TELEGRAM_BOT_TOKEN", "") or "").strip()
        or str(os.environ.get("BOT_TOKEN", "") or "").strip()
    )


def _get_group_id() -> str:
    """Group ID: settings.TELEGRAM_GROUP_ID → BACKUP_GROUP_ID env var."""
    return (
        str(getattr(settings, "TELEGRAM_GROUP_ID", "") or "").strip()
        or str(os.environ.get("TELEGRAM_GROUP_ID", "") or "").strip()
        or str(os.environ.get("BACKUP_GROUP_ID", "") or "").strip()
    )


def _get_default_db_credentials() -> dict[str, str]:
    default_db = (getattr(settings, "DATABASES", {}) or {}).get("default", {})
    if not default_db or "postgresql" not in str(default_db.get("ENGINE", "")).lower():
        raise ValueError("default DB is not PostgreSQL")
    credentials = {
        "name": str(default_db.get("NAME", "") or "").strip(),
        "user": str(default_db.get("USER", "") or "").strip(),
        "password": str(default_db.get("PASSWORD", "") or "").strip(),
        "host": str(default_db.get("HOST", "") or "localhost").strip() or "localhost",
        "port": str(default_db.get("PORT", "") or "5432").strip() or "5432",
    }
    missing = [key for key in ("name", "user") if not credentials[key]]
    if missing:
        raise ValueError(f"missing default DB credentials: {', '.join(missing)}")
    return credentials


def _build_center_export_path(center: Center) -> Path:
    backup_date = timezone.localdate().isoformat()
    return _get_backup_root() / f"{center.slug}_{backup_date}.json"


def _build_full_backup_path() -> Path:
    backup_date = timezone.localdate().isoformat()
    return _get_backup_root() / f"postgres_full_{backup_date}.sql"


def _build_pg_dump_command(credentials: dict[str, str], backup_path: Path) -> list[str]:
    return [
        "pg_dump",
        "-h",
        credentials["host"],
        "-p",
        credentials["port"],
        "-U",
        credentials["user"],
        "-d",
        credentials["name"],
        "-f",
        str(backup_path),
        "--no-owner",
        "--no-privileges",
        "-Fp",
    ]


def _iter_export_models() -> list[type[models.Model]]:
    export_models: list[type[models.Model]] = []
    for model in apps.get_models():
        if model._meta.app_label not in CENTER_EXPORT_APPS:
            continue
        if model._meta.proxy or model._meta.auto_created:
            continue
        export_models.append(model)
    return export_models


def _build_center_lookup_map(export_models: list[type[models.Model]]) -> dict[type[models.Model], str]:
    lookup_map: dict[type[models.Model], str] = {Center: ""}
    unresolved = set(export_models) - {Center}

    changed = True
    while changed and unresolved:
        changed = False
        for model in list(unresolved):
            for field in model._meta.fields:
                if not isinstance(field, (models.ForeignKey, models.OneToOneField)):
                    continue
                related_model = field.related_model
                if related_model not in lookup_map:
                    continue
                parent_lookup = lookup_map[related_model]
                lookup_map[model] = f"{field.name}__{parent_lookup}" if parent_lookup else field.name
                unresolved.remove(model)
                changed = True
                break

    return lookup_map


def export_center_snapshot(center: Center) -> Path:
    export_models = _iter_export_models()
    lookup_map = _build_center_lookup_map(export_models)

    objects: list[dict[str, Any]] = []
    for model in export_models:
        if model is Center:
            qs = model._default_manager.filter(pk=center.pk).order_by("pk")
        else:
            lookup = lookup_map.get(model)
            if not lookup:
                continue
            qs = model._default_manager.filter(**{f"{lookup}_id": center.id}).order_by("pk").distinct()
        serialized = serializers.serialize("json", qs)
        objects.extend(json.loads(serialized))

    export_path = _build_center_export_path(center)
    payload = {
        "meta": {
            "type": "center_scoped_snapshot",
            "center_id": center.id,
            "center_slug": center.slug,
            "generated_at": timezone.now().isoformat(),
            "object_count": len(objects),
        },
        "objects": objects,
    }
    with export_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info("Center snapshot exported: center=%s file=%s objects=%s", center.slug, export_path, len(objects))
    return export_path


def backup_full_database() -> Path:
    if shutil.which("pg_dump") is None:
        raise RuntimeError("pg_dump is not available on this system")

    backup_path = _build_full_backup_path()
    credentials = _get_default_db_credentials()

    env = os.environ.copy()
    env["PGCONNECT_TIMEOUT"] = env.get("PGCONNECT_TIMEOUT", "15")
    if credentials["password"]:
        env["PGPASSWORD"] = credentials["password"]

    result = subprocess.run(
        _build_pg_dump_command(credentials, backup_path),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        if backup_path.exists():
            backup_path.unlink(missing_ok=True)
        error_text = (result.stderr or result.stdout or f"pg_dump exited with code {result.returncode}").strip()
        raise RuntimeError(error_text)

    logger.info("Full PostgreSQL backup created: file=%s", backup_path)
    return backup_path


# ────────────────────────────────────────────────────────────────────────────
# TELEGRAM – SYNC (requests, HECH QANDAY async/event-loop muammo yo'q)
# ────────────────────────────────────────────────────────────────────────────

def send_file_to_telegram(file_path: str | Path, caption: str | None = None) -> None:
    """
    Faylni Telegram guruhga document sifatida yuboradi.

    faqat `requests` ishlatadi – aiogram/asyncio event-loop muammo yo'q.

    Raises:
        ValueError      – token yoki group_id sozlanmagan bo'lsa
        FileNotFoundError – fayl topilmasa
        RuntimeError    – Telegram API xato qaytarsa
        requests.RequestException – tarmoq xatosi
    """
    token = _get_bot_token()
    group_id = _get_group_id()

    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN yoki BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan! "
            "Render Dashboard → Environment Variables ga qo'shing."
        )
    if not group_id:
        raise ValueError(
            "TELEGRAM_GROUP_ID yoki BACKUP_GROUP_ID muhit o'zgaruvchisi o'rnatilmagan! "
            "Render Dashboard → Environment Variables ga qo'shing."
        )

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Backup fayli topilmadi: {path}")

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    caption_text = caption or path.name

    logger.info(
        "Telegram yuborish boshlandi: file=%s size=%d bytes chat_id=%s",
        path.name,
        path.stat().st_size,
        group_id,
    )

    with path.open("rb") as fh:
        resp = requests.post(
            url,
            data={"chat_id": str(group_id), "caption": caption_text},
            files={"document": (path.name, fh, "application/octet-stream")},
            timeout=120,
        )

    try:
        result = resp.json()
    except Exception:
        result = {}

    if not resp.ok or not result.get("ok"):
        err_desc = result.get("description", resp.text[:400])
        raise RuntimeError(
            f"Telegram API xatosi [{resp.status_code}]: {err_desc}\n"
            f"  Token prefix: {token[:10]}***\n"
            f"  Chat ID: {group_id}"
        )

    logger.info("✅ Telegram muvaffaqiyatli yuborildi: file=%s", path.name)


# ────────────────────────────────────────────────────────────────────────────
# MAIN JOB
# ────────────────────────────────────────────────────────────────────────────

def backup_and_send_all_centers() -> dict[str, Any]:
    """
    Barcha ACTIVE markazlar uchun backup yaratadi va Telegram guruhga yuboradi.

    - Har bir markaz uchun alohida JSON snapshot
    - To'liq PostgreSQL dump (pg_dump mavjud bo'lsa)
    - Xato bo'lsa qolgan markazlar davom etadi
    - To'liq traceback loglanadi
    """
    summary: dict[str, Any] = {
        "total": 0,
        "backed_up": 0,
        "sent": 0,
        "combined_sent": 0,
        "full_sent": 0,
        "skipped": 0,
        "failed": 0,
        "files": [],
        "full_backup_file": None,
        "failed_centers": [],
    }

    logger.info("=" * 60)
    logger.info("BACKUP JOB BOSHLANDI: %s", timezone.now().isoformat())
    logger.info("=" * 60)

    # ── Env var tekshiruvi ─────────────────────────────────────────────────
    token = _get_bot_token()
    group_id = _get_group_id()
    if not token:
        logger.error(
            "BACKUP JOB TO'XTATILDI: TELEGRAM_BOT_TOKEN (yoki BOT_TOKEN) "
            "env var o'rnatilmagan! Render Dashboard da sozlang."
        )
        return summary
    if not group_id:
        logger.error(
            "BACKUP JOB TO'XTATILDI: TELEGRAM_GROUP_ID (yoki BACKUP_GROUP_ID) "
            "env var o'rnatilmagan! Render Dashboard da sozlang."
        )
        return summary

    logger.info("Token mavjud: %s***", token[:8])
    logger.info("Group ID: %s", group_id)

    # ── Markazlarni olish ──────────────────────────────────────────────────
    centers = list(
        Center.objects.filter(status=Center.STATUS_ACTIVE)
        .only("id", "slug", "name", "status")
        .order_by("id")
    )
    summary["total"] = len(centers)
    logger.info("Aktiv markazlar: %d ta", len(centers))

    if not centers:
        logger.warning("Hech qanday aktiv markaz topilmadi. Job tugadi.")
        return summary

    date_str = timezone.localdate().isoformat()

    # ── Har bir markaz ─────────────────────────────────────────────────────
    for center in centers:
        logger.info("── Markaz: %s (%s) ──", center.name, center.slug)
        backup_path: Path | None = None
        try:
            # 1. JSON snapshot yaratish
            backup_path = export_center_snapshot(center)
            summary["backed_up"] += 1
            summary["files"].append(str(backup_path))

            # 2. Telegram yuborish
            caption = (
                f"📦 Markaz backup\n"
                f"🏢 Markaz: {center.name} ({center.slug})\n"
                f"📅 Sana: {date_str}\n"
                f"📁 Fayl: {backup_path.name}\n"
                f"🔢 Tur: JSON snapshot"
            )
            send_file_to_telegram(backup_path, caption=caption)
            summary["sent"] += 1
            logger.info(
                "✅ Yuborildi: center=%s file=%s",
                center.slug,
                backup_path.name,
            )

        except ValueError as exc:
            # Token/group_id muammosi
            summary["skipped"] += 1
            logger.warning("⚠️ O'tkazib yuborildi: center=%s sabab=%s", center.slug, exc)

        except Exception:
            summary["failed"] += 1
            summary["failed_centers"].append(center.slug)
            logger.error(
                "❌ XATOLIK: center=%s\n%s",
                center.slug,
                traceback.format_exc(),
            )

    # ── To'liq PostgreSQL dump ─────────────────────────────────────────────
    logger.info("── To'liq PostgreSQL dump ──")
    try:
        full_path = backup_full_database()
        summary["full_backup_file"] = str(full_path)
        summary["files"].append(str(full_path))

        caption = (
            f"🗄️ To'liq PostgreSQL backup\n"
            f"📅 Sana: {date_str}\n"
            f"🏢 Markazlar soni: {summary['total']}\n"
            f"📁 Fayl: {full_path.name}"
        )
        send_file_to_telegram(full_path, caption=caption)
        summary["sent"] += 1
        summary["combined_sent"] = 1
        summary["full_sent"] = 1
        logger.info("✅ To'liq backup yuborildi: file=%s", full_path.name)

    except Exception:
        summary["failed"] += 1
        logger.error("❌ To'liq backup XATOLIGI:\n%s", traceback.format_exc())

    # ── Yakuniy hisobot ────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(
        "BACKUP JOB TUGADI | total=%d backed_up=%d sent=%d "
        "full_sent=%d skipped=%d failed=%d",
        summary["total"],
        summary["backed_up"],
        summary["sent"],
        summary["full_sent"],
        summary["skipped"],
        summary["failed"],
    )
    if summary["failed_centers"]:
        logger.error("XATO bo'lgan markazlar: %s", ", ".join(summary["failed_centers"]))
    logger.info("=" * 60)
    return summary


# ────────────────────────────────────────────────────────────────────────────
# SCHEDULER – BackgroundScheduler (Django WSGI / Gunicorn bilan mos)
# ────────────────────────────────────────────────────────────────────────────

def setup_backup_scheduler() -> BackgroundScheduler:
    """
    BackgroundScheduler (thread-based) yaratadi.
    Har kuni 16:00 Asia/Tashkent da backup_and_send_all_centers() ishlatadi.

    Django AppConfig.ready() dan chaqiriladi.
    Gunicorn multi-worker: faqat bitta worker uchun
      BACKUP_SCHEDULER_ENABLED=true env var o'rnating.
    """
    global _backup_scheduler

    if _backup_scheduler and _backup_scheduler.running:
        logger.info("Backup scheduler allaqachon ishlamoqda.")
        return _backup_scheduler

    tz = getattr(settings, "TIME_ZONE", "Asia/Tashkent")
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(
        backup_and_send_all_centers,
        CronTrigger(hour=17, minute=35, timezone=tz),
        id="tenant-db-backup-daily",
        name="tenant-db-backup-daily",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    scheduler.start()
    _backup_scheduler = scheduler
    logger.info("✅ Backup scheduler ishga tushdi: har kuni 16:00 %s", tz)
    return scheduler


# ────────────────────────────────────────────────────────────────────────────
# ASYNC WRAPPER – Bot handler'laridan chaqirish uchun
# ────────────────────────────────────────────────────────────────────────────

async def run_backup_async() -> dict[str, Any]:
    """
    Bot /backup_now handler uchun async wrapper.
    backup_and_send_all_centers() ni thread pool da ishlatadi.
    """
    import asyncio
    return await asyncio.to_thread(backup_and_send_all_centers)
