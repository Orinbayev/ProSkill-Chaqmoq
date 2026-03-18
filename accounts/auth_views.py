"""
Custom authentication views for role-based redirects.
Subdomain logic removed — uses path-based resolution only.
"""

from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch
from django.conf import settings
from accounts.api_auth import record_activity


class SecureLoginView(auth_views.LoginView):
    """
    Secure login view with role-based redirects.
    Supports optional center_slug kwarg (from /c/<slug>/hisob/login/).
    """

    template_name = 'accounts/login.html'

    def dispatch(self, request, *args, **kwargs):
        """Prevent redirect loop — already authenticated users go home."""
        if request.user.is_authenticated:
            return redirect(self._get_home_url(request.user))
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
        return response

    def form_valid(self, form):
        response = super().form_valid(form)
        record_activity(self.request.user, "Login successful (Website)", request=self.request)
        return response

    def get_success_url(self):
        return self._get_home_url(self.request.user)

    def get_redirect_url(self):
        return self.get_success_url()

    # ── helpers ──────────────────────────────────────────────────

    def _get_home_url(self, user):
        """
        Role-based redirect after login.
        - SuperAdmin  → /platform/
        - Director/Manager/Teacher/Student → /  (core:home, middleware sets center)
        """
        if user.is_superuser:
            try:
                return reverse('platform_global:superadmin_dashboard')
            except NoReverseMatch:
                pass

        # Check if URL contained center_slug — if so, go to center home
        # (middleware already attached request.center from the slug)
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
