"""
ChaqmoqApp database backup service.

Daily scheduler, manual management commands and Telegram /db command all use
this module so the behavior is the same in local and production.
"""

from __future__ import annotations

import json
import logging
import os
import gzip
import shutil
import sqlite3
import subprocess
import time
import traceback
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management import call_command
from django.db import connection, models, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

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
CENTER_LOOKUP_MAX_DEPTH = 3
CENTER_LOOKUP_EXCLUDED_FIELDS = {"deleted_by", "restored_by"}
BACKUP_SCHEDULE_TZ_FALLBACK = "Asia/Tashkent"
BACKUP_SEND_TIME_FALLBACK = "18:00"
BACKUP_SCHEDULER_JOB_ID = "tenant-db-backup-daily-send-telegram"
TELEGRAM_SEND_TIMEOUT_DEFAULT = 120
TELEGRAM_SEND_TIMEOUT_LARGE = int(os.getenv("TELEGRAM_SEND_TIMEOUT_LARGE", "180"))
TELEGRAM_CONNECT_TIMEOUT = int(os.getenv("TELEGRAM_CONNECT_TIMEOUT", "20"))
TELEGRAM_MAX_DOCUMENT_SIZE_MB = int(os.getenv("TELEGRAM_MAX_DOCUMENT_SIZE_MB", "49"))
TELEGRAM_ZIP_MIN_SIZE_MB = int(os.getenv("TELEGRAM_ZIP_MIN_SIZE_MB", "8"))
TELEGRAM_SEND_RETRIES = int(os.getenv("TELEGRAM_SEND_RETRIES", "2"))


def _parse_send_time(value: str | None) -> tuple[int, int]:
    raw = (value or BACKUP_SEND_TIME_FALLBACK).strip()
    try:
        hour_text, minute_text = raw.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"BACKUP_SEND_TIME noto'g'ri formatda: {raw!r}. Format: HH:MM") from exc
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"BACKUP_SEND_TIME noto'g'ri qiymat: {raw!r}. Format: HH:MM")
    return hour, minute


def _get_backup_timezone_name() -> str:
    return (
        str(getattr(settings, "BACKUP_TIMEZONE", "") or "").strip()
        or str(os.environ.get("BACKUP_TIMEZONE", "") or "").strip()
        or str(getattr(settings, "TIME_ZONE", "") or "").strip()
        or BACKUP_SCHEDULE_TZ_FALLBACK
    )


def _get_backup_zoneinfo() -> ZoneInfo:
    tz_name = _get_backup_timezone_name()
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"BACKUP_TIMEZONE noto'g'ri: {tz_name!r}") from exc


def _get_backup_send_time() -> tuple[int, int]:
    return _parse_send_time(
        str(getattr(settings, "BACKUP_SEND_TIME", "") or "")
        or os.environ.get("BACKUP_SEND_TIME")
        or BACKUP_SEND_TIME_FALLBACK
    )


BACKUP_SCHEDULE_HOUR, BACKUP_SCHEDULE_MINUTE = _parse_send_time(
    os.environ.get("BACKUP_SEND_TIME") or BACKUP_SEND_TIME_FALLBACK
)
BACKUP_LOCAL_RETENTION_DAYS = int(os.getenv("BACKUP_KEEP_DAYS", "7"))


def get_backup_schedule_label(timezone_name: str | None = None) -> str:
    hour, minute = _get_backup_send_time()
    tz_name = timezone_name or _get_backup_timezone_name()
    return f"{hour:02d}:{minute:02d} {tz_name}"


def _backup_now() -> timezone.datetime:
    return timezone.localtime(timezone.now(), _get_backup_zoneinfo())


def _timestamp_label(now: timezone.datetime | None = None) -> str:
    return (now or _backup_now()).strftime("%Y-%m-%d_%H-%M")


