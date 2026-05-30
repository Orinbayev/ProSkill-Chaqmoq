"""
core/middleware_rbac.py

Role-based access control middleware for ChaqmoqApp.

Bu middleware:
1. Har bir request'da foydalanuvchi rolini tekshiradi
2. Agar foydalanuvchi ruxsatsiz sahifaga kirmoqchi bo'lsa, o'z dashboardiga yo'naltiradi
3. Login'dan keyin ?next parametrini role-based filter qiladi
"""

import logging
import re
from django.shortcuts import redirect
from django.urls import resolve, Resolver404

logger = logging.getLogger(__name__)

# Slug sifatida hech qachon qabul qilinmaydigan prefikslar (core.middleware dan mos)
_SLUG_EXCLUDED = {
    'admin', 'platform', 'hisob', 'static', 'media', 'api',
    'health', 'logout', 'c', 'emergency-enter-now', 'favicon.ico',
    '__debug__', 'chaqmoq', 'talim', 'billing', 'store', 'click',
    'chat', 'games', 'notifications', 'permissions',
}
_SLUG_PATH_RE = re.compile(r'^/([a-z0-9][a-z0-9\-]{0,62})(/.+)$')

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
                'core:dashboard_student_init_api',
                'core:profile',
                'core:user_view',
                'accounts:profile',
                'core:notifications',
                'core:notifications_mark_read',
                'core:notification_preferences',
                'core:notifications_mark_read_api',
                'core:game_hub',
                'core:game_play',
                'core:game_rating',
                # Guruh Chat
                'core:chat_list',
                'core:group_chat',
                'core:chat_messages_api',
                'core:chat_send_api',
                'core:chat_typing_api',
                'logout',
            },
        },
        'parent': {
            'namespaces': set(),
            'names': {
                'core:home',
                'core:dashboard_parent',
                'core:profile',
                'core:user_view',
                'accounts:profile',
                'core:toggle_child',
                'core:notifications',
                'core:notifications_mark_read',
                'core:notification_preferences',
                'core:notifications_mark_read_api',
                'logout',
            },
        },
        'teacher': {
            'namespaces': {'education', 'chaqmoq', 'store'},
            'names': {
                'core:home',
                'core:dashboard_teacher',
                'core:game_rating',
                'core:user_view',
                'core:user_edit',
                'core:profile',
                'core:notifications',
                'core:notifications_mark_read',
                'core:notification_preferences',
                'core:notifications_mark_read_api',
                # Guruh Chat
                'core:chat_list',
                'core:group_chat',
                'core:chat_messages_api',
                'core:chat_send_api',
                'core:chat_typing_api',
                # Profil sahifasi (ism, familya, parol, avatar)
                'accounts:profile',
                'accounts:user_edit',
                # Telegram ulash
                'connect_telegram',
                # Parol o'zgartirish
                'password_set',
                'forgot_password_init',
                'forgot_password_verify_choice',
                'forgot_password_confirm_choice',
                'forgot_password_verify',
                'forgot_password_set',
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
        if any(path.startswith(prefix) for prefix in SKIP_PREFIXES) or '/api/' in path:
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

        # Slug-prefix URL lar uchun namespace bo'sh bo'ladi (masalan /<slug>/talim/...)
        # Slugni olib tashlab, canonical namespace ni topamiz
        if not namespace:
            m = _SLUG_PATH_RE.match(path)
            if m and m.group(1) not in _SLUG_EXCLUDED:
                try:
                    canonical = resolve(m.group(2))
                    if canonical.namespace:
                        namespace = canonical.namespace
                        url_name = canonical.url_name or url_name
                except Resolver404:
                    pass

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
