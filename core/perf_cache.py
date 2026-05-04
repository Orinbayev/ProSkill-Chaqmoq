"""Performance — markazlashtirilgan cache helperlar.

Asosiy maqsad: og'ir hisobotlar (oylik, salary summary) har request'da qayta
hisoblamasdan, kichik TTL bilan keshlanadi. Multi-tenant: har key markaz
ID'si bilan boshlanadi — markaz bo'yicha izolyatsiya.

Ishlatish:
    from core.perf_cache import perf_cache_get_or_set, invalidate_center

    data = perf_cache_get_or_set(
        f"salary_sum_{center_id}_{year}_{month}",
        lambda: heavy_compute(),
        ttl=900,
    )

    # Markaz bo'yicha hammasini bekor qilish (masalan, attendance saqlanganda):
    invalidate_center(center_id, prefix="salary")
"""
from __future__ import annotations

from typing import Callable, Optional

from django.core.cache import cache


# Default TTL'lar (soniyalarda)
TTL_SHORT = 60          # 1 daqiqa — tez-tez yangilanadigan ro'yxatlar
TTL_MEDIUM = 300        # 5 daqiqa — paginatsiyali ro'yxatlar
TTL_LONG = 900          # 15 daqiqa — oylik hisobotlar
TTL_DAILY = 3600        # 1 soat — yillik agregatlar


def _safe_int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def cache_key_for_center(prefix: str, center_id, *parts) -> str:
    """Markaz va parametrlar bo'yicha cache key.

    Masalan: salary_sum:c=42:y=2026:m=5
    """
    cid = _safe_int(center_id) if center_id is not None else 0
    rest = ":".join(str(p) for p in parts if p is not None)
    return f"{prefix}:c={cid}:{rest}".rstrip(":")


def perf_cache_get_or_set(
    key: str,
    compute: Callable,
    ttl: int = TTL_MEDIUM,
    *,
    skip_cache: bool = False,
):
    """Cache'da bo'lsa qaytaradi, bo'lmasa hisoblaydi va saqlaydi."""
    if skip_cache:
        return compute()
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = compute()
    try:
        cache.set(key, result, timeout=ttl)
    except Exception:
        # Cache backend muammosida silently fall through — function still works.
        pass
    return result


def invalidate_center(center_id, prefix: str = ""):
    """Berilgan markaz uchun barcha cache'larni bekor qilish.

    LocMemCache `delete_pattern` qo'llamaydi, shuning uchun versiya bumping
    strategiyasidan foydalanamiz: har markaz uchun "version" raqami bor;
    cache key'ga qo'shiladi. Versiyani oshirsak — hamma eski key'lar
    avtomatik muddatsiz qoladi (LRU bilan tozalanadi).
    """
    cid = _safe_int(center_id)
    version_key = f"perf_ver:c={cid}:{prefix}" if prefix else f"perf_ver:c={cid}"
    try:
        cache.incr(version_key)
    except ValueError:
        # Boshlangichida key yo'q — yaratamiz
        cache.set(version_key, 1, timeout=None)


def get_center_version(center_id, prefix: str = "") -> int:
    """Markaz uchun joriy cache version raqamini qaytaradi."""
    cid = _safe_int(center_id)
    version_key = f"perf_ver:c={cid}:{prefix}" if prefix else f"perf_ver:c={cid}"
    v = cache.get(version_key)
    if v is None:
        cache.set(version_key, 1, timeout=None)
        return 1
    return _safe_int(v) or 1


def versioned_cache_key(prefix: str, center_id, *parts) -> str:
    """Markaz versiyali cache key — version oshirilsa eski key'lar miss bo'ladi."""
    v = get_center_version(center_id, prefix)
    base = cache_key_for_center(prefix, center_id, *parts)
    return f"{base}:v{v}"