def _backup_date_label(now: timezone.datetime | None = None) -> str:
    return (now or _backup_now()).strftime("%Y-%m-%d")


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
    today = _backup_now().date()
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
    """Token priority: TELEGRAM_BOT_TOKEN -> BOT_TOKEN -> BACKUP_BOT_TOKEN."""
    _load_backup_env_files()
    return (
        str(getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
        or str(os.environ.get("TELEGRAM_BOT_TOKEN", "") or "").strip()
        or str(os.environ.get("BOT_TOKEN", "") or "").strip()
        or str(getattr(settings, "BACKUP_BOT_TOKEN", "") or "").strip()
        or str(os.environ.get("BACKUP_BOT_TOKEN", "") or "").strip()
    )


def _get_group_id() -> str:
    """Chat priority: TELEGRAM_BACKUP_CHAT_ID -> BACKUP_GROUP_ID -> TELEGRAM_GROUP_ID."""
    _load_backup_env_files()
    return (
        str(getattr(settings, "TELEGRAM_BACKUP_CHAT_ID", "") or "").strip()
        or str(os.environ.get("TELEGRAM_BACKUP_CHAT_ID", "") or "").strip()
        or str(getattr(settings, "BACKUP_GROUP_ID", "") or "").strip()
        or str(os.environ.get("BACKUP_GROUP_ID", "") or "").strip()
        or str(getattr(settings, "TELEGRAM_GROUP_ID", "") or "").strip()
        or str(os.environ.get("TELEGRAM_GROUP_ID", "") or "").strip()
    )


def _parse_csv_ids(raw: str | None) -> set[str]:
    values: set[str] = set()
    for item in str(raw or "").replace(";", ",").split(","):
        item = item.strip()
        if item:
            values.add(item)
    return values


def get_admin_telegram_ids() -> set[str]:
    _load_backup_env_files()
    return _parse_csv_ids(
        str(getattr(settings, "ADMIN_TELEGRAM_IDS", "") or "")
        or os.environ.get("ADMIN_TELEGRAM_IDS", "")
    )


def is_authorized_telegram_backup_request(
    chat_id: int | str | None,
    user_id: int | str | None,
) -> tuple[bool, str]:
    """
    /db command faqat TELEGRAM_BACKUP_CHAT_ID ichida va adminlardan ishlaydi.

    Admin manbalari:
      1. ADMIN_TELEGRAM_IDS env
      2. accounts.BotAdmin
      3. Telegram ID bog'langan Django superuser
    """
    allowed_chat_id = _get_group_id()
    current_chat_id = str(chat_id or "").strip()
    current_user_id = str(user_id or "").strip()

    if not allowed_chat_id:
        return False, "TELEGRAM_BACKUP_CHAT_ID env sozlanmagan."
    if current_chat_id != str(allowed_chat_id):
        return False, "Bu buyruq faqat ruxsat berilgan backup guruhida ishlaydi."
    if not current_user_id:
        return False, "Telegram foydalanuvchi ID aniqlanmadi."

    admin_ids = get_admin_telegram_ids()
    if admin_ids:
        if current_user_id in admin_ids:
            return True, ""
        return False, "Sizga /db backup buyrug'i uchun ruxsat berilmagan."

    try:
        from accounts.models import BotAdmin, User

        if BotAdmin.objects.filter(telegram_id=current_user_id).exists():
            return True, ""
        if User.objects.filter(is_superuser=True, telegram_id=current_user_id).exists():
            return True, ""
    except Exception:
        logger.exception("Telegram admin ruxsatini tekshirishda xatolik")
        return False, "Admin ruxsatini tekshirishda xatolik yuz berdi."

    return (
        False,
        "ADMIN_TELEGRAM_IDS env yoki BotAdmin orqali ruxsat berilgan admin topilmadi.",
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


def _safe_slug(value: str | None, fallback: str = "center") -> str:
    return slugify(value or "")[:80] or fallback


def _build_center_export_path(
    center: Center,
    timestamp_label: str | None = None,
    suffix: str = ".json",
) -> Path:
    ts = timestamp_label or _timestamp_label()
    slug = _safe_slug(center.slug, f"center-{center.pk}")
    return _get_backup_root() / f"center_{slug}_backup_{ts}{suffix}"


def _build_global_backup_path(suffix: str, timestamp_label: str | None = None) -> Path:
    ts = timestamp_label or _timestamp_label()
    return _get_backup_root() / f"global_backup_{ts}{suffix}"


def _build_full_fixture_backup_path() -> Path:
    return _build_global_backup_path(".json.gz")


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


def _build_pg_dump_url_command(database_url: str, backup_path: Path) -> list[str]:
    return [
        "pg_dump",
        "--dbname",
        database_url,
        "-f",
        str(backup_path),
        "--no-owner",
        "--no-privileges",
        "-Fp",
    ]


def _pg_dump_missing_error() -> RuntimeError:
    return RuntimeError(
        "pg_dump topilmadi. PostgreSQL backup uchun pg_dump PATH ichida bo'lishi shart. "
        "Render Native Runtime OS-level paketlarni apt/sudo orqali o'rnatishni kafolatlamaydi; "
        "production uchun Docker image ichida postgresql-client o'rnating yoki pg_dump binary "
        "ni build paytida /opt/render/project ichiga qo'shib PATH ga kiriting."
    )


def _database_engine_name(db_config: dict[str, Any]) -> str:
    database_url = str(os.environ.get("DATABASE_URL", "") or "").lower()
    if database_url.startswith(("postgres://", "postgresql://")):
        return "postgresql"
    if database_url.startswith("sqlite://"):
        return "sqlite"
    engine = str(db_config.get("ENGINE", "") or "").lower()
    if "postgresql" in engine or "postgis" in engine:
        return "postgresql"
    if "sqlite" in engine:
        return "sqlite"
    return engine or "unknown"


def _sqlite_backup(source_path: Path, backup_path: Path) -> Path:
    if not source_path.exists():
        raise FileNotFoundError(f"SQLite database topilmadi: {source_path}")

    backup_path.unlink(missing_ok=True)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(str(source_path), timeout=60)
    target = sqlite3.connect(str(backup_path), timeout=60)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()

    logger.info("SQLite backup yaratildi: source=%s file=%s size=%d", source_path, backup_path, backup_path.stat().st_size)
    return backup_path


def _postgres_backup(
    db_config: dict[str, Any],
    backup_path: Path,
    *,
    database_url: str | None = None,
) -> Path:
    if shutil.which("pg_dump") is None:
        raise _pg_dump_missing_error()

    backup_path.unlink(missing_ok=True)
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PGCONNECT_TIMEOUT"] = env.get("PGCONNECT_TIMEOUT", "15")
    options = db_config.get("OPTIONS") or {}
    sslmode = str(options.get("sslmode") or os.environ.get("PGSSLMODE") or "").strip()
    if sslmode:
        env["PGSSLMODE"] = sslmode

    if database_url:
        command = _build_pg_dump_url_command(database_url, backup_path)
    else:
        credentials = {
            "name": str(db_config.get("NAME", "") or "").strip(),
            "user": str(db_config.get("USER", "") or "").strip(),
            "password": str(db_config.get("PASSWORD", "") or "").strip(),
            "host": str(db_config.get("HOST", "") or "localhost").strip() or "localhost",
            "port": str(db_config.get("PORT", "") or "5432").strip() or "5432",
        }
        missing = [key for key in ("name", "user") if not credentials[key]]
        if missing:
            raise ValueError(f"PostgreSQL credential yetishmayapti: {', '.join(missing)}")
        if credentials["password"]:
            env["PGPASSWORD"] = credentials["password"]
        command = _build_pg_dump_command(credentials, backup_path)

    result = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=int(os.environ.get("PG_DUMP_TIMEOUT_SECONDS", "900")),
    )
    if result.returncode != 0:
        backup_path.unlink(missing_ok=True)
        error_text = (result.stderr or result.stdout or f"pg_dump exited with code {result.returncode}").strip()
        raise RuntimeError(f"pg_dump xatosi: {error_text}")

    logger.info("PostgreSQL backup yaratildi: file=%s size=%d", backup_path, backup_path.stat().st_size)
    return backup_path


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
    export_model_set = set(export_models)
    def find_paths(
        model: type[models.Model],
        depth: int,
        visiting: set[type[models.Model]],
    ) -> list[str]:
        if model is Center:
            return [""]
        if depth >= CENTER_LOOKUP_MAX_DEPTH:
            return []

        paths: set[str] = set()
        visiting.add(model)
        for field in model._meta.fields:
            if field.name in CENTER_LOOKUP_EXCLUDED_FIELDS:
                continue
            if not isinstance(field, (models.ForeignKey, models.OneToOneField)):
                continue
            related_model = field.related_model
            if related_model is None:
                continue
            if related_model not in export_model_set and related_model is not Center:
                continue
            if related_model in visiting:
                continue

            for parent_lookup in find_paths(related_model, depth + 1, set(visiting)):
                if parent_lookup:
                    paths.add(f"{field.name}__{parent_lookup}")
                else:
                    paths.add(field.name)

        return sorted(paths)

    lookup_map: dict[type[models.Model], list[str]] = {}
    for model in export_models:
        paths = find_paths(model, 0, set())
        if paths:
            lookup_map[model] = paths

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


def export_center_snapshot(center: Center, timestamp_label: str | None = None) -> Path:
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

    export_path = _build_center_export_path(center, timestamp_label=timestamp_label)
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


def backup_global_database(timestamp_label: str | None = None) -> Path:
    default_db = (getattr(settings, "DATABASES", {}) or {}).get("default", {})
    if not default_db:
        raise RuntimeError("settings.DATABASES['default'] topilmadi")

    engine = _database_engine_name(default_db)
    if engine == "sqlite":
        db_name = default_db.get("NAME")
        source_path = Path(db_name) if isinstance(db_name, (str, Path)) else Path(str(db_name))
        return _sqlite_backup(source_path, _build_global_backup_path(".sqlite3", timestamp_label))

    if engine == "postgresql":
        database_url = str(os.environ.get("DATABASE_URL", "") or "").strip()
        return _postgres_backup(
            default_db,
            _build_global_backup_path(".sql", timestamp_label),
            database_url=database_url or None,
        )

    raise RuntimeError(f"Qo'llab-quvvatlanmagan database engine: {default_db.get('ENGINE') or engine}")


def backup_full_database() -> Path:
    """Backward-compatible alias for old commands/tests."""
    return backup_global_database()


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


@dataclass
class BackupArtifact:
    path: Path
    scope: str
    label: str
    kind: str
    center_slug: str = ""
    center_name: str = ""

    @property
    def size(self) -> int:
        return self.path.stat().st_size if self.path.exists() else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "name": self.path.name,
            "scope": self.scope,
            "label": self.label,
            "kind": self.kind,
            "center_slug": self.center_slug,
            "center_name": self.center_name,
            "size": self.size,
        }


