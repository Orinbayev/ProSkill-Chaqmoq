"""
core/middleware.py

TenantMiddleware — session-based center resolution (PRIMARY).
Path-based /<slug>/ extraction (SECONDARY fallback).

PERFORMANCE FIXES (v2):
- Center.objects.get() har requestda emas, faqat zarur hollarda (is_deleted/status tekshirish uchun)
- user.center already loaded by Django auth, select_related via auth backend
- _CENTER_CACHE dict bilan per-process memory cache (30s TTL)
- slug URL lookup: ham in-memory cache
"""

import re
import time
import logging
from django.shortcuts import redirect
from django.utils import timezone
from accounts.models import Center
from core.tenant_context import set_current_tenant, clear_current_tenant

logger = logging.getLogger(__name__)

# ── In-process center cache (pk → (center_obj, fetched_at)) ─────────────────
# Render single-process: safe.  Multi-worker: har worker o'z cache ga ega.
# TTL: 30 seconds (subscription/status o'zgarishlarini tez aks ettiradi)
_CENTER_CACHE: dict[int, tuple] = {}
_CENTER_CACHE_TTL = 30  # seconds

# ── Slug cache ───────────────────────────────────────────────────────────────
_SLUG_CACHE: dict[str, tuple] = {}
_SLUG_CACHE_TTL = 120  # seconds


def _get_center_cached(center_id: int):
    """
    Center ni in-process cache orqali oladi.
    Cache miss yoki TTL o'tsa – DB dan yangilaydi.
    """
    now = time.monotonic()
    cached = _CENTER_CACHE.get(center_id)
    if cached:
        center_obj, fetched_at = cached
        if now - fetched_at < _CENTER_CACHE_TTL:
            return center_obj
    try:
        center_obj = Center.objects.get(pk=center_id)
        _CENTER_CACHE[center_id] = (center_obj, now)
        return center_obj
    except Center.DoesNotExist:
        _CENTER_CACHE.pop(center_id, None)
        return None


def _get_center_by_slug_cached(slug: str):
    """Slug bo'yicha Center ni cache orqali oladi."""
    now = time.monotonic()
    cached = _SLUG_CACHE.get(slug)
    if cached:
        center_obj, fetched_at = cached
        if now - fetched_at < _SLUG_CACHE_TTL:
            return center_obj
    center_obj = Center._default_manager.filter(slug=slug, is_deleted=False).first()
    if center_obj:
        _SLUG_CACHE[slug] = (center_obj, now)
    return center_obj


def invalidate_center_cache(center_id: int):
    """
    Center o'zgarganda cache ni tozalash uchun.
    Center.save() signal dan chaqirilishi mumkin.
    """
    _CENTER_CACHE.pop(center_id, None)
    # Slug cache: topish qiyin, shuning uchun butun slug cache ni tozalaymiz
    _SLUG_CACHE.clear()

# Paths that should NEVER be treated as center slugs
EXCLUDED_PREFIXES = {
    'admin', 'platform', 'hisob', 'static', 'media', 'api',
    'health', 'logout', 'c', 'emergency-enter-now', 'favicon.ico',
    '__debug__', 'chaqmoq', 'talim', 'billing', 'store', 'click',
}

NO_REDIRECT_PREFIXES = (
    '/admin/', '/platform/', '/static/', '/media/',
    '/health/', '/logout/', '/emergency-enter-now/',
    '/hisob/', '/c/', '/api/', '/click',
)

