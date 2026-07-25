"""
core/middleware_rbac.py

Role-based access control middleware for ChaqmoqApp.

Bu middleware:
1. Har bir request'da foydalanuvchi rolini tekshiradi
2. Agar foydalanuvchi ruxsatsiz sahifaga kirmoqchi bo'lsa, o'z dashboardiga yo'naltiradi
   (API/JSON so'rovlarda 403 JSON qaytaradi)
3. Faqat tashqi auth ishlatadigan API prefikslarini (mobile token, Click, bot secret) o'tkazadi —
   blanket `/api/` skip YO'Q (IDOR/RBAC bypass oldini olish)
"""

import logging
import re

from django.http import JsonResponse
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

# Umumiy tizim yo'llari — RBAC tekshirilmaydi
SKIP_PREFIXES = (
    '/static/',
    '/media/',
    '/admin/',
    '/logout/',
    '/hisob/login/',   # login + bot internal APIs (X-API-SECRET)
    '/hisob/logout/',
    '/hisob/billing/',
    '/hisob/tolov/',
    '/click/',         # Click Shop API (imzo tekshiruvi viewda)
    '/health/',
    '/c/',
    '/emergency-enter-now/',
    '/favicon.ico',
    '/__debug__/',
)

# Tashqi/token asosidagi API lar — o'z auth qatlamiga ega (sessiya RBAC emas)
# Eslatma: blanket `/api/` BU YERDA YO'Q — web sessiya API lar RBAC dan o'tadi.
EXTERNAL_API_PREFIXES = (
    '/api/mobile/',    # Flutter Bearer token
    '/api/click/',     # Click prepare/complete/webhook
    '/api/schema/',    # OpenAPI schema
    '/api/docs/',      # Swagger UI
    '/api/redoc/',     # ReDoc
    '/api/v1/',        # Bot telegram link va boshqa secret API
)


def _strip_slug_prefix(path: str) -> str:
    """`/center-slug/rest` → `/rest` (faqat haqiqiy center slug bo'lsa)."""
    m = _SLUG_PATH_RE.match(path)
    if not m:
        return path
    slug = m.group(1)
    if slug in _SLUG_EXCLUDED:
        return path
    return m.group(2)


def _is_skipped_path(path: str) -> bool:
    """Tizim yoki tashqi-auth API yo'li ekanini aniqlaydi."""
    if any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
        return True

    # Slug-prefixed: /proskill/hisob/login/ ...
    rest = _strip_slug_prefix(path)
    if rest != path and any(rest.startswith(prefix) for prefix in SKIP_PREFIXES):
        return True

    # External APIs (root yoki slug ostida)
    candidates = (path, rest) if rest != path else (path,)
    for candidate in candidates:
        if any(candidate.startswith(prefix) for prefix in EXTERNAL_API_PREFIXES):
            return True
    return False


def _wants_json_response(request, path: str) -> bool:
    """API/AJAX so'rovlar uchun 403 JSON qaytarish kerakmi."""
    if '/api/' in path:
        return True
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    accept = (request.headers.get('Accept') or '').lower()
    if 'application/json' in accept and 'text/html' not in accept:
        return True
    return False


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
                'core:notification_read_one',
                'core:notification_preferences',
                'core:notifications_mark_read_api',
                'core:game_hub',
                'core:game_play',
                'core:game_rating',
                # Student panel APIs (web)
                'core:student_panel_dashboard_api',
                'core:student_panel_groups_api',
                'core:student_panel_attendance_api',
                'core:student_panel_payments_api',
                'core:student_game_status_api',
                'core:student_game_result_api',
                'core:game_convert_balls_api',
                'core:game_balls_config_api',
                'core:game_config_api',
                'core:game_suggestion_api',
                'core:game_student_questions_api',
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
                'core:notification_read_one',
                'core:notification_preferences',
                'core:notifications_mark_read_api',
                # Parent panel APIs
                'core:parent_panel_children_api',
                'core:parent_panel_child_dashboard_api',
                'core:parent_panel_child_groups_api',
                'core:parent_panel_child_attendance_api',
                'core:parent_panel_child_payments_api',
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
                'core:notification_read_one',
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
                # Lesson preview (global + namespaced)
                'api_calculate_lessons',
                'education:calculate_lessons_api',
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
            'names': {
                'logout',
                'api_calculate_lessons',
                'education:calculate_lessons_api',
                # HR (global + slug-prefixed, namespace yo'q)
                'hr_employees_api',
                'hr_employee_detail_api',
                'hr_available_teachers_api',
                'hr_employees_api_prefixed',
                'hr_employee_detail_api_prefixed',
                'hr_available_teachers_api_prefixed',
            },
        },
        'director': {
            'namespaces': {'core', 'education', 'chaqmoq', 'store', 'billing', 'marketing', 'accounts'},
            'names': {
                'logout',
                'api_calculate_lessons',
                'education:calculate_lessons_api',
                'hr_employees_api',
                'hr_employee_detail_api',
                'hr_available_teachers_api',
                'hr_employees_api_prefixed',
                'hr_employee_detail_api_prefixed',
                'hr_available_teachers_api_prefixed',
            },
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

        path = request.path
        if _is_skipped_path(path):
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

        # Slug-prefix URL lar uchun namespace bo'sh bo'lishi mumkin
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
                "RBAC: user %s (role=%s) blocked from '%s', path=%s",
                request.user.pk, user_role, full_name, path,
            )
            if _wants_json_response(request, path):
                return JsonResponse(
                    {
                        "ok": False,
                        "error": "Bu amal uchun ruxsat yo'q.",
                        "code": "rbac_forbidden",
                    },
                    status=403,
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
        # Bare url_name fallback (namespaced full_name mos kelmasa)
        if url_name_only := full_name.split(':')[-1]:
            if url_name_only in allowed_names:
                return True

        return False