def _default_db_identity() -> tuple[str, str, str, str] | None:
    default_db = (getattr(settings, "DATABASES", {}) or {}).get("default", {})
    if _database_engine_name(default_db) != "postgresql":
        return None
    return (
        str(default_db.get("NAME", "") or "").strip(),
        str(default_db.get("USER", "") or "").strip(),
        str(default_db.get("HOST", "") or "localhost").strip() or "localhost",
        str(default_db.get("PORT", "") or "5432").strip() or "5432",
    )


def _center_database_config(center: Center) -> dict[str, Any] | None:
    db_name = str(getattr(center, "db_name", "") or "").strip()
    if not db_name:
        return None
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": db_name,
        "USER": str(getattr(center, "db_user", "") or "").strip(),
        "PASSWORD": str(getattr(center, "db_password", "") or "").strip(),
        "HOST": str(getattr(center, "db_host", "") or "localhost").strip() or "localhost",
        "PORT": str(getattr(center, "db_port", "") or "5432").strip() or "5432",
    }


def _center_has_separate_database(center: Center) -> bool:
    config = _center_database_config(center)
    if not config:
        return False
    default_identity = _default_db_identity()
    if default_identity is None:
        return True
    center_identity = (
        str(config.get("NAME", "") or "").strip(),
        str(config.get("USER", "") or "").strip(),
        str(config.get("HOST", "") or "localhost").strip() or "localhost",
        str(config.get("PORT", "") or "5432").strip() or "5432",
    )
    return bool(default_identity and center_identity != default_identity)