_SLUG_RE = re.compile(r'^/([a-z0-9][a-z0-9\-]{0,62})/')


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Reset
        request.center = None
        request.active_center = None
        request.url_center_slug = None

        # Skip static/media
        if (path.startswith('/static/')
                or path.startswith('/media/')
                or path == '/favicon.ico'):
            return self.get_response(request)

        # ── PRIMARY: session/user-based ─────────────────────────
        if request.user.is_authenticated:
            if request.user.is_superuser:
                active_center_id = request.session.get('active_center_id')
                if active_center_id:
                    # ✅ PERF: cache orqali, DB dan emas
                    center = _get_center_cached(int(active_center_id))
                    if center and not center.is_deleted:
                        request.active_center = center
                        request.center = center
            elif hasattr(request.user, 'center') and request.user.center:
                # ✅ PERF: request.user.center allaqachon Django auth orqali yuklangan.
                # Har requestda Center.objects.get() chaqirish — KERAKSIZ query.
                # Faqat is_deleted yoki ARCHIVED tekshirish kerak bo'lganda cache ishlatamiz.
                user_center = request.user.center
                center_pk = user_center.pk

                # Cache dan olish (30s TTL)
                fresh_center = _get_center_cached(center_pk)
                if fresh_center is None:
                    from django.contrib.auth import logout
                    logout(request)
                    return redirect('/')

                if fresh_center.is_deleted or fresh_center.status == 'ARCHIVED':
                    from django.contrib.auth import logout
                    logout(request)
                    return redirect('/')

                request.active_center = fresh_center
                request.center = fresh_center

                # ✅ PERF: Subscription check – faqat 1 soatda bir marta
                last_check = request.session.get('last_sub_check')
                now_ts = timezone.now().timestamp()
                if not last_check or (now_ts - last_check > 3600):
                    try:
                        from billing.services import check_subscription_expiry
                        check_subscription_expiry(fresh_center)
                        request.session['last_sub_check'] = now_ts
                    except Exception as e:
                        logger.error(f'Middleware sub-check error: {e}')

                # Blocked check
                is_blocked = fresh_center.status == 'BLOCKED'
                if not is_blocked:
                    # ✅ PERF: subscription ni cache dan olish (Django cached_property yoki related cache)
                    try:
                        sub = fresh_center.subscriptions.filter(
                            status__in=['ACTIVE', 'GRACE']
                        ).only('status', 'expires_at', 'hard_expires_at').first()
                        if sub and sub.is_blocked():
                            is_blocked = True
                    except Exception:
                        pass  # Blocked check failed - not critical

                if is_blocked:
                    allowed = (
                        path.startswith('/hisob/billing/') or
                        path.startswith('/c/')            or
                        path.startswith('/hisob/tolov/')  or
                        path.startswith('/logout/')       or
                        path.startswith('/admin/logout/') or
                        '/hisob/billing/' in path
                    )
                    if not allowed:
                        role = getattr(request.user, 'role', None)
                        if role not in ('student', 'parent', 'teacher'):
                            return redirect('billing:plans')

        # ── SECONDARY: slug from URL /<slug>/... ────────────────
        m = _SLUG_RE.match(path)
        if m:
            slug = m.group(1)
            if slug not in EXCLUDED_PREFIXES:
                # ✅ PERF: slug cache
                center = _get_center_by_slug_cached(slug)
                if center:
                    request.url_center_slug = slug
                    # Don't override session-based center
                    if request.center is None:
                        request.center = center
                        request.active_center = center

        # ── AUTO-REDIRECT: logged-in user with center → /<slug>/current_path ───
        # Covers /, /stat/students/, /do'kon/leads/ etc.
        is_api = '/api/' in path
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        is_excluded = any(path.startswith(p) for p in NO_REDIRECT_PREFIXES)

        if (request.user.is_authenticated
                and request.center
                and request.center.slug
                and request.url_center_slug is None
                and request.method == 'GET'
                and not is_api
                and not is_ajax
                and not is_excluded):
            slug = request.center.slug
            return redirect(f'/{slug}{path}', permanent=False)

        return self.get_response(request)


class TenantContextMiddleware:
    """
    Безопасно определяет tenant (центр) для каждого запроса и связывает с tenant_context.
    Не меняет бизнес-логику, не требует изменения URL.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        center = None
        # 1. Попытка через request.user.center
        user = getattr(request, 'user', None)
        if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
            center = getattr(user, 'center', None)
        # 2. Попытка через сессию (если уже реализовано)
        if not center:
            center_id = request.session.get('active_center_id')
            if center_id:
                try:
                    center = Center.objects.filter(id=center_id, is_deleted=False).first()
                except Exception as e:
                    logger.warning(f"Ошибка поиска центра по сессии: {e}")
        # 3. (Не трогаем path/subdomain)
        if center:
            set_current_tenant(center)
        else:
            clear_current_tenant()
        request.center = center or None
        try:
            response = self.get_response(request)
        finally:
            clear_current_tenant()
        return response

