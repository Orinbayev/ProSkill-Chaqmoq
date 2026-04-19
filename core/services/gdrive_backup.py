"""
ChaqmoqApp – Google Drive Backup Service
=========================================
Telegram'ga yuborilgan backup fayllarni Google Drive papkasiga ham yuklaydi.
Telegram birinchi va asosiy kanal; Google Drive — ikkinchi mustaqil manzil.

Ishga tushirish:
  1. Google Cloud loyiha yarating, Google Drive API ni yoqing.
  2. Service Account yarating, JSON key yuklab oling.
  3. Drive'da papka yarating va service account emailiga "Editor" ruxsat bering.
  4. Render env vars:
       GDRIVE_SERVICE_ACCOUNT_JSON = JSON fayl butun ichi (bitta qatorga)
       GDRIVE_FOLDER_ID            = papka ID (Drive URL'dagi /folders/<ID> qismi)

Funksiya sozlanmagan bo'lsa jimgina `False` qaytaradi — mavjud Telegram backup
hech qachon shu sababli yiqilmaydi.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

GDRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _get_service_account_json() -> str:
    return (
        str(getattr(settings, "GDRIVE_SERVICE_ACCOUNT_JSON", "") or "").strip()
        or str(os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON", "") or "").strip()
    )


def _get_folder_id() -> str:
    return (
        str(getattr(settings, "GDRIVE_FOLDER_ID", "") or "").strip()
        or str(os.environ.get("GDRIVE_FOLDER_ID", "") or "").strip()
    )


def is_gdrive_configured() -> bool:
    """Env vars to'ldirilganmi? Agar yo'q bo'lsa, yuklash bosqichi jimgina o'tkaziladi."""
    return bool(_get_service_account_json() and _get_folder_id())


def _build_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_raw = _get_service_account_json()
    if not creds_raw:
        raise ValueError(
            "GDRIVE_SERVICE_ACCOUNT_JSON env var o'rnatilmagan. "
            "Render Dashboard → Environment Variables ga qo'shing."
        )

    try:
        creds_info = json.loads(creds_raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"GDRIVE_SERVICE_ACCOUNT_JSON qiymati noto'g'ri JSON: {exc}. "
            "Butun JSON fayl ichini bitta qatorga yopishtiring."
        ) from exc

    credentials = service_account.Credentials.from_service_account_info(
        creds_info, scopes=GDRIVE_SCOPES
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _escape_drive_query(value: str) -> str:
    """Drive Query tili uchun qo'shtirnoqli satrlarni qochirish."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _find_or_create_folder(service, name: str, parent_id: str) -> str:
    safe_name = _escape_drive_query(name)
    query = (
        f"name = '{safe_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents "
        f"and trashed = false"
    )
    result = (
        service.files()
        .list(
            q=query,
            fields="files(id, name)",
            pageSize=1,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = result.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = (
        service.files()
        .create(body=metadata, fields="id", supportsAllDrives=True)
        .execute()
    )
    folder_id = folder["id"]
    logger.info("GDrive yangi papka: name=%s parent=%s id=%s", name, parent_id, folder_id)
    return folder_id


def upload_file_to_gdrive(
    file_path: str | Path,
    subfolder_path: list[str] | None = None,
) -> dict[str, Any]:
    """
    Faylni Google Drive'ga yuklaydi.

    subfolder_path — masalan ["2026-04", "2026-04-19"] — root papka ichida
    avtomatik papka yaratib shu yerga qo'yadi.

    Raises:
        ValueError           – env vars yo'q bo'lsa
        FileNotFoundError    – fayl topilmasa
        Google API Exception – autentifikatsiya yoki tarmoq xatosi
    """
    from googleapiclient.http import MediaFileUpload

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"GDrive upload: fayl topilmadi: {path}")

    root_folder_id = _get_folder_id()
    if not root_folder_id:
        raise ValueError(
            "GDRIVE_FOLDER_ID env var o'rnatilmagan. "
            "Drive URL'dagi /folders/<ID> qismini nusxa oling."
        )

    service = _build_drive_service()

    parent_id = root_folder_id
    for folder_name in subfolder_path or []:
        parent_id = _find_or_create_folder(service, folder_name, parent_id)

    metadata = {"name": path.name, "parents": [parent_id]}
    media = MediaFileUpload(str(path), resumable=True)

    logger.info(
        "GDrive yuklash boshlandi: file=%s size=%d bytes parent=%s",
        path.name,
        path.stat().st_size,
        parent_id,
    )

    result = (
        service.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id, name, webViewLink, size",
            supportsAllDrives=True,
        )
        .execute()
    )

    logger.info(
        "✅ GDrive yuklandi: file=%s id=%s link=%s",
        result.get("name"),
        result.get("id"),
        result.get("webViewLink"),
    )
    return result


def safe_upload_file_to_gdrive(
    file_path: str | Path,
    subfolder_path: list[str] | None = None,
) -> dict[str, Any] | None:
    """
    upload_file_to_gdrive'ning xavfsiz varianti: sozlanmagan bo'lsa None qaytaradi,
    xato bo'lsa logga yozadi va None qaytaradi (Telegram backup flow uzilmaydi).
    """
    if not is_gdrive_configured():
        logger.info("GDrive sozlanmagan — yuklash o'tkazib yuborildi: file=%s", file_path)
        return None
    try:
        return upload_file_to_gdrive(file_path, subfolder_path)
    except Exception:
        import traceback

        logger.error(
            "❌ GDrive yuklash XATOSI: file=%s\n%s",
            file_path,
            traceback.format_exc(),
        )
        return None
