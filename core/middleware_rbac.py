"""
core/middleware_rbac.py

Role-based access control middleware for ChaqmoqApp.

Bu middleware:
1. Har bir request'da foydalanuvchi rolini tekshiradi
2. Agar foydalanuvchi ruxsatsiz sahifaga kirmoqchi bo'lsa, o'z dashboardiga yo'naltiradi
3. Login'dan keyin ?next parametrini role-based filter qiladi
"""

import logging
from django.shortcuts import redirect
from django.urls import resolve, Resolver404

logger = logging.getLogger(__name__)

# Barcha rollar uchun ochiq yo'llar (tekshirilmaydi)
SKIP_PREFIXES = (
    '/static/',
    '/media/',
    '/admin/',
    '/hisob/login/',
    '/hisob/logout/',
    '/hisob/billing/',
    '/hisob/tolov/',
    '/api/',
    '/click/',
    '/health/',
    '/c/',
    '/emergency-enter-now/',
    '/favicon.ico',
    '/__debug__/',
)


class RoleBasedAccessMiddleware:
    """
    Har bir foydalanuvchi faqat o'z roliga mos sahifalarga kirishi mumkin.
    """

    ROLE_PERMISSIONS = {
        'student': {
            'namespaces': {'store', 'chaqmoq'},
            'names': {
                'core:home',
                'core:dashboard_student',
                'core:user_view',
                'core:notifications_list',
                'core:mark_notification_read',
                'logout',
            },
        },
        'parent': {
            'namespaces': set(),
            'names': {
                'core:home',
                'core:dashboard_parent',
                'core:user_view',
                'core:toggle_child',
                'core:notifications_list',
                'core:mark_notification_read',
                'logout',
            },
        },
        'teacher': {
            'namespaces': {'education', 'chaqmoq', 'store'},
            'names': {
                'core:home',
                'core:dashboard_teacher',
                'core:user_view',
                'core:user_edit',
                'core:notifications_list',
                'core:mark_notification_read',
                'logout',
            },
        },
        'manager': {
            'namespaces': {'core', 'education', 'chaqmoq', 'store', 'billing', 'accounts'},
            'names': {'logout'},
        },
        'director': {
            'namespaces': {'core', 'education', 'chaqmoq', 'store', 'billing', 'marketing', 'accounts'},
            'names': {'logout'},
        },
    }

    DASHBOARD_MAP = {
        'student': 'core:home',
        'parent': 'core:home',
        'teacher': 'core:home',
        'manager': 'core:home',
        'director': 'core:home',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Autentifikatsiya qilinmagan foydalanuvchilarni o'tkazib yuborish
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Tizimli yo'llarni o'tkazib yuborish
        path = request.path
        if any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
            return self.get_response(request)

        # Superuser — hamma narsaga ruxsat
        if request.user.is_superuser:
            return self.get_response(request)

        # Foydalanuvchi rolini olish
        user_role = getattr(request.user, 'role', None)
        if not user_role or user_role not in self.ROLE_PERMISSIONS:
            logger.warning(
                "RoleBasedAccessMiddleware: unknown role '%s' for user %s, skipping RBAC check.",
                user_role, request.user.pk
            )
            return self.get_response(request)

        # URL ni resolve qilish
        try:
            resolved = resolve(path)
        except Resolver404:
            return self.get_response(request)

        namespace = resolved.namespace or ''
        url_name = resolved.url_name or ''
        full_name = f"{namespace}:{url_name}" if namespace else url_name

        # Ruxsat tekshiruvi
        if not self._has_permission(user_role, namespace, full_name):
            logger.info(
                "RBAC: user %s (role=%s) blocked from '%s', redirecting to dashboard.",
                request.user.pk, user_role, full_name
            )
            dashboard = self.DASHBOARD_MAP.get(user_role, 'core:home')
            return redirect(dashboard)

        return self.get_response(request)

    def _has_permission(self, role: str, namespace: str, full_name: str) -> bool:
        perms = self.ROLE_PERMISSIONS.get(role, {})
        allowed_namespaces = perms.get('namespaces', set())
        allowed_names = perms.get('names', set())

        if namespace and namespace in allowed_namespaces:
            return True
        if full_name in allowed_names:
            return True

        return False