def _iter_backup_centers(center_slugs: list[str] | None = None) -> list[Center]:
    qs = Center.objects.only(
        "id",
        "slug",
        "name",
        "status",
        "db_name",
        "db_user",
        "db_password",
        "db_host",
        "db_port",
    ).order_by("id")
    if center_slugs:
        qs = qs.filter(slug__in=center_slugs)
    centers = list(qs)
    if center_slugs:
        found = {center.slug for center in centers}
        missing = sorted(set(center_slugs) - found)
        if missing:
            raise ValueError(f"Markaz sluglari topilmadi: {', '.join(missing)}")
    return centers


def backup_center_database(center: Center, timestamp_label: str | None = None) -> BackupArtifact:
    slug = _safe_slug(center.slug, f"center-{center.pk}")
    if _center_has_separate_database(center):
        db_config = _center_database_config(center)
        assert db_config is not None
        path = _build_center_export_path(center, timestamp_label=timestamp_label, suffix=".sql")
        _postgres_backup(db_config, path)
        kind = "postgresql_sql"
        label = f"Markaz DB backup: {center.name} ({slug})"
    else:
        path = export_center_snapshot(center, timestamp_label=timestamp_label)
        kind = "tenant_json_snapshot"
        label = f"Markaz tenant snapshot: {center.name} ({slug})"

    return BackupArtifact(
        path=path,
        scope="center",
        label=label,
        kind=kind,
        center_slug=slug,
        center_name=center.name,
    )


def backup_global_database_artifact(timestamp_label: str | None = None) -> BackupArtifact:
    path = backup_global_database(timestamp_label=timestamp_label)
    kind = "sqlite3" if path.suffix == ".sqlite3" else "postgresql_sql"
    return BackupArtifact(
        path=path,
        scope="global",
        label="Umumiy/global database backup",
        kind=kind,
    )


def create_all_backups_zip(
    artifacts: list[BackupArtifact],
    timestamp_label: str | None = None,
) -> BackupArtifact:
    ts = timestamp_label or _timestamp_label()
    zip_path = _get_backup_root() / f"all_databases_backup_{ts}.zip"
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for artifact in artifacts:
            archive.write(artifact.path, artifact.path.name)
    logger.info("All-backups ZIP yaratildi: file=%s size=%d", zip_path, zip_path.stat().st_size)
    return BackupArtifact(
        path=zip_path,
        scope="all",
        label="Barcha database backuplar ZIP",
        kind="zip",
    )


