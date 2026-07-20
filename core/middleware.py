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
from urllib.parse import urlparse

from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone

from accounts.models import Center
from core.tenant_context import set_current_tenant, clear_current_tenant

logger = logging.getLogger(__name__)

# ── In-process caches (per worker). TTLs come from settings (phase 8). ─────
_CENTER_CACHE: dict[int, tuple] = {}
_SLUG_CACHE: dict[str, tuple] = {}
_SUB_BLOCK_CACHE: dict[int, tuple] = {}


def _setting_int(name: str, default: int) -> int:
    try:
        from django.conf import settings as dj_settings
        return max(1, int(getattr(dj_settings, name, default) or default))
    except Exception:
        return default


def _center_cache_ttl() -> int:
    return _setting_int("CENTER_CACHE_TTL", 15)


def _slug_cache_ttl() -> int:
    return _setting_int("CENTER_SLUG_CACHE_TTL", 60)


def _sub_block_cache_ttl() -> int:
    return _setting_int("SUBSCRIPTION_BLOCK_CACHE_TTL", 15)


def _sub_check_interval() -> int:
    return _setting_int("SUBSCRIPTION_CHECK_INTERVAL_SECONDS", 120)


def _root_center(center):
    """Filial subscription root markazdan olinadi."""
    if center is None:
        return None
    try:
        if getattr(center, "parent_center_id", None) and hasattr(center, "get_root_center"):
            return center.get_root_center()
    except Exception:
        pass
    return center


def _get_center_cached(center_id: int):
    """
    Center ni in-process cache orqali oladi.
    Cache miss yoki TTL o'tsa – DB dan yangilaydi.
    """
    now = time.monotonic()
    ttl = _center_cache_ttl()
    cached = _CENTER_CACHE.get(center_id)
    if cached:
        center_obj, fetched_at = cached
        if now - fetched_at < ttl:
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
    ttl = _slug_cache_ttl()
    cached = _SLUG_CACHE.get(slug)
    if cached:
        center_obj, fetched_at = cached
        if now - fetched_at < ttl:
            return center_obj
    center_obj = Center._default_manager.filter(slug=slug, is_deleted=False).first()
    if center_obj:
        _SLUG_CACHE[slug] = (center_obj, now)
    return center_obj


def invalidate_center_cache(center_id: int):
    """
    Center yoki uning subscriptioni o'zgarganda in-process cache ni tozalaydi.
    Filiallar root id bo'yicha ham chaqirilishi mumkin.
    """
    if center_id is None:
        return
    try:
        center_id = int(center_id)
    except (TypeError, ValueError):
        return
    _CENTER_CACHE.pop(center_id, None)
    _SUB_BLOCK_CACHE.pop(center_id, None)
    # Slug cache: reverse index yo'q — tozalaymiz (kichik dict).
    _SLUG_CACHE.clear()


def invalidate_center_tree_cache(center) -> None:
    """Root + filiallar cache ini tozalash (billing eventlardan)."""
    if center is None:
        return
    root = _root_center(center)
    ids = {getattr(center, "pk", None), getattr(root, "pk", None)}
    try:
        if root is not None and hasattr(root, "child_branches"):
            ids.update(root.child_branches.values_list("pk", flat=True))
    except Exception:
        pass
    for cid in ids:
        if cid:
            invalidate_center_cache(cid)


def _is_center_blocked(center) -> bool:
    """
    Subscription block holatini in-process cache bilan tekshiradi.
    Filiallar root markaz subscriptionidan foydalanadi.
    """
    if center is None:
        return False
    root = _root_center(center)
    if center.status == "BLOCKED" or (root is not None and root.status == "BLOCKED"):
        return True

    cache_key = getattr(root, "pk", None) or center.pk
    now = time.monotonic()
    ttl = _sub_block_cache_ttl()
    cached = _SUB_BLOCK_CACHE.get(cache_key)
    if cached:
        is_blocked, fetched_at = cached
        if now - fetched_at < ttl:
            return is_blocked
    try:
        target = root or center
        sub = target.subscriptions.filter(
            status="ACTIVE"
        ).only("status", "expires_at", "manual_block").first()
        is_blocked = bool(sub and sub.is_blocked())
        # No ACTIVE subscription and center is not on free/system path:
        # treat hard-expired missing sub as blocked only when status is BLOCKED
        # (handled above) or sub explicitly blocked. Missing sub → not blocked here
        # (feature gates handle plan limits separately).
    except Exception:
        is_blocked = False
    _SUB_BLOCK_CACHE[cache_key] = (is_blocked, now)
    return is_blocked


