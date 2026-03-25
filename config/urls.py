from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.urls import re_path
from django.views.static import serve
from django.http import HttpResponse
from accounts import api_auth
from accounts.views import test_db, test_center
from billing import click_views as billing_click_views


urlpatterns = [
    # ✅ TEST URLS (MUST BE FIRST)
    path('test-db/', test_db),
    path('test-center/', test_center),

    # 🔹 Admin panel
    path('admin/', admin.site.urls),

    # 🔹 Auth
    path('hisob/login/', include('accounts.auth_urls')),
    path('api/v1/auth/link-telegram/', api_auth.link_telegram_api, name='api_link_telegram'),

    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # ✅ Click Shop API endpoints — global root
    path('click/prepare/', billing_click_views.click_prepare, name='click_prepare'),
    path('click/complete/', billing_click_views.click_complete, name='click_complete'),
    path('click/webhook/', billing_click_views.click_webhook, name='click_webhook'),
    # Backward-compatible legacy callback paths.
    path('api/click/prepare/', billing_click_views.click_prepare, name='api_click_prepare'),
    path('api/click/complete/', billing_click_views.click_complete, name='api_click_complete'),
    path('api/click/webhook/', billing_click_views.click_webhook, name='api_click_webhook'),

    # Browser Redirects
    path('payment/success/', billing_click_views.payment_success, name='payment_success'),
    path('payment/cancel/', billing_click_views.payment_cancel, name='payment_cancel'),

    # 🔹 Global Platform (Fixed Prefix)
    path('platform/', include(('accounts.urls', 'accounts'), namespace='platform_global')),
    path("i18n/", include("django.conf.urls.i18n")),

    # 🔹 Localized Marketing Website (/uz/, /ru/, /en/)
    re_path(
        r'^(?P<lang_code>uz|ru|en)/',
        include(('marketing.urls_i18n', 'marketing_i18n'), namespace='marketing_i18n'),
    ),

    # 🔹 Public Marketing Website
    path('', include(('marketing.urls', 'marketing'), namespace='marketing')),

    # 🔹 Main Application (Tenant Aware)
    # Middleware strips /<slug>/ prefix and rewrites path_info,
    # so these patterns match both /stat/students/ and /proskill/stat/students/
    path('', include(('core.urls', 'core'), namespace='core')),
    path('hisob/', include(('accounts.urls_tenant', 'accounts'), namespace='accounts')),
    path('hisob/billing/', include(('billing.urls', 'billing'), namespace='billing')),
    path('chaqmoq/', include(('chaqmoq.urls', 'chaqmoq'), namespace='chaqmoq')),
    path('talim/', include(('education.urls', 'education'), namespace='education')),
    path("do'kon/", include(('store.urls', 'store'), namespace='store')),

    # ✅ Center-scoped login/billing (legacy /c/<slug>/ support)
    path('c/<slug:center_slug>/', include(('core.center_urls', 'center'), namespace='center')),

    # ✅ /<center_slug>/ prefix — NON-CAPTURING re_path so center_slug is NOT
    # passed as kwarg to views (avoids TypeError in all view functions).
    # Middleware reads slug from request.path and sets request.center.
    re_path(r'^(?:[a-z0-9][a-z0-9\-]{0,62})/', include('config.slug_prefix_urls')),
]



# 🔹 Media
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]

# ✅ HEALTH CHECK VIEW (Render uchun)
def health_check(request):
    return HttpResponse("OK", status=200)

urlpatterns.insert(2, path('health/', health_check))