def create_database_backups(
    *,
    center_slugs: list[str] | None = None,
    include_global: bool = True,
    include_centers: bool = True,
) -> dict[str, Any]:
    """
    Global DB va har bir markaz backup faylini yaratadi, Telegramga yubormaydi.
    """
    now = _backup_now()
    ts = _timestamp_label(now)
    summary: dict[str, Any] = {
        "started_at": now.isoformat(),
        "timestamp": ts,
        "date": _backup_date_label(now),
        "total": 0,
        "backed_up": 0,
        "failed": 0,
        "failed_centers": [],
        "errors": [],
        "artifacts": [],
        "files": [],
        "full_backup_file": None,
    }

    logger.info("=" * 60)
    logger.info("DATABASE BACKUP YARATISH BOSHLANDI: %s", now.isoformat())
    logger.info("=" * 60)

    if include_global:
        logger.info("── Global DB backup ──")
        try:
            artifact = backup_global_database_artifact(timestamp_label=ts)
            summary["artifacts"].append(artifact.to_dict())
            summary["files"].append(str(artifact.path))
            summary["full_backup_file"] = str(artifact.path)
            summary["backed_up"] += 1
            logger.info("✅ Global DB backup yaratildi: %s", artifact.path.name)
        except Exception as exc:
            summary["failed"] += 1
            summary["errors"].append({"scope": "global", "error": str(exc)})
            logger.error("❌ Global DB backup xatoligi:\n%s", traceback.format_exc())

    centers: list[Center] = []
    if include_centers:
        centers = _iter_backup_centers(center_slugs)
        summary["total"] = len(centers)
        logger.info("Backup olinadigan markazlar: %d ta", len(centers))
        for center in centers:
            logger.info("── Markaz: %s (%s) ──", center.name, center.slug)
            try:
                artifact = backup_center_database(center, timestamp_label=ts)
                summary["artifacts"].append(artifact.to_dict())
                summary["files"].append(str(artifact.path))
                summary["backed_up"] += 1
                logger.info(
                    "✅ Markaz backup yaratildi: center=%s file=%s kind=%s",
                    center.slug,
                    artifact.path.name,
                    artifact.kind,
                )
            except Exception as exc:
                summary["failed"] += 1
                summary["failed_centers"].append(center.slug)
                summary["errors"].append(
                    {"scope": "center", "center": center.slug, "error": str(exc)}
                )
                logger.error("❌ Markaz backup xatoligi: center=%s\n%s", center.slug, traceback.format_exc())

    try:
        keep_days = int(getattr(settings, "BACKUP_KEEP_DAYS", BACKUP_LOCAL_RETENTION_DAYS))
        _cleanup_old_local_backups(max_age_days=keep_days)
    except Exception:
        logger.warning("Lokal backup tozalashda xato", exc_info=True)

    logger.info(
        "DATABASE BACKUP YARATISH TUGADI | centers=%d backed_up=%d failed=%d files=%d",
        summary["total"],
        summary["backed_up"],
        summary["failed"],
        len(summary["files"]),
    )
    return summary


# ────────────────────────────────────────────────────────────────────────────
# TELEGRAM – SYNC (requests, HECH QANDAY async/event-loop muammo yo'q)
# ────────────────────────────────────────────────────────────────────────────

def _require_telegram_settings() -> tuple[str, str]:
    token = _get_bot_token()
    group_id = _get_group_id()
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN env o'rnatilmagan. "
            "Render/Docker/Local .env ichida TELEGRAM_BOT_TOKEN qo'shing."
        )
    if not group_id:
        raise ValueError(
            "TELEGRAM_BACKUP_CHAT_ID env o'rnatilmagan. "
            "Backup yuboriladigan guruh chat_id qiymatini qo'shing."
        )
    return token, group_id


def _telegram_api_request(
    method: str,
    *,
    token: str | None = None,
    http_method: str = "post",
    timeout: int = 30,
    **params: Any,
) -> dict[str, Any]:
    token = (token or _get_bot_token()).strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN env o'rnatilmagan")
    url = f"https://api.telegram.org/bot{token}/{method}"
    is_get = http_method.lower() == "get"
    if is_get:
        resp = requests.get(url, params=params, timeout=timeout)
    else:
        resp = requests.post(url, data=params, timeout=timeout)
    try:
        data = resp.json()
    except Exception:
        data = {}
    if not resp.ok or not data.get("ok"):
        description = data.get("description", resp.text[:400])
        raise RuntimeError(f"Telegram {method} xatosi [{resp.status_code}]: {description}")
    return data["result"]


