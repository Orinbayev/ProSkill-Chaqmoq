"""
core/middleware.py

TenantMiddleware — session-based center resolution (PRIMARY).
Path-based /c/<slug>/ extraction (SECONDARY fallback for unauthenticated/center-less requests).
"""

import re
import logging
from django.shortcuts import redirect
from django.utils import timezone
from accounts.models import Center

logger = logging.getLogger(__name__)

# Matches /c/<center_slug>/ prefix
_CENTER_SLUG_RE = re.compile(r'^/c/([a-z0-9][a-z0-9\-]{0,62})/')


class TenantMiddleware:
    """
    Resolves request.center using TWO strategies:

    PRIMARY (always runs first):
        - Authenticated user → user.center (standard user)
        - Superuser          → session['active_center_id']

    SECONDARY fallback (only when request.center is still None):
        - URL path starts with /c/<center_slug>/ → lookup Center by slug
        - Attaches center to request WITHOUT overriding primary resolution
        - Also stores slug on request.url_center_slug for login views
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # ── Reset all tenant attrs ───────────────────────────────
        request.center = None
        request.active_center = None
        request.url_center_slug = None   # slug extracted from /c/<slug>/

        # ── Skip static/media/favicon ────────────────────────────
        if (path.startswith('/static/')
                or path.startswith('/media/')
                or path == '/favicon.ico'):
            return self.get_response(request)

        # ═══════════════════════════════════════════════════════════
        # PRIMARY: session/user based resolution
        # ═══════════════════════════════════════════════════════════
        if request.user.is_authenticated:

            # A) Superuser: session override
            if request.user.is_superuser:
                active_center_id = request.session.get('active_center_id')
                if active_center_id:
                    center = Center.objects.filter(
                        id=active_center_id, is_deleted=False
                    ).first()
                    if center:
                        request.active_center = center
                        request.center = center

            # B) Standard user: always use assigned center
            elif hasattr(request.user, 'center') and request.user.center:
                try:
                    fresh_center = Center.objects.get(pk=request.user.center.pk)
                except Center.DoesNotExist:
                    from django.contrib.auth import logout
                    logout(request)
                    return redirect('/')

                if fresh_center.is_deleted:
                    from django.contrib.auth import logout
                    logout(request)
                    return redirect('/')

                if fresh_center.status == 'ARCHIVED':
                    from django.contrib.auth import logout
                    logout(request)
                    return redirect('/')

                request.active_center = fresh_center
                request.center = fresh_center

                # Subscription expiry check — once per hour per session
                last_check = request.session.get('last_sub_check')
                now_ts = timezone.now().timestamp()
                if not last_check or (now_ts - last_check > 3600):
                    try:
                        from billing.services import check_subscription_expiry
                        check_subscription_expiry(fresh_center)
                        request.session['last_sub_check'] = now_ts
                    except Exception as e:
                        logger.error(f'Middleware sub-check error: {e}')

                # Blocked center: redirect admin/manager to billing
                is_blocked = fresh_center.status == 'BLOCKED'
                if not is_blocked:
                    sub = getattr(fresh_center, 'subscription', None)
                    if sub and sub.is_blocked():
                        is_blocked = True

                if is_blocked:
                    allowed = (
                        path.startswith('/hisob/billing/') or
                        path.startswith('/c/')            or   # ← allow /c/<slug>/billing/
                        path.startswith('/hisob/tolov/')  or
                        path.startswith('/logout/')       or
                        path.startswith('/admin/logout/')
                    )
                    if not allowed:
                        role = getattr(request.user, 'role', None)
                        if role not in ('student', 'parent', 'teacher'):
                            return redirect('billing:plans')

            # C) Orphan user (no center) — allow, views handle access

        # ═══════════════════════════════════════════════════════════
        # SECONDARY: path-based slug fallback  /c/<slug>/...
        # Only runs when PRIMARY did NOT set request.center.
        # ═══════════════════════════════════════════════════════════
        m = _CENTER_SLUG_RE.match(path)
        if m:
            request.url_center_slug = m.group(1)          # always store the slug
            if request.center is None:                     # don't override PRIMARY
                center = Center.objects.filter(
                    slug=request.url_center_slug, is_deleted=False
                ).first()
                if center:
                    request.center = center
                    request.active_center = center
                    logger.debug(
                        f'[TenantMiddleware] center resolved from URL slug: '
                        f'{request.url_center_slug}'
                    )

        return self.get_response(request)
