from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.db import models
from django.utils import timezone

from accounts.models import Center

logger = logging.getLogger(__name__)

_backup_scheduler: AsyncIOScheduler | None = None
CENTER_EXPORT_APPS = {"accounts", "core", "billing", "education", "store", "chaqmoq"}


def _get_backup_root() -> Path:
    backup_root = Path(settings.BASE_DIR) / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    return backup_root


def _get_bot_token() -> str:
    return str(getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()


def _get_group_id() -> str | int:
    raw_group_id = str(getattr(settings, "TELEGRAM_GROUP_ID", "") or "").strip()
    if not raw_group_id:
        return ""
    try:
        return int(raw_group_id)
    except ValueError:
        return raw_group_id


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


async def send_file_to_telegram(file_path: str | Path, caption: str | None = None) -> None:
    token = _get_bot_token()
    group_id = _get_group_id()

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not configured")
    if not group_id:
        raise ValueError("TELEGRAM_GROUP_ID is not configured")

    path = Path(file_path)
    bot = Bot(token=token)
    try:
        await bot.send_document(
            chat_id=group_id,
            document=FSInputFile(str(path), filename=path.name),
            caption=caption or path.name,
        )
    finally:
        await bot.session.close()


def _run_async(coro: Any) -> Any:
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def backup_and_send_all_centers() -> dict[str, Any]:
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

    centers = list(
        Center.objects.filter(status=Center.STATUS_ACTIVE)
        .only("id", "slug", "name", "status")
        .order_by("id")
    )
    summary["total"] = len(centers)

    if not centers:
        logger.info("Tenant backup skipped: no active centers found")
        return summary

    for center in centers:
        try:
            backup_path = export_center_snapshot(center)
            summary["backed_up"] += 1
            summary["files"].append(str(backup_path))
            _run_async(
                send_file_to_telegram(
                    backup_path,
                    caption=(
                        f"Center scoped backup\n"
                        f"Center: {center.slug}\n"
                        f"Date: {timezone.localdate().isoformat()}\n"
                        f"File: {backup_path.name}"
                    ),
                )
            )
            summary["sent"] += 1
            logger.info("Tenant backup sent: center=%s file=%s", center.slug, backup_path)
        except ValueError as exc:
            summary["skipped"] += 1
            logger.warning("Tenant backup skipped: center=%s reason=%s", center.slug, exc)
        except Exception:
            summary["failed"] += 1
            summary["failed_centers"].append(center.slug)
            logger.exception("Tenant backup failed: center=%s", center.slug)

    try:
        full_backup_path = backup_full_database()
        summary["full_backup_file"] = str(full_backup_path)
        summary["files"].append(str(full_backup_path))
        _run_async(
            send_file_to_telegram(
                full_backup_path,
                caption=(
                    f"Full PostgreSQL backup\n"
                    f"Date: {timezone.localdate().isoformat()}\n"
                    f"Centers: {summary['total']}\n"
                    f"File: {full_backup_path.name}"
                ),
            )
        )
        summary["sent"] += 1
        summary["combined_sent"] = 1
        summary["full_sent"] = 1
        logger.info("Full backup sent: file=%s", full_backup_path)
    except Exception:
        summary["failed"] += 1
        logger.exception("Full backup failed")

    logger.info(
        "Tenant backup job completed: total=%s backed_up=%s sent=%s full_sent=%s skipped=%s failed=%s",
        summary["total"],
        summary["backed_up"],
        summary["sent"],
        summary["full_sent"],
        summary["skipped"],
        summary["failed"],
    )
    return summary


async def _run_scheduled_backup() -> None:
    await asyncio.to_thread(backup_and_send_all_centers)


async def setup_backup_scheduler() -> AsyncIOScheduler:
    global _backup_scheduler

    if _backup_scheduler and _backup_scheduler.running:
        return _backup_scheduler

    scheduler = AsyncIOScheduler(timezone=getattr(settings, "TIME_ZONE", "Asia/Tashkent"))
    scheduler.add_job(
        _run_scheduled_backup,
        CronTrigger(hour=16, minute=0),
        id="tenant-db-backup-daily",
        name="tenant-db-backup-daily",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    scheduler.start()
    _backup_scheduler = scheduler
    logger.info("Tenant backup scheduler started: daily at 16:00 %s", getattr(settings, "TIME_ZONE", "Asia/Tashkent"))
    return scheduler
