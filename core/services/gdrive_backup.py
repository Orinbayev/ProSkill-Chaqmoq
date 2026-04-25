"""
ChaqmoqApp – Google Drive Backup Service
=========================================
Telegram'ga yuborilgan backup fayllarni Google Drive papkasiga ham yuklaydi.
Telegram birinchi va asosiy kanal; Google Drive — ikkinchi mustaqil manzil.

Ikki xil autentifikatsiya qo'llab-quvvatlanadi:

1. OAUTH (shaxsiy Gmail uchun — TAVSIYA ETILADI)
   Env vars:
     GDRIVE_OAUTH_CLIENT_ID
     GDRIVE_OAUTH_CLIENT_SECRET
     GDRIVE_OAUTH_REFRESH_TOKEN
     GDRIVE_FOLDER_ID
   Fayl foydalanuvchining 15GB Drive quotasidan yuklanadi.
   Refresh token'ni olish uchun bir martalik:
       python manage.py gdrive_oauth_setup <client_secrets.json yo'li>

2. SERVICE ACCOUNT (faqat Google Workspace + Shared Drive uchun)
   Env vars:
     GDRIVE_SERVICE_ACCOUNT_JSON
     GDRIVE_FOLDER_ID
   Shaxsiy Gmail'da ishlamaydi (service account quotasiga ega emas).

Ikkalasidan biri sozlanmagan bo'lsa funksiya jimgina o'tkaziladi — Telegram
backup hech qachon shu sababli yiqilmaydi.
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


def _env_or_setting(name: str) -> str:
    return (
        str(getattr(settings, name, "") or "").strip()
        or str(os.environ.get(name, "") or "").strip()
    )


def _get_service_account_json() -> str:
    return _env_or_setting("GDRIVE_SERVICE_ACCOUNT_JSON")


def _get_oauth_refresh_token() -> str:
    return _env_or_setting("GDRIVE_OAUTH_REFRESH_TOKEN")


def _get_oauth_client_id() -> str:
    return _env_or_setting("GDRIVE_OAUTH_CLIENT_ID")


def _get_oauth_client_secret() -> str:
    return _env_or_setting("GDRIVE_OAUTH_CLIENT_SECRET")


def _get_folder_id() -> str:
    return _env_or_setting("GDRIVE_FOLDER_ID")


def _oauth_configured() -> bool:
    return bool(
        _get_oauth_refresh_token()
        and _get_oauth_client_id()
        and _get_oauth_client_secret()
    )


def _service_account_configured() -> bool:
    return bool(_get_service_account_json())


def auth_method() -> str:
    """Qaysi auth rejimi ishlatiladi? 'oauth', 'service_account', yoki 'none'."""
    if _oauth_configured():
        return "oauth"
    if _service_account_configured():
        return "service_account"
    return "none"


def is_gdrive_configured() -> bool:
    """Env vars to'ldirilganmi? Agar yo'q bo'lsa, yuklash bosqichi jimgina o'tkaziladi."""
    return bool(_get_folder_id()) and auth_method() != "none"


def _build_oauth_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=None,
        refresh_token=_get_oauth_refresh_token(),
        client_id=_get_oauth_client_id(),
        client_secret=_get_oauth_client_secret(),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=GDRIVE_SCOPES,
    )
    # Refresh token'ni access token'ga almashtirish (1 soatlik).
    creds.refresh(Request())
    return creds


def _build_service_account_credentials():
    from google.oauth2 import service_account

    creds_raw = _get_service_account_json()
    try:
        creds_info = json.loads(creds_raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"GDRIVE_SERVICE_ACCOUNT_JSON qiymati noto'g'ri JSON: {exc}. "
            "Butun JSON fayl ichini bitta qatorga yopishtiring."
        ) from exc

    return service_account.Credentials.from_service_account_info(
        creds_info, scopes=GDRIVE_SCOPES
    )


def _build_drive_service():
    from googleapiclient.discovery import build

    method = auth_method()
    if method == "oauth":
        credentials = _build_oauth_credentials()
    elif method == "service_account":
        credentials = _build_service_account_credentials()
    else:
        raise ValueError(
            "Google Drive uchun auth sozlanmagan. Ikki variantdan birini tanlang:\n"
            "  OAuth (shaxsiy Gmail): GDRIVE_OAUTH_CLIENT_ID, "
            "GDRIVE_OAUTH_CLIENT_SECRET, GDRIVE_OAUTH_REFRESH_TOKEN\n"
            "  Service Account (Google Workspace + Shared Drive): "
            "GDRIVE_SERVICE_ACCOUNT_JSON"
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
    except Exception as exc:
        import traceback

        error_text = str(exc)
        if "storageQuotaExceeded" in error_text or "Service Accounts do not have storage quota" in error_text:
            logger.error(
                "❌ GDrive yuklash XATOSI: storageQuotaExceeded. "
                "Service Account shaxsiy Drive quotasiga ega emas; Shared Drive yoki OAuth kerak. file=%s",
                file_path,
            )
            return None

        logger.error(
            "❌ GDrive yuklash XATOSI: file=%s\n%s",
            file_path,
            traceback.format_exc(),
        )
        return None
