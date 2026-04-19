"""
ChaqmoqApp – Markaz DB Backup Service
======================================
Har kuni 17:35 (Asia/Tashkent) da:
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
import gzip
import shutil
import subprocess
import time
import traceback
from pathlib import Path
from typing import Any, TYPE_CHECKING

import requests
from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management import call_command
from django.db import connection, models, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Q
from django.utils import timezone

from accounts.models import Center
from core.services.gdrive_backup import (
    is_gdrive_configured,
    safe_upload_file_to_gdrive,
)

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

_backup_scheduler: "BackgroundScheduler | None" = None
CENTER_EXPORT_APPS = {"accounts", "core", "billing", "education", "store", "chaqmoq"}
BACKUP_SCHEDULE_HOUR = 17
BACKUP_SCHEDULE_MINUTE = 35
BACKUP_SCHEDULE_TZ_FALLBACK = "Asia/Tashkent"
BACKUP_LOCAL_RETENTION_DAYS = 7
TELEGRAM_SEND_TIMEOUT_DEFAULT = 120
TELEGRAM_SEND_TIMEOUT_LARGE = 600


def get_backup_schedule_label(timezone_name: str | None = None) -> str:
    tz_name = timezone_name or getattr(settings, "TIME_ZONE", BACKUP_SCHEDULE_TZ_FALLBACK)
    return f"{BACKUP_SCHEDULE_HOUR:02d}:{BACKUP_SCHEDULE_MINUTE:02d} {tz_name}"


def _get_backup_root() -> Path:
    backup_root = Path(settings.BASE_DIR) / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    return backup_root


def _cleanup_old_local_backups(max_age_days: int = BACKUP_LOCAL_RETENTION_DAYS) -> int:
    """
    Backups papkasidagi `max_age_days` kundan eski fayllarni o'chiradi.
    Render disk ephemeral bo'lsa ham lokal dev'da fayllar to'planib ketmasligi uchun.
    """
    root = _get_backup_root()
    cutoff = time.time() - (max_age_days * 86400)
    removed = 0
    for item in root.iterdir():
        try:
            if not item.is_file():
                continue
            if item.stat().st_mtime >= cutoff:
                continue
            item.unlink(missing_ok=True)
            removed += 1
        except Exception:
            logger.warning("Eski backup fayli o'chirilmadi: %s", item, exc_info=True)
    if removed:
        logger.info("Lokal backup tozalash: %d ta eski fayl o'chirildi", removed)
    return removed


def _gdrive_subfolder_path_for_date() -> list[str]:
    """Google Drive ichida sana bo'yicha tree: YYYY-MM / YYYY-MM-DD."""
    today = timezone.localdate()
    return [today.strftime("%Y-%m"), today.isoformat()]


def _load_backup_env_files() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    base_dir = Path(settings.BASE_DIR)
    load_dotenv(base_dir / ".env", override=False)
    load_dotenv(base_dir / "telegram_bot" / ".env", override=False)