def send_text_to_telegram(text: str, *, chat_id: str | None = None) -> None:
    token, default_chat_id = _require_telegram_settings()
    target_chat_id = chat_id or default_chat_id
    _telegram_api_request(
        "sendMessage",
        token=token,
        chat_id=str(target_chat_id),
        text=text,
        timeout=30,
    )
    logger.info("Telegram xabar yuborildi: chat_id=%s text=%s", target_chat_id, text[:80])


def _zip_single_file_for_telegram(path: Path) -> Path:
    zip_path = path.with_suffix(path.suffix + ".zip")
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(path, path.name)
    logger.info(
        "Telegram uchun fayl zip qilindi: original=%s zipped=%s size=%d",
        path.name,
        zip_path.name,
        zip_path.stat().st_size,
    )
    return zip_path


def _prepare_document_for_telegram(path: Path) -> Path:
    max_bytes = TELEGRAM_MAX_DOCUMENT_SIZE_MB * 1024 * 1024
    zip_min_bytes = TELEGRAM_ZIP_MIN_SIZE_MB * 1024 * 1024
    original_size = path.stat().st_size
    compressible_suffixes = {".sql", ".json", ".sqlite3"}

    if (
        path.suffix.lower() != ".zip"
        and path.suffix.lower() in compressible_suffixes
        and original_size >= zip_min_bytes
    ):
        zipped = _zip_single_file_for_telegram(path)
        if zipped.stat().st_size < original_size or original_size > max_bytes:
            return zipped
        zipped.unlink(missing_ok=True)

    if original_size <= max_bytes:
        return path

    zipped = path if path.suffix == ".zip" else _zip_single_file_for_telegram(path)
    if zipped.stat().st_size > max_bytes:
        raise RuntimeError(
            f"Backup fayli Telegram limiti uchun juda katta: {zipped.name} "
            f"({zipped.stat().st_size} bytes). TELEGRAM_MAX_DOCUMENT_SIZE_MB ni tekshiring "
            "yoki backupni tashqi storagega yuklang."
        )
    return zipped


def _format_file_size(path: Path) -> str:
    size_mb = path.stat().st_size / (1024 * 1024)
    return f"{size_mb:.1f} MB"


def _caption_for_artifact(artifact: BackupArtifact | dict[str, Any]) -> str:
    if isinstance(artifact, dict):
        path = Path(str(artifact["path"]))
        scope = artifact.get("scope", "")
        kind = artifact.get("kind", "")
        label = artifact.get("label", "")
        center_name = artifact.get("center_name", "")
        center_slug = artifact.get("center_slug", "")
    else:
        path = artifact.path
        scope = artifact.scope
        kind = artifact.kind
        label = artifact.label
        center_name = artifact.center_name
        center_slug = artifact.center_slug

    date_label = _backup_date_label()
    if scope == "global":
        return (
            "🗄️ Global database backup\n"
            f"📅 Sana: {date_label}\n"
            f"📁 Fayl: {path.name}\n"
            f"🔢 Tur: {kind}"
        )
    if scope == "center":
        return (
            "📦 Markaz database backup\n"
            f"🏢 Markaz: {center_name} ({center_slug})\n"
            f"📅 Sana: {date_label}\n"
            f"📁 Fayl: {path.name}\n"
            f"🔢 Tur: {kind}"
        )
    if scope == "all":
        return (
            "🗜️ Barcha database backuplar\n"
            f"📅 Sana: {date_label}\n"
            f"📁 Fayl: {path.name}\n"
            "Ichida global va har bir markaz backup fayli alohida."
        )
    return f"{label}\n📁 Fayl: {path.name}\n🔢 Tur: {kind}"


def _artifact_from_dict(data: dict[str, Any]) -> BackupArtifact:
    return BackupArtifact(
        path=Path(str(data["path"])),
        scope=str(data.get("scope", "")),
        label=str(data.get("label", "")),
        kind=str(data.get("kind", "")),
        center_slug=str(data.get("center_slug", "")),
        center_name=str(data.get("center_name", "")),
    )


