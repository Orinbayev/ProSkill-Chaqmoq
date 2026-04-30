"""
Custom authentication views for role-based redirects.
Subdomain logic removed — uses path-based resolution only.

PERF v2:
- form_invalid: 2 DB query (email + phone) → kerak bo'lmagan holda o'tkazib yuboriladi
- form_valid: record_activity + Telegram xabari BLOCKING edi — Thread orqali non-blocking qilindi
- _record_async: login tugagandan keyin fon threadida ishlaydi, response ga ta'sir qilmaydi

PERF v3:
- Orphan user (center is None) va role bo'sh bo'lgan user login qila olmaydi — aniq xato.
- Login request timing va SQL query count log qilinadi (`chaqmoq.login.perf`).
"""

import hashlib
import logging
import threading
import time

from django.contrib.auth import views as auth_views
from django.core.cache import cache
from django.db import connection
from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch

logger = logging.getLogger(__name__)
perf_logger = logging.getLogger("chaqmoq.login.perf")


def _record_activity_bg(user, action, request_meta: dict):
    """
    record_activity() ni fon threadida ishlatadi.
    Login response ga hech qanday ta'sir ko'rsatmaydi.
    Telegram xabari ham bu thread ichida yuboriladi.
    """
    try:
        from accounts.api_auth import record_activity

        class _FakeRequest:
            """record_activity META ni kutadi, lekin biz uni dict sifatida beramiz."""
            def __init__(self, meta):
                self.META = meta

        record_activity(user, action, request=_FakeRequest(request_meta))
    except Exception as exc:
        logger.warning("_record_activity_bg xatosi: %s", exc)