def _bind_authenticated_center(request, center, path: str, *, clear_invalid_session: bool = False):
    """
    request.center/request.active_center ni o'rnatadi va subscription/block holatini tekshiradi.
    Director session orqali tanlagan center yaroqsiz bo'lsa session tozalanib fallback qilinadi.
    """
    if center is None:
        return None

    fresh_center = _get_center_cached(center.pk)
    if fresh_center is None:
        if clear_invalid_session:
            request.session.pop('active_center_id', None)
            return None
        from django.contrib.auth import logout
        logout(request)
        return redirect('/')

    if fresh_center.is_deleted or fresh_center.status == 'ARCHIVED':
        if clear_invalid_session:
            request.session.pop('active_center_id', None)
            return None
        from django.contrib.auth import logout
        logout(request)
        return redirect('/')

    request.active_center = fresh_center
    request.center = fresh_center

    # Subscription expiry reconcile — per-center, short interval (default 2 min).
    root = _root_center(fresh_center)
    root_id = getattr(root, "pk", None) or fresh_center.pk
    session_key = f"last_sub_check_{root_id}"
    last_check = request.session.get(session_key) or request.session.get("last_sub_check")
    now_ts = timezone.now().timestamp()
    if not last_check or (now_ts - float(last_check) > _sub_check_interval()):
        try:
            from billing.services import check_subscription_expiry
            check_subscription_expiry(root or fresh_center)
            # Expiry may flip status — drop block cache for this tree.
            invalidate_center_tree_cache(fresh_center)
            request.session[session_key] = now_ts
            request.session["last_sub_check"] = now_ts  # backward compatible
        except Exception as e:
            logger.error(f'Middleware sub-check error: {e}')

    is_blocked = _is_center_blocked(fresh_center)

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

    return None


def _get_director_session_center(request):
    active_center_id = request.session.get('active_center_id')
    if not active_center_id:
        return None

    try:
        center_id = int(active_center_id)
    except (TypeError, ValueError):
        request.session.pop('active_center_id', None)
        return None

    from accounts.models import DirectorCenterAccess

    user_center = getattr(request.user, 'center', None)
    is_own = bool(user_center and user_center.id == center_id)
    has_access = is_own or DirectorCenterAccess.objects.filter(
        director=request.user,
        center_id=center_id,
        is_active=True,
    ).exists()
    if not has_access:
        request.session.pop('active_center_id', None)
        return None

    center = _get_center_cached(center_id)
    if center and not center.is_deleted and center.status != 'ARCHIVED':
        return center

    request.session.pop('active_center_id', None)
    return None

# Paths that should NEVER be treated as center slugs
EXCLUDED_PREFIXES = {
    'admin', 'platform', 'hisob', 'static', 'media', 'api',
    'health', 'logout', 'c', 'emergency-enter-now', 'favicon.ico',
    '__debug__', 'chaqmoq', 'talim', 'billing', 'store', 'click',
    'chat', 'games', 'notifications', 'permissions',
}

NO_REDIRECT_PREFIXES = (
    '/admin/', '/platform/', '/static/', '/media/',
    '/health/', '/logout/', '/emergency-enter-now/',
    '/hisob/', '/c/', '/api/', '/click',
    '/chat/', '/games/', '/notifications/', '/permissions/',
)

_SLUG_RE = re.compile(r'^/([a-z0-9][a-z0-9\-]{0,62})/')


def _is_mobile_api_path(path: str) -> bool:
    return '/api/mobile/' in path


def _allowed_mobile_origin(origin: str | None) -> str | None:
    if not origin:
        return None
    try:
        parsed = urlparse(origin)
    except ValueError:
        return None
    if parsed.scheme not in {'http', 'https'}:
        return None
    if parsed.hostname not in {'127.0.0.1', 'localhost'}:
        return None
    return origin


def _append_vary_header(response, value: str) -> None:
    current = response.get('Vary')
    if not current:
        response['Vary'] = value
        return
    parts = [item.strip() for item in current.split(',') if item.strip()]
    if value not in parts:
        parts.append(value)
        response['Vary'] = ', '.join(parts)