def send_file_to_telegram(
    file_path: str | Path,
    caption: str | None = None,
    timeout: int | None = None,
) -> Path:
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
    token, group_id = _require_telegram_settings()

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Backup fayli topilmadi: {path}")
    path = _prepare_document_for_telegram(path)

    size = path.stat().st_size
    if timeout is None:
        timeout = (
            TELEGRAM_SEND_TIMEOUT_LARGE
            if size > 10 * 1024 * 1024  # 10 MB dan katta = sekin upload
            else TELEGRAM_SEND_TIMEOUT_DEFAULT
        )

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    caption_text = caption or path.name

    timeout_config = (TELEGRAM_CONNECT_TIMEOUT, timeout)
    attempts = max(1, TELEGRAM_SEND_RETRIES + 1)
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        logger.info(
            "Telegram yuborish boshlandi: file=%s size=%d bytes chat_id=%s timeout=%ss attempt=%d/%d",
            path.name,
            size,
            group_id,
            timeout,
            attempt,
            attempts,
        )

        try:
            with path.open("rb") as fh:
                resp = requests.post(
                    url,
                    data={"chat_id": str(group_id), "caption": caption_text},
                    files={"document": (path.name, fh, "application/octet-stream")},
                    timeout=timeout_config,
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

            logger.info(
                "✅ Telegram muvaffaqiyatli yuborildi: file=%s elapsed=%.1fs",
                path.name,
                time.monotonic() - started,
            )
            return path
        except requests.RequestException as exc:
            last_error = exc
            logger.warning(
                "Telegram upload urinishida xato: file=%s attempt=%d/%d error=%s",
                path.name,
                attempt,
                attempts,
                exc,
                exc_info=True,
            )
            if attempt < attempts:
                time.sleep(min(5 * attempt, 15))
                continue
            break
        except RuntimeError:
            raise

    raise RuntimeError(f"Telegram upload timeout/tarmoq xatosi: {path.name}: {last_error}")


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
        raise ValueError("TELEGRAM_BOT_TOKEN env var o'rnatilmagan")
    if not group_id:
        raise ValueError("TELEGRAM_BACKUP_CHAT_ID env var o'rnatilmagan")

    def _call(method: str, **params: str) -> dict[str, Any]:
        return _telegram_api_request(
            method,
            token=token,
            http_method="get",
            timeout=15,
            **params,
        )

    bot_info = _call("getMe")
    try:
        chat_info = _call("getChat", chat_id=str(group_id))
    except RuntimeError as exc:
        raise RuntimeError(
            f"{exc}. Hozirgi bot=@{bot_info.get('username')} ushbu chatga qo'shilganini "
            "va TELEGRAM_BOT_TOKEN/TELEGRAM_BACKUP_CHAT_ID sozlamalari to'g'ri ekanini tekshiring."
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

def send_database_backups_to_telegram(
    *,
    center_slugs: list[str] | None = None,
    include_global: bool = True,
    include_centers: bool = True,
    send_zip: bool = False,
    zip_only: bool = False,
    notify_start: bool = True,
    notify_finish: bool = True,
    notify_error: bool = True,
    notify_progress: bool = True,
) -> dict[str, Any]:
    """
    Real-time backup yaratadi va Telegram backup guruhiga yuboradi.
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
        "sent_files": [],
        "full_backup_file": None,
        "failed_centers": [],
        "preflight_errors": [],
        "fatal_error": "",
        "errors": [],
        "gdrive_enabled": is_gdrive_configured(),
        "gdrive_uploaded": 0,
        "gdrive_failed": 0,
    }

    logger.info("=" * 60)
    logger.info("BACKUP TELEGRAM JOB BOSHLANDI: %s", _backup_now().isoformat())
    logger.info("=" * 60)

    try:
        token, group_id = _require_telegram_settings()
        logger.info("Telegram backup chat_id=%s", group_id)
        validate_telegram_destination(token=token, group_id=group_id)
    except Exception as exc:
        summary["failed"] = 1
        summary["fatal_error"] = str(exc)
        summary["preflight_errors"] = [str(exc)]
        logger.error("❌ Backup yuborishda xatolik: %s", exc, exc_info=True)
        return summary

    try:
        if notify_start:
            send_text_to_telegram("⏳ Database backup tayyorlanmoqda...")

        backup_summary = create_database_backups(
            center_slugs=center_slugs,
            include_global=include_global,
            include_centers=include_centers,
        )
        summary.update(
            {
                "total": backup_summary.get("total", 0),
                "backed_up": backup_summary.get("backed_up", 0),
                "failed": backup_summary.get("failed", 0),
                "files": list(backup_summary.get("files", [])),
                "full_backup_file": backup_summary.get("full_backup_file"),
                "failed_centers": list(backup_summary.get("failed_centers", [])),
                "errors": list(backup_summary.get("errors", [])),
            }
        )
        artifacts = [_artifact_from_dict(item) for item in backup_summary.get("artifacts", [])]

        if not artifacts:
            raise RuntimeError("Yuborish uchun backup fayl yaratilmadi")

        artifacts_to_send = list(artifacts)
        if send_zip or zip_only:
            zip_artifact = create_all_backups_zip(artifacts, timestamp_label=backup_summary.get("timestamp"))
            summary["files"].append(str(zip_artifact.path))
            if zip_only:
                artifacts_to_send = [zip_artifact]
            else:
                artifacts_to_send.append(zip_artifact)

        if notify_progress:
            try:
                send_text_to_telegram(
                    f"📦 Backup tayyorlandi: {len(artifacts)} ta fayl. Telegramga yuborilmoqda..."
                )
            except Exception:
                logger.warning("Telegram progress xabar yuborilmadi", exc_info=True)

        gdrive_subpath = _gdrive_subfolder_path_for_date()
        for artifact in artifacts_to_send:
            try:
                prepared_path = artifact.path
                if notify_progress:
                    try:
                        prepared_path = _prepare_document_for_telegram(artifact.path)
                        send_text_to_telegram(
                            f"📤 Yuborilmoqda: {prepared_path.name} ({_format_file_size(prepared_path)})"
                        )
                    except Exception:
                        logger.warning("Telegram per-file progress xabar yuborilmadi", exc_info=True)
                caption = _caption_for_artifact(artifact)
                if prepared_path != artifact.path:
                    caption += f"\n🗜️ Telegramga zip holatida yuborildi: {prepared_path.name}"
                sent_path = send_file_to_telegram(prepared_path, caption=caption)
                summary["sent"] += 1
                summary["sent_files"].append(str(sent_path))
                if artifact.scope == "global":
                    summary["full_sent"] = 1
                if artifact.scope == "all":
                    summary["combined_sent"] = 1
                logger.info("✅ Telegramga backup yuborildi: %s", artifact.path.name)

                if summary["gdrive_enabled"] and artifact.scope != "all":
                    if safe_upload_file_to_gdrive(artifact.path, gdrive_subpath):
                        summary["gdrive_uploaded"] += 1
                    else:
                        summary["gdrive_failed"] += 1
            except Exception as exc:
                summary["failed"] += 1
                summary["errors"].append(
                    {"scope": artifact.scope, "file": str(artifact.path), "error": str(exc)}
                )
                logger.error("❌ Backup yuborishda xatolik: file=%s\n%s", artifact.path, traceback.format_exc())

        if summary["failed"]:
            error_text = summary["fatal_error"] or "; ".join(
                str(item.get("error", item)) for item in summary.get("errors", [])[:3]
            )
            summary["fatal_error"] = error_text or "Backup jarayonida xatolik bor"
            if notify_error:
                send_text_to_telegram(f"❌ Backup yuborilmadi: {summary['fatal_error']}")
        elif notify_finish:
            send_text_to_telegram(f"✅ Database backup yuborildi. Sana: {backup_summary.get('date')}")

    except Exception as exc:
        summary["failed"] += 1
        summary["fatal_error"] = str(exc)
        logger.error("❌ Backup yuborishda xatolik:\n%s", traceback.format_exc())
        if notify_error:
            try:
                send_text_to_telegram(f"❌ Backup yuborilmadi: {exc}")
            except Exception:
                logger.exception("Telegramga error xabar yuborib bo'lmadi")

    logger.info(
        "BACKUP TELEGRAM JOB TUGADI | total=%d backed_up=%d sent=%d failed=%d",
        summary["total"],
        summary["backed_up"],
        summary["sent"],
        summary["failed"],
    )
    return summary


def backup_and_send_all_centers() -> dict[str, Any]:
    """Backward-compatible entrypoint for old cron/tests."""
    return send_database_backups_to_telegram()


# ────────────────────────────────────────────────────────────────────────────
# SCHEDULER – BackgroundScheduler (Django WSGI / Gunicorn bilan mos)
# ────────────────────────────────────────────────────────────────────────────

def setup_backup_scheduler() -> "BackgroundScheduler":
    """
    BackgroundScheduler (thread-based) yaratadi.
    BACKUP_SEND_TIME/BACKUP_TIMEZONE bo'yicha backup_and_send_all_centers() ishlatadi.

    Django AppConfig.ready() dan chaqiriladi.
    Gunicorn/Render production uchun eng ishonchli yo'l: Render Cron -> send_db_backups.
    Web worker ichida faqat BACKUP_SCHEDULER_ENABLED=true bo'lsa yoqing.
    """
    global _backup_scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    if _backup_scheduler and _backup_scheduler.running:
        logger.info("Backup scheduler allaqachon ishlamoqda.")
        return _backup_scheduler

    tz = _get_backup_timezone_name()
    hour, minute = _get_backup_send_time()
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(
        backup_and_send_all_centers,
        CronTrigger(hour=hour, minute=minute, timezone=tz),
        id=BACKUP_SCHEDULER_JOB_ID,
        name=BACKUP_SCHEDULER_JOB_ID,
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

async def run_backup_async(**kwargs: Any) -> dict[str, Any]:
    """
    Bot /db handler uchun async wrapper.
    send_database_backups_to_telegram() ni thread pool da ishlatadi.
    """
    import asyncio
    return await asyncio.to_thread(send_database_backups_to_telegram, **kwargs)
