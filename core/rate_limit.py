"""
core/rate_limit.py

Cache asosida ishlatiladigan yengil rate limiting decorator.
Tashqi kutubxona talab qilmaydi — Django cache backend ishlatiladi.

Ishlatish:
    from core.rate_limit import rate_limit

    @rate_limit(max_calls=10, period=60)          # 10 ta so'rov / 1 daqiqa
    @login_required
    def my_api_view(request):
        ...

    @rate_limit(max_calls=5, period=60, key="ip") # IP bo'yicha
    def public_view(request):
        ...

key parametrlari:
    "user"  — autentifikatsiya qilingan foydalanuvchi bo'yicha (default)
    "ip"    — IP manzil bo'yicha
    "both"  — user + IP birgalikda
"""

from __future__ import annotations

import functools
import hashlib
import logging
from typing import Callable

from django.core.cache import cache
from django.http import JsonResponse, HttpRequest, HttpResponse

logger = logging.getLogger(__name__)

_DEFAULT_MAX_CALLS = 60
_DEFAULT_PERIOD = 60  # seconds


def _get_client_ip(request: HttpRequest) -> str:
    """X-Forwarded-For yoki REMOTE_ADDR orqali IP manzilni oladi."""
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _build_cache_key(request: HttpRequest, prefix: str, key_type: str) -> str:
    """Rate limit uchun cache kalit yaratadi."""
    parts = [prefix]

    if key_type in ("user", "both"):
        if request.user.is_authenticated:
            parts.append(f"u{request.user.pk}")
        else:
            parts.append("anon")

    if key_type in ("ip", "both"):
        ip = _get_client_ip(request)
        ip_hash = hashlib.md5(ip.encode()).hexdigest()[:12]
        parts.append(f"ip{ip_hash}")

    raw = ":".join(parts)
    return f"rl:{hashlib.md5(raw.encode()).hexdigest()}"


def rate_limit(
    max_calls: int = _DEFAULT_MAX_CALLS,
    period: int = _DEFAULT_PERIOD,
    key: str = "user",
    block: bool = True,
) -> Callable:
    """
    Rate limiting decorator.

    Parametrlar:
        max_calls  - Ruxsat berilgan maksimal so'rovlar soni
        period     - Vaqt oralig'i (soniyalarda)
        key        - Kalit turi: "user", "ip", "both"
        block      - True: 429 qaytaradi; False: faqat loglaydi (soft mode)
    """
    def decorator(view_func: Callable) -> Callable:
        prefix = f"rl:{view_func.__module__}.{view_func.__name__}"

        @functools.wraps(view_func)
        def wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            # Superuser va stafflar uchun cheklov yo'q
            if getattr(request, "user", None) and request.user.is_authenticated:
                if request.user.is_superuser or request.user.is_staff:
                    return view_func(request, *args, **kwargs)

            cache_key = _build_cache_key(request, prefix, key)
            current = cache.get(cache_key, 0)

            if current >= max_calls:
                logger.warning(
                    "Rate limit exceeded: view=%s key_type=%s user=%s ip=%s",
                    f"{view_func.__module__}.{view_func.__name__}",
                    key,
                    getattr(request.user, "pk", "anon") if hasattr(request, "user") else "anon",
                    _get_client_ip(request),
                )
                if block:
                    is_ajax = (
                        request.headers.get("X-Requested-With") == "XMLHttpRequest"
                        or "application/json" in request.headers.get("Accept", "")
                    )
                    if is_ajax:
                        return JsonResponse(
                            {"ok": False, "error": "Juda ko'p so'rov. Biroz kuting."},
                            status=429,
                        )
                    from django.shortcuts import render
                    return render(request, "429.html", status=429)

            # Kalit mavjud bo'lmasa yangi davr boshlaydi
            if current == 0:
                cache.set(cache_key, 1, period)
            else:
                cache.incr(cache_key)

            return view_func(request, *args, **kwargs)

        return wrapped
    return decorator


def rate_limit_api(max_calls: int = 30, period: int = 60) -> Callable:
    """API endpointlar uchun shortcut (IP + user, JSON javob)."""
    return rate_limit(max_calls=max_calls, period=period, key="both", block=True)


def rate_limit_public(max_calls: int = 20, period: int = 60) -> Callable:
    """Ommaviy (login talab qilmaydigan) sahifalar uchun shortcut (IP bo'yicha)."""
    return rate_limit(max_calls=max_calls, period=period, key="ip", block=True)