class MobileApiCorsMiddleware:
    """
    Flutter web preview uchun local dev CORS/preflight support.
    Native mobile build uchun bu kerak emas, lekin browser preview
    paytida /api/mobile/* endpointlari OPTIONS so'rovini o'tkazishi kerak.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = _allowed_mobile_origin(request.headers.get('Origin'))
        if _is_mobile_api_path(request.path) and origin and request.method == 'OPTIONS':
            response = HttpResponse(status=200)
            self._apply_headers(response, origin)
            return response

        response = self.get_response(request)

        if _is_mobile_api_path(request.path) and origin:
            self._apply_headers(response, origin)
        return response

    def _apply_headers(self, response, origin: str) -> None:
        response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Allow-Credentials'] = 'true'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken, X-Requested-With, X-Center-Slug'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        _append_vary_header(response, 'Origin')


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings as _settings
        _mw_debug = getattr(_settings, 'PERF_MIDDLEWARE_DEBUG', False)
        _t0 = time.perf_counter() if _mw_debug else 0

        path = request.path

        # Reset
        request.center = None
        request.active_center = None
        request.url_center_slug = None

        # Skip static/media/health — Render health check eng tez yo'l
        if (path.startswith('/static/')
                or path.startswith('/media/')
                or path == '/favicon.ico'
                or path.rstrip('/') == '/health'):
            return self.get_response(request)

        # Pre-compute redirect flags once (used in fast-path and fallback)
        is_api = '/api/' in path
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        is_excluded = any(path.startswith(p) for p in NO_REDIRECT_PREFIXES)

        # ── FAST-PATH REDIRECT ──────────────────────────────────
        # For authenticated non-superusers doing GET requests that lack a slug
        # prefix: issue the redirect BEFORE any subscription DB query.
        # Session is already loaded by AuthenticationMiddleware, so
        # request.session access here is free (no extra DB hit).
        if (request.user.is_authenticated
                and not request.user.is_superuser
                and request.method == 'GET'
                and not is_api
                and not is_ajax
                and not is_excluded):

            _m_early = _SLUG_RE.match(path)
            _early_slug = _m_early.group(1) if _m_early else None
            _already_prefixed = bool(_early_slug and _early_slug not in EXCLUDED_PREFIXES)

            if not _already_prefixed:
                _user_center = getattr(request.user, 'center', None)
                if _user_center:
                    _redirect_slug = None
                    if getattr(request.user, 'role', None) == 'director':
                        _switched_id = request.session.get('active_center_id')
                        if _switched_id:
                            try:
                                _switched = _get_center_cached(int(_switched_id))
                                if _switched and not _switched.is_deleted and _switched.slug:
                                    _redirect_slug = _switched.slug
                            except (TypeError, ValueError):
                                pass
                    if not _redirect_slug:
                        _redirect_slug = _user_center.slug
                    if _redirect_slug:
                        if _mw_debug:
                            _elapsed = (time.perf_counter() - _t0) * 1000
                            logger.info(
                                '[MW-DEBUG] fast-path redirect to /%s%s in %.1fms',
                                _redirect_slug, path, _elapsed,
                            )
                        return redirect(f'/{_redirect_slug}{path}', permanent=False)

        if _mw_debug:
            logger.info('[MW-DEBUG] no fast-path redirect for %s (api=%s excluded=%s)', path, is_api, is_excluded)

        # ── PRIMARY: session/user-based ─────────────────────────
        if request.user.is_authenticated:
            if request.user.is_superuser:
                active_center_id = request.session.get('active_center_id')
                if active_center_id:
                    try:
                        center = _get_center_cached(int(active_center_id))
                    except (TypeError, ValueError):
                        center = None
                    if center and not center.is_deleted:
                        request.active_center = center
                        request.center = center
                    else:
                        request.session.pop('active_center_id', None)
            elif hasattr(request.user, 'center') and request.user.center:
                role = getattr(request.user, 'role', None)
                if _mw_debug:
                    _t_bind = time.perf_counter()
                if role == 'director':
                    switched_center = _get_director_session_center(request)
                    if switched_center is not None:
                        response = _bind_authenticated_center(
                            request,
                            switched_center,
                            path,
                            clear_invalid_session=True,
                        )
                        if response:
                            return response

                if request.center is None:
                    response = _bind_authenticated_center(request, request.user.center, path)
                    if response:
                        return response
                if _mw_debug:
                    logger.info(
                        '[MW-DEBUG] _bind_authenticated_center took %.1fms',
                        (time.perf_counter() - _t_bind) * 1000,
                    )

        # ── SECONDARY: slug from URL /<slug>/... ────────────────
        m = _SLUG_RE.match(path)
        if m:
            slug = m.group(1)
            if slug not in EXCLUDED_PREFIXES:
                if _mw_debug:
                    _t_slug = time.perf_counter()
                center = _get_center_by_slug_cached(slug)
                if center:
                    request.url_center_slug = slug
                    if request.center is None:
                        request.center = center
                        request.active_center = center
                if _mw_debug:
                    logger.info(
                        '[MW-DEBUG] slug lookup "%s" → %s in %.1fms',
                        slug, center, (time.perf_counter() - _t_slug) * 1000,
                    )

        # ── AUTO-REDIRECT: fallback for superadmin / edge cases ──
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

        if _mw_debug:
            logger.info('[MW-DEBUG] total middleware: %.1fms', (time.perf_counter() - _t0) * 1000)
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
