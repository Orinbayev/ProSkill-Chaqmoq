"""
config/slug_prefix_urls.py

URL patterns for /<center_slug>/ prefix.
No app_name defined to avoid W005 conflicts.
Views resolve identically; request.center is set by TenantMiddleware.
"""
from django.urls import path, include
from billing import click_views as billing_click_views

urlpatterns = [
    path('', include('core.urls')),
    path('hisob/', include('accounts.urls_tenant')),
    path('hisob/billing/', include('billing.urls')),
    path('chaqmoq/', include('chaqmoq.urls')),
    path('talim/', include('education.urls')),
    path("do'kon/", include('store.urls')),

    # ✅ Click endpoints (slug-prefixed fallback)
    path('click/prepare/', billing_click_views.click_prepare),
    path('click/complete/', billing_click_views.click_complete),
]
