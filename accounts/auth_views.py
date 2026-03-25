"""
Custom authentication views for role-based redirects.
Subdomain logic removed — uses path-based resolution only.
"""

import hashlib

from django.contrib.auth import views as auth_views
from django.core.cache import cache
from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch
from accounts.api_auth import record_activity


class SecureLoginView(auth_views.LoginView):
    """
    Secure login view with role-based redirects.
    Supports optional center_slug kwarg (from /c/<slug>/hisob/login/).
    """

    template_name = 'accounts/login.html'
    LOGIN_MAX_FAILED_ATTEMPTS = 8
    LOGIN_THROTTLE_WINDOW_SECONDS = 15 * 60

    def dispatch(self, request, *args, **kwargs):
        """Prevent redirect loop — already authenticated users go home."""
        if request.user.is_authenticated:
            return redirect(self._get_home_url(request.user))
        if request.method == "POST":
            username = (request.POST.get("username") or "").strip().lower()
            if self._is_login_locked(request, username):
                form = self.get_form()
                form.add_error(None, "Ko'p urinish bo'ldi. 15 daqiqadan keyin qayta urinib ko'ring.")
                return self.render_to_response(self.get_context_data(form=form))
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        response = super().form_invalid(form)
        email = form.data.get('username', '')
        from accounts.models import User
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            user = User.objects.filter(phone_number=email).first()
        if user:
            record_activity(user, "Failed login attempt detected", request=self.request)
        self._register_failed_attempt(self.request, email)
        return response

    def form_valid(self, form):
        response = super().form_valid(form)
        self._clear_failed_attempts(self.request, form.cleaned_data.get("username", ""))
        record_activity(self.request.user, "Login successful (Website)", request=self.request)
        return response

    def get_success_url(self):
        return self._get_home_url(self.request.user)

    def get_redirect_url(self):
        return self.get_success_url()

    # ── helpers ──────────────────────────────────────────────────

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
