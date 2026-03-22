from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.utils import timezone

from accounts.models import Center

logger = logging.getLogger(__name__)

_backup_scheduler: AsyncIOScheduler | None = None


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


def _get_center_db_credentials(center: Center) -> dict[str, str]:
    credentials = {
        "name": str(getattr(center, "db_name", "") or "").strip(),
        "user": str(getattr(center, "db_user", "") or "").strip(),
        "password": str(getattr(center, "db_password", "") or "").strip(),
        "host": str(getattr(center, "db_host", "") or "localhost").strip() or "localhost",
        "port": str(getattr(center, "db_port", "") or "5432").strip() or "5432",
    }

    missing = [key for key in ("name", "user") if not credentials[key]]
    if missing:
        raise ValueError(f"missing DB credentials: {', '.join(missing)}")

    return credentials


def _build_backup_path(center: Center) -> Path:
    backup_date = timezone.localdate().isoformat()
    return _get_backup_root() / f"{center.slug}_{backup_date}.sql"


def _build_combined_archive_path() -> Path:
    backup_date = timezone.localdate().isoformat()
    return _get_backup_root() / f"all_centers_{backup_date}.zip"


def _build_pg_dump_command(center: Center, backup_path: Path) -> list[str]:
    credentials = _get_center_db_credentials(center)
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


def backup_center_database(center: Center) -> Path:
    if shutil.which("pg_dump") is None:
        raise RuntimeError("pg_dump is not available on this system")

    backup_path = _build_backup_path(center)
    credentials = _get_center_db_credentials(center)

    env = os.environ.copy()
    env["PGCONNECT_TIMEOUT"] = env.get("PGCONNECT_TIMEOUT", "15")
    if credentials["password"]:
        env["PGPASSWORD"] = credentials["password"]

    result = subprocess.run(
        _build_pg_dump_command(center, backup_path),
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

    logger.info("Tenant backup created: center=%s file=%s", center.slug, backup_path)
    return backup_path


def create_combined_archive(file_paths: list[str | Path]) -> Path:
    if not file_paths:
        raise ValueError("No backup files found for combined archive")

    archive_path = _build_combined_archive_path()
    with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in file_paths:
            path = Path(file_path)
            if path.exists():
                zf.write(path, arcname=path.name)

    logger.info("Combined backup archive created: file=%s", archive_path)
    return archive_path


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
        "skipped": 0,
        "failed": 0,
        "files": [],
        "combined_archive": None,
        "failed_centers": [],
    }

    centers = list(
        Center.objects.filter(status=Center.STATUS_ACTIVE)
        .only("id", "slug", "name", "status", "db_name", "db_user", "db_password", "db_host", "db_port")
        .order_by("id")
    )
    summary["total"] = len(centers)

    if not centers:
        logger.info("Tenant backup skipped: no active centers found")
        return summary

    for center in centers:
        try:
            backup_path = backup_center_database(center)
            summary["backed_up"] += 1
            summary["files"].append(str(backup_path))
            _run_async(
                send_file_to_telegram(
                    backup_path,
                    caption=(
                        f"Center backup\n"
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

    if summary["files"]:
        try:
            combined_archive = create_combined_archive(summary["files"])
            summary["combined_archive"] = str(combined_archive)
            _run_async(
                send_file_to_telegram(
                    combined_archive,
                    caption=(
                        f"Combined backup\n"
                        f"Date: {timezone.localdate().isoformat()}\n"
                        f"Centers: {summary['backed_up']}\n"
                        f"File: {combined_archive.name}"
                    ),
                )
            )
            summary["sent"] += 1
            summary["combined_sent"] = 1
            logger.info("Combined backup sent: file=%s", combined_archive)
        except Exception:
            summary["failed"] += 1
            logger.exception("Combined backup send failed")

    logger.info(
        "Tenant backup job completed: total=%s backed_up=%s sent=%s combined_sent=%s skipped=%s failed=%s",
        summary["total"],
        summary["backed_up"],
        summary["sent"],
        summary["combined_sent"],
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