class SecureLoginView(auth_views.LoginView):
    """
    Secure login view with role-based redirects.
    Supports optional center_slug kwarg (from /c/<slug>/hisob/login/).
    """

    template_name = 'accounts/login.html'
    LOGIN_MAX_FAILED_ATTEMPTS = 8
    LOGIN_THROTTLE_WINDOW_SECONDS = 15 * 60

    ORPHAN_ERROR = (
        "Siz hech qaysi o'quv markazga biriktirilmagansiz. "
        "Administrator bilan bog'laning."
    )
    NO_ROLE_ERROR = "Sizga rol biriktirilmagan. Administrator bilan bog'laning."

    def dispatch(self, request, *args, **kwargs):
        """Prevent redirect loop — already authenticated users go home.

        Measures total request duration and SQL query count per login.
        Log line: `chaqmoq.login.perf` with ms + query count.
        """
        t0 = time.perf_counter()
        q0 = len(connection.queries) if connection.queries_logged else 0

        try:
            if request.user.is_authenticated:
                return redirect(self._get_home_url(request.user))
            if request.method == "POST":
                username = (request.POST.get("username") or "").strip().lower()
                if self._is_login_locked(request, username):
                    form = self.get_form()
                    form.add_error(None, "Ko'p urinish bo'ldi. 15 daqiqadan keyin qayta urinib ko'ring.")
                    return self.render_to_response(self.get_context_data(form=form))
            return super().dispatch(request, *args, **kwargs)
        finally:
            if request.method == "POST":
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                query_count = (len(connection.queries) - q0) if connection.queries_logged else -1
                perf_logger.info(
                    "login POST: %.1fms, %s queries, path=%s, authed=%s",
                    elapsed_ms,
                    query_count if query_count >= 0 else "?",
                    request.path,
                    request.user.is_authenticated,
                )

    def form_invalid(self, form):
        response = super().form_invalid(form)
        email = (form.data.get('username') or '').strip()

        # ✅ PERF FIX: Noto'g'ri login bo'lsa ham 2 DB query ketardi (email + phone).
        # Endi faqat throttle key uchun email ishlatamiz, DB query YO'Q.
        # UserActivity.create fon threadida bajariladi.
        self._register_failed_attempt(self.request, email)

        if email:
            # DB query va Telegram xabari fon threadida — response tezlashadi
            meta_copy = {
                k: v for k, v in self.request.META.items()
                if k in ('HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR', 'HTTP_USER_AGENT')
            }
            threading.Thread(
                target=self._record_failed_login_bg,
                args=(email, meta_copy),
                daemon=True,
            ).start()

        return response

    def form_valid(self, form):
        # ✅ Orphan/no-role guard: superuser bundan mustasno, qolgan rollar
        # uchun tenant va role majburiy. Bu yerda tekshirib, login qilishdan
        # oldin aniq xato chiqaramiz (session ga user yozilmaydi).
        user = form.get_user()
        if not user.is_superuser:
            reason = None
            if getattr(user, "center", None) is None:
                reason = self.ORPHAN_ERROR
            elif not (getattr(user, "role", "") or "").strip():
                reason = self.NO_ROLE_ERROR
            if reason:
                # Throttle counter'ni oshirmaymiz — parol to'g'ri edi, faqat
                # konfiguratsiya muammosi. Failed-login yozuvi ham yozilmaydi.
                form.add_error(None, reason)
                return self.render_to_response(self.get_context_data(form=form))

        remember = self.request.POST.get("remember")
        if remember:
            self.request.session.set_expiry(2592000)
        else:
            self.request.session.set_expiry(0)

        # ✅ PERF FIX: super().form_valid() → session write, redirect.
        # record_activity + Telegram xabari BLOCKING edi (5s timeout).
        # Endi fon threadida ishlaydi — response darhol qaytadi.
        response = super().form_valid(form)
        self._clear_failed_attempts(self.request, form.cleaned_data.get("username", ""))

        user = self.request.user
        meta_copy = {
            k: v for k, v in self.request.META.items()
            if k in ('HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR', 'HTTP_USER_AGENT')
        }
        threading.Thread(
            target=_record_activity_bg,
            args=(user, "Login successful (Website)", meta_copy),
            daemon=True,
        ).start()

        return response

    def get_success_url(self):
        return self._get_home_url(self.request.user)

    def get_redirect_url(self):
        return self.get_success_url()

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _record_failed_login_bg(email: str, meta_copy: dict):
        """
        Noto'g'ri login uchun UserActivity ni fon threadida yozadi.
        DB query va Telegram xabari shu yerda bo'ladi.
        """
        try:
            from accounts.models import User
            from accounts.utils import normalize_phone

            user = None
            try:
                user = User.objects.only(
                    "id", "email", "phone_number", "telegram_id",
                    "is_telegram_linked", "is_demo_user",
                ).get(email__iexact=email)
            except User.DoesNotExist:
                norm = normalize_phone(email)
                matches = list(
                    User.objects.only(
                        "id", "email", "phone_number", "telegram_id",
                        "is_telegram_linked", "is_demo_user",
                    ).filter(phone_number=norm).order_by("id")[:2]
                )
                if len(matches) == 1:
                    user = matches[0]

            if user:
                _record_activity_bg(user, "Failed login attempt detected", meta_copy)
        except Exception as exc:
            logger.warning("_record_failed_login_bg xatosi: %s", exc)

    def _client_ip(self, request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def _throttle_key(self, request, username):
        normalized_username = (username or "").strip().lower()
        raw_key = f"{self._client_ip(request)}:{normalized_username}"
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return f"login:throttle:{key_hash}"

    def _is_login_locked(self, request, username):
        key = self._throttle_key(request, username)
        return int(cache.get(key, 0) or 0) >= self.LOGIN_MAX_FAILED_ATTEMPTS

    def _register_failed_attempt(self, request, username):
        key = self._throttle_key(request, username)
        attempts = int(cache.get(key, 0) or 0) + 1
        cache.set(key, attempts, timeout=self.LOGIN_THROTTLE_WINDOW_SECONDS)

    def _clear_failed_attempts(self, request, username):
        key = self._throttle_key(request, username)
        cache.delete(key)

    def _get_home_url(self, user):
        """
        Role-based redirect after login.
        - SuperAdmin  → /platform/
        - Users with center → /<center_slug>/  (slug-prefixed home)
        - Orphan users → /
        """
        if user.is_superuser:
            try:
                return reverse('platform_global:superadmin_dashboard')
            except NoReverseMatch:
                return '/platform/'

        # Redirect to /<slug>/ so URL bar always shows center name
        center = getattr(user, 'center', None)
        if center and hasattr(center, 'slug') and center.slug:
            return f'/{center.slug}/'

        try:
            return reverse('core:home')
        except NoReverseMatch:
            return '/'


class CenterScopedLoginView(SecureLoginView):
    """
    Login view reachable via /c/<center_slug>/hisob/login/.

    Enforces that the logging-in user actually belongs to the center
    named in the URL slug, preventing cross-center logins.
    """

    def form_valid(self, form):
        user = form.get_user()
        url_slug = self.kwargs.get('center_slug') or getattr(
            self.request, 'url_center_slug', None
        )

        if url_slug and not user.is_superuser:
            user_center = getattr(user, 'center', None)
            if not user_center or user_center.slug != url_slug:
                form.add_error(
                    None,
                    "Siz bu markazga kirish huquqiga ega emassiz."
                )
                return self.form_invalid(form)

        return super().form_valid(form)
