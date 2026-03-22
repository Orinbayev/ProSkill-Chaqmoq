"""
core/middleware.py

TenantMiddleware — session-based center resolution (PRIMARY).
Path-based /<slug>/ extraction (SECONDARY fallback).
"""

import re
import logging
from django.shortcuts import redirect
from django.utils import timezone
from accounts.models import Center
from core.tenant_context import set_current_tenant, clear_current_tenant

logger = logging.getLogger(__name__)

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
                    center = Center.objects.filter(
                        id=active_center_id, is_deleted=False
                    ).first()
                    if center:
                        request.active_center = center
                        request.center = center
            elif hasattr(request.user, 'center') and request.user.center:
                try:
                    fresh_center = Center.objects.get(pk=request.user.center.pk)
                except Center.DoesNotExist:
                    from django.contrib.auth import logout
                    logout(request)
                    return redirect('/')

                if fresh_center.is_deleted or fresh_center.status == 'ARCHIVED':
                    from django.contrib.auth import logout
                    logout(request)
                    return redirect('/')

                request.active_center = fresh_center
                request.center = fresh_center

                # Subscription check
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
                    sub = getattr(fresh_center, 'subscription', None)
                    if sub and sub.is_blocked():
                        is_blocked = True

                if is_blocked:
                    allowed = (
                        path.startswith('/hisob/billing/') or
                        path.startswith('/c/')            or
                        path.startswith('/hisob/tolov/')  or
                        path.startswith('/logout/')       or
                        path.startswith('/admin/logout/') or
                        # Allow slug-prefixed billing
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
                center = Center._default_manager.filter(
                    slug=slug, is_deleted=False
                ).first()
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

