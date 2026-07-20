"""
Shared login brute-force / enumeration throttle helpers.

Used by:
- Web SecureLoginView (accounts.auth_views)
- Mobile API login (core.mobile_api)

Keys are IP + normalized identifier (hashed) so attackers cannot spray one
account from many IPs without tripping the IP-wide budget either.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse

logger = logging.getLogger(__name__)


def _int_setting(name: str, default: int) -> int:
    try:
        return int(getattr(settings, name, default) or default)
    except (TypeError, ValueError):
        return default


def login_max_failed_attempts() -> int:
    return max(3, min(_int_setting("LOGIN_MAX_FAILED_ATTEMPTS", 8), 50))


def login_throttle_window_seconds() -> int:
    return max(60, min(_int_setting("LOGIN_THROTTLE_WINDOW_SECONDS", 15 * 60), 24 * 3600))


def login_ip_max_attempts() -> int:
    """Per-IP failed attempt budget (across all identifiers)."""
    return max(10, min(_int_setting("LOGIN_IP_MAX_FAILED_ATTEMPTS", 40), 500))


def client_ip(request: HttpRequest) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR") or ""
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    return request.META.get("REMOTE_ADDR") or "unknown"


def _hash_part(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def throttle_key_for_identifier(request: HttpRequest, identifier: str) -> str:
    normalized = (identifier or "").strip().lower()
    raw = f"{client_ip(request)}:{normalized}"
    return f"login:throttle:id:{_hash_part(raw)}"


def throttle_key_for_ip(request: HttpRequest) -> str:
    return f"login:throttle:ip:{_hash_part(client_ip(request))}"


def failed_attempt_count(key: str) -> int:
    return int(cache.get(key, 0) or 0)


def is_login_locked(request: HttpRequest, identifier: str) -> bool:
    id_key = throttle_key_for_identifier(request, identifier)
    ip_key = throttle_key_for_ip(request)
    if failed_attempt_count(id_key) >= login_max_failed_attempts():
        return True
    if failed_attempt_count(ip_key) >= login_ip_max_attempts():
        return True
    return False


def register_failed_login(request: HttpRequest, identifier: str) -> int:
    """Increment counters; return the identifier-scoped attempt count."""
    window = login_throttle_window_seconds()
    id_key = throttle_key_for_identifier(request, identifier)
    ip_key = throttle_key_for_ip(request)

    id_attempts = failed_attempt_count(id_key) + 1
    cache.set(id_key, id_attempts, timeout=window)

    ip_attempts = failed_attempt_count(ip_key) + 1
    cache.set(ip_key, ip_attempts, timeout=window)

    logger.warning(
        "login_throttle fail ip=%s id_attempts=%s ip_attempts=%s",
        client_ip(request),
        id_attempts,
        ip_attempts,
    )
    return id_attempts


def clear_failed_login(request: HttpRequest, identifier: str) -> None:
    cache.delete(throttle_key_for_identifier(request, identifier))
    # Do not clear IP-wide budget on success — limits credential stuffing.


def locked_json_response() -> JsonResponse:
    minutes = max(1, login_throttle_window_seconds() // 60)
    return JsonResponse(
        {
            "ok": False,
            "success": False,
            "error": f"Juda ko‘p urinish. {minutes} daqiqadan keyin qayta urinib ko‘ring.",
            "message": f"Juda ko‘p urinish. {minutes} daqiqadan keyin qayta urinib ko‘ring.",
            "code": "rate_limited",
        },
        status=429,
    )


def locked_message() -> str:
    minutes = max(1, login_throttle_window_seconds() // 60)
    return f"Ko‘p urinish bo‘ldi. {minutes} daqiqadan keyin qayta urinib ko‘ring."


def generic_invalid_credentials_message() -> str:
    return "Login yoki parol noto‘g‘ri"


def invalid_credentials_payload(**extra: Any) -> dict:
    msg = generic_invalid_credentials_message()
    payload = {
        "ok": False,
        "success": False,
        "error": msg,
        "message": msg,
        "code": "invalid_credentials",
    }
    payload.update(extra)
    return payload