def _get_bot_token() -> str:
    """Token priority: BACKUP_BOT_TOKEN -> TELEGRAM_BOT_TOKEN -> BOT_TOKEN."""
    _load_backup_env_files()
    return (
        str(getattr(settings, "BACKUP_BOT_TOKEN", "") or "").strip()
        or str(os.environ.get("BACKUP_BOT_TOKEN", "") or "").strip()
        or str(getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
        or str(os.environ.get("TELEGRAM_BOT_TOKEN", "") or "").strip()
        or str(os.environ.get("BOT_TOKEN", "") or "").strip()
    )


def _get_group_id() -> str:
    """Group priority: BACKUP_GROUP_ID -> TELEGRAM_GROUP_ID."""
    _load_backup_env_files()
    return (
        str(getattr(settings, "BACKUP_GROUP_ID", "") or "").strip()
        or str(os.environ.get("BACKUP_GROUP_ID", "") or "").strip()
        or str(getattr(settings, "TELEGRAM_GROUP_ID", "") or "").strip()
        or str(os.environ.get("TELEGRAM_GROUP_ID", "") or "").strip()
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


def _build_full_fixture_backup_path() -> Path:
    backup_date = timezone.localdate().isoformat()
    return _get_backup_root() / f"django_full_{backup_date}.json.gz"


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


def _build_center_lookup_map(
    export_models: list[type[models.Model]],
) -> tuple[dict[type[models.Model], list[str]], list[type[models.Model]]]:
    """
    Har model uchun Center'ga BARCHA FK yo'llarini topadi.

    Returns:
        (lookup_map, skipped)
        lookup_map[Model] = ["center", "created_by__center", ...]  – filter uchun yo'llar
        skipped           = Center'ga umuman yo'li yo'q modellar (ogohlantirish uchun)
    """
    lookup_map: dict[type[models.Model], list[str]] = {Center: [""]}

    max_iterations = len(export_models) + 5  # xavfsizlik limiti
    for _ in range(max_iterations):
        changed = False
        for model in export_models:
            if model is Center:
                continue
            new_lookups: set[str] = set()
            for field in model._meta.fields:
                if not isinstance(field, (models.ForeignKey, models.OneToOneField)):
                    continue
                related_model = field.related_model
                if related_model not in lookup_map:
                    continue
                for parent_lookup in lookup_map[related_model]:
                    if parent_lookup:
                        new_lookups.add(f"{field.name}__{parent_lookup}")
                    else:
                        new_lookups.add(field.name)
            existing = set(lookup_map.get(model, []))
            if new_lookups and new_lookups != existing:
                lookup_map[model] = sorted(new_lookups)
                changed = True
        if not changed:
            break

    skipped = [m for m in export_models if m not in lookup_map]
    return lookup_map, skipped


def _collect_migration_state() -> list[dict[str, str]]:
    """Backup olinayotgan paytdagi migration holati — tiklashda moslikni tekshirish uchun."""
    try:
        rows = (
            MigrationRecorder(connection)
            .migration_qs.values("app", "name")
            .order_by("app", "name")
        )
        return [{"app": r["app"], "name": r["name"]} for r in rows]
    except Exception:
        logger.warning("Migration holatini o'qib bo'lmadi", exc_info=True)
        return []


def export_center_snapshot(center: Center) -> Path:
    export_models = _iter_export_models()
    lookup_map, skipped_models = _build_center_lookup_map(export_models)

    if skipped_models:
        logger.warning(
            "⚠️  Center'ga FK yo'li topilmagan modellar (backup'ga KIRMAYDI): %s",
            ", ".join(m._meta.label for m in skipped_models),
        )

    objects: list[dict[str, Any]] = []

    # REPEATABLE READ – export davomida boshqa yozuvlar snapshot'ga ta'sir qilmasin.
    # Bu PostgreSQL'ning "bir zumdagi surat" rejimi, bir necha daqiqalik export uchun muhim.
    with transaction.atomic():
        if connection.vendor == "postgresql":
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            except Exception:
                logger.warning(
                    "REPEATABLE READ o'rnatib bo'lmadi — default isolation'da davom etiladi",
                    exc_info=True,
                )

        for model in export_models:
            if model is Center:
                qs = model._default_manager.filter(pk=center.pk).order_by("pk")
            else:
                lookups = lookup_map.get(model, [])
                if not lookups:
                    # Yuqoridagi warning'da e'lon qilindi, bu yerda takror yozmaymiz.
                    continue
                q = Q()
                for lookup in lookups:
                    q |= Q(**{f"{lookup}_id": center.id})
                qs = model._default_manager.filter(q).order_by("pk").distinct()
            serialized = serializers.serialize("json", qs)
            objects.extend(json.loads(serialized))

    export_path = _build_center_export_path(center)
    payload = {
        "meta": {
            "type": "center_scoped_snapshot",
            "schema_version": 2,
            "center_id": center.id,
            "center_slug": center.slug,
            "generated_at": timezone.now().isoformat(),
            "object_count": len(objects),
            "skipped_models": [m._meta.label for m in skipped_models],
            "migrations": _collect_migration_state(),
        },
        "objects": objects,
    }
    # Backup fayli — compact JSON (odam o'qimaydi, faqat dastur). ~30-40% kichikroq.
    with export_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    logger.info(
        "Center snapshot exported: center=%s file=%s objects=%s size=%d",
        center.slug,
        export_path,
        len(objects),
        export_path.stat().st_size,
    )
    return export_path


def backup_full_database() -> Path:
    try:
        credentials = _get_default_db_credentials()
    except ValueError as exc:
        return backup_full_database_fixture(f"PostgreSQL sozlanmagan: {exc}")

    if shutil.which("pg_dump") is None:
        return backup_full_database_fixture("pg_dump topilmadi")

    backup_path = _build_full_backup_path()
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
        return backup_full_database_fixture(f"pg_dump xatosi: {error_text}")

    logger.info("Full PostgreSQL backup created: file=%s", backup_path)
    return backup_path


def backup_full_database_fixture(reason: str) -> Path:
    """
    Full DB uchun portable fallback: Django dumpdata JSON yaratib gzip qiladi.

    Render image ichida `pg_dump` bo'lmasa ham kunlik full backup Telegramga
    borishi uchun kerak.
    """
    backup_path = _build_full_fixture_backup_path()
    temp_path = backup_path.with_suffix("")
    temp_path.unlink(missing_ok=True)
    backup_path.unlink(missing_ok=True)

    logger.warning("PostgreSQL dump fallback ishlatilmoqda: %s", reason)
    call_command(
        "dumpdata",
        output=str(temp_path),
        indent=2,
        use_natural_foreign_keys=True,
        use_natural_primary_keys=True,
        verbosity=0,
    )
    with temp_path.open("rb") as source, gzip.open(backup_path, "wb") as target:
        shutil.copyfileobj(source, target)
    temp_path.unlink(missing_ok=True)

    logger.info(
        "Full Django fixture backup created: file=%s size=%d bytes",
        backup_path,
        backup_path.stat().st_size,
    )
    return backup_path


# ────────────────────────────────────────────────────────────────────────────
# TELEGRAM – SYNC (requests, HECH QANDAY async/event-loop muammo yo'q)
# ────────────────────────────────────────────────────────────────────────────

def send_file_to_telegram(
    file_path: str | Path,
    caption: str | None = None,
    timeout: int | None = None,
) -> None:
    """
    Faylni Telegram guruhga document sifatida yuboradi.

    faqat `requests` ishlatadi – aiogram/asyncio event-loop muammo yo'q.

    Timeout fayl hajmiga qarab avtomatik moslashadi (katta SQL dump uchun 600s).

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
            "BACKUP_BOT_TOKEN yoki TELEGRAM_BOT_TOKEN/BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan! "
            "Render Dashboard → Environment Variables ga qo'shing."
        )
    if not group_id:
        raise ValueError(
            "BACKUP_GROUP_ID yoki TELEGRAM_GROUP_ID muhit o'zgaruvchisi o'rnatilmagan! "
            "Render Dashboard → Environment Variables ga qo'shing."
        )

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Backup fayli topilmadi: {path}")

    size = path.stat().st_size
    if timeout is None:
        timeout = (
            TELEGRAM_SEND_TIMEOUT_LARGE
            if size > 10 * 1024 * 1024  # 10 MB dan katta = sekin upload
            else TELEGRAM_SEND_TIMEOUT_DEFAULT
        )

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    caption_text = caption or path.name

    logger.info(
        "Telegram yuborish boshlandi: file=%s size=%d bytes chat_id=%s timeout=%ds",
        path.name,
        size,
        group_id,
        timeout,
    )

    with path.open("rb") as fh:
        resp = requests.post(
            url,
            data={"chat_id": str(group_id), "caption": caption_text},
            files={"document": (path.name, fh, "application/octet-stream")},
            timeout=timeout,
        )

    try:
        result = resp.json()
    except Exception:
        result = {}

    if not resp.ok or not result.get("ok"):
        err_desc = result.get("description", resp.text[:400])
        raise RuntimeError(
            f"Telegram API xatosi [{resp.status_code}]: {err_desc}\n"
            f"  Chat ID: {group_id}"
        )

    logger.info("✅ Telegram muvaffaqiyatli yuborildi: file=%s", path.name)


def validate_telegram_destination(
    token: str | None = None,
    group_id: str | None = None,
) -> dict[str, Any]:
    """
    Token va backup chatni oldindan tekshiradi.

    Guruh noto'g'ri bo'lsa yoki bot guruhga qo'shilmagan bo'lsa, backup fayllarni
    yaratib vaqt ketkazmasdan aniq xato qaytaradi.
    """
    token = (token or _get_bot_token()).strip()
    group_id = (group_id or _get_group_id()).strip()
    if not token:
        raise ValueError("BACKUP_BOT_TOKEN yoki TELEGRAM_BOT_TOKEN/BOT_TOKEN env var o'rnatilmagan")
    if not group_id:
        raise ValueError("BACKUP_GROUP_ID yoki TELEGRAM_GROUP_ID env var o'rnatilmagan")

    def _call(method: str, **params: str) -> dict[str, Any]:
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/{method}",
            params=params,
            timeout=15,
        )
        try:
            data = resp.json()
        except Exception:
            data = {}
        if not resp.ok or not data.get("ok"):
            description = data.get("description", resp.text[:400])
            raise RuntimeError(f"Telegram {method} xatosi: {description}")
        return data["result"]

    bot_info = _call("getMe")
    try:
        chat_info = _call("getChat", chat_id=str(group_id))
    except RuntimeError as exc:
        raise RuntimeError(
            f"{exc}. Hozirgi bot=@{bot_info.get('username')} ushbu chatga qo'shilganini "
            "va BACKUP_BOT_TOKEN/BACKUP_GROUP_ID sozlamalari to'g'ri ekanini tekshiring."
        ) from exc
    logger.info(
        "Telegram destination OK: bot=@%s chat=%s type=%s",
        bot_info.get("username"),
        chat_info.get("title") or chat_info.get("username") or group_id,
        chat_info.get("type"),
    )
    return {"bot": bot_info, "chat": chat_info}


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
        "preflight_errors": [],
        "fatal_error": "",
        "gdrive_enabled": is_gdrive_configured(),
        "gdrive_uploaded": 0,
        "gdrive_failed": 0,
    }

    logger.info("=" * 60)
    logger.info("BACKUP JOB BOSHLANDI: %s", timezone.now().isoformat())
    logger.info("=" * 60)

    # ── Env var tekshiruvi ─────────────────────────────────────────────────
    token = _get_bot_token()
    group_id = _get_group_id()
    preflight_errors: list[str] = []
    if not token:
        preflight_errors.append(
            "BACKUP_BOT_TOKEN yoki TELEGRAM_BOT_TOKEN/BOT_TOKEN env var o'rnatilmagan"
        )
    if not group_id:
        preflight_errors.append(
            "BACKUP_GROUP_ID yoki TELEGRAM_GROUP_ID env var o'rnatilmagan"
        )
    if preflight_errors:
        summary["failed"] = 1
        summary["preflight_errors"] = preflight_errors
        summary["fatal_error"] = "; ".join(preflight_errors)
        logger.error(
            "BACKUP JOB TO'XTATILDI: %s. Render cron envVars ni tekshiring.",
            summary["fatal_error"],
        )
        return summary

    logger.info("Token mavjud.")
    logger.info("Group ID: %s", group_id)
    try:
        validate_telegram_destination(token=token, group_id=group_id)
    except Exception as exc:
        summary["failed"] = 1
        summary["fatal_error"] = str(exc)
        logger.error("BACKUP JOB TO'XTATILDI: %s", exc)
        return summary

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
    gdrive_subpath = _gdrive_subfolder_path_for_date()

    if summary["gdrive_enabled"]:
        logger.info("GDrive ulangan — fayllar Telegram'dan keyin Drive'ga ham yuklanadi")
    else:
        logger.info(
            "GDrive ulanmagan (GDRIVE_SERVICE_ACCOUNT_JSON / GDRIVE_FOLDER_ID yo'q) — "
            "faqat Telegram yuboriladi"
        )

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

            # 3. Google Drive – ikkinchi mustaqil manzil (sozlangan bo'lsa)
            if summary["gdrive_enabled"]:
                gdrive_result = safe_upload_file_to_gdrive(backup_path, gdrive_subpath)
                if gdrive_result:
                    summary["gdrive_uploaded"] += 1
                else:
                    summary["gdrive_failed"] += 1

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

    # ── To'liq DB backup ──────────────────────────────────────────────────
    logger.info("── To'liq DB backup ──")
    try:
        full_path = backup_full_database()
        summary["full_backup_file"] = str(full_path)
        summary["files"].append(str(full_path))
        full_backup_type = (
            "PostgreSQL SQL dump"
            if full_path.suffix == ".sql"
            else "Django JSON fixture (gzip)"
        )

        caption = (
            f"🗄️ To'liq DB backup\n"
            f"📅 Sana: {date_str}\n"
            f"🏢 Markazlar soni: {summary['total']}\n"
            f"📁 Fayl: {full_path.name}\n"
            f"🔢 Tur: {full_backup_type}"
        )
        send_file_to_telegram(full_path, caption=caption)
        summary["sent"] += 1
        summary["combined_sent"] = 1
        summary["full_sent"] = 1
        logger.info("✅ To'liq backup yuborildi: file=%s", full_path.name)

        if summary["gdrive_enabled"]:
            gdrive_result = safe_upload_file_to_gdrive(full_path, gdrive_subpath)
            if gdrive_result:
                summary["gdrive_uploaded"] += 1
            else:
                summary["gdrive_failed"] += 1

    except Exception:
        summary["failed"] += 1
        logger.error("❌ To'liq backup XATOLIGI:\n%s", traceback.format_exc())

    # ── Lokal fayllarni tozalash ──────────────────────────────────────────
    try:
        _cleanup_old_local_backups()
    except Exception:
        logger.warning("Lokal tozalashda xato (backup natijasiga ta'sir qilmaydi)", exc_info=True)

    # ── Yakuniy hisobot ────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(
        "BACKUP JOB TUGADI | total=%d backed_up=%d sent=%d "
        "full_sent=%d skipped=%d failed=%d gdrive=%s(+%d/-%d)",
        summary["total"],
        summary["backed_up"],
        summary["sent"],
        summary["full_sent"],
        summary["skipped"],
        summary["failed"],
        "on" if summary["gdrive_enabled"] else "off",
        summary["gdrive_uploaded"],
        summary["gdrive_failed"],
    )
    if summary["failed_centers"]:
        logger.error("XATO bo'lgan markazlar: %s", ", ".join(summary["failed_centers"]))
    logger.info("=" * 60)
    return summary


# ────────────────────────────────────────────────────────────────────────────
# SCHEDULER – BackgroundScheduler (Django WSGI / Gunicorn bilan mos)
# ────────────────────────────────────────────────────────────────────────────

def setup_backup_scheduler() -> "BackgroundScheduler":
    """
    BackgroundScheduler (thread-based) yaratadi.
    Har kuni 17:35 Asia/Tashkent da backup_and_send_all_centers() ishlatadi.

    Django AppConfig.ready() dan chaqiriladi.
    Gunicorn multi-worker: faqat bitta worker uchun
      BACKUP_SCHEDULER_ENABLED=true env var o'rnating.
    """
    global _backup_scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    if _backup_scheduler and _backup_scheduler.running:
        logger.info("Backup scheduler allaqachon ishlamoqda.")
        return _backup_scheduler

    tz = getattr(settings, "TIME_ZONE", BACKUP_SCHEDULE_TZ_FALLBACK)
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(
        backup_and_send_all_centers,
        CronTrigger(hour=BACKUP_SCHEDULE_HOUR, minute=BACKUP_SCHEDULE_MINUTE, timezone=tz),
        id="tenant-db-backup-daily",
        name="tenant-db-backup-daily",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    scheduler.start()
    _backup_scheduler = scheduler
    logger.info("✅ Backup scheduler ishga tushdi: har kuni %s", get_backup_schedule_label(tz))
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
