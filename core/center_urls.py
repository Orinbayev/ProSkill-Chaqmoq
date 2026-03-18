"""
core/center_urls.py

Center-scoped URL routes accessible via:
    /c/<center_slug>/hisob/login/
    /c/<center_slug>/hisob/billing/...

ONLY login and billing are included here.
All other app routes remain unchanged at their existing paths.
"""

from django.urls import path, include
from accounts.auth_views import CenterScopedLoginView
from accounts import password_reset_views

app_name = 'center'

urlpatterns = [
    # ── Login (center-scoped) ────────────────────────────────────
    # Accessible: /c/<center_slug>/hisob/login/
    path(
        'hisob/login/',
        CenterScopedLoginView.as_view(),
        name='login',
    ),

    # ── Billing (center-scoped) ──────────────────────────────────
    # Accessible: /c/<center_slug>/hisob/billing/plans/
    path(
        'hisob/billing/',
        include(('billing.urls', 'billing_c'), namespace='billing_c'),
    ),
]
