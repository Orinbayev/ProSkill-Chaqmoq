from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.urls import re_path
from django.views.static import serve
from django.http import HttpResponse
from accounts import api_auth
from accounts.auth_views import SecureLoginView
from accounts.views import test_db, test_center
from billing import click_views as billing_click_views
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from marketing import views as marketing_views
from education import views as education_views
from education import hr_views as education_hr_views


urlpatterns = [
    # ✅ TEST URLS (MUST BE FIRST)
    path('test-db/', test_db),
    path('test-center/', test_center),

    # 📄 API Dokumentatsiya (faqat staff/admin uchun)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # 🔹 Admin panel
    path('admin/', admin.site.urls),

    # 🔹 Auth
    path('hisob/login/', include('accounts.auth_urls')),
    # ✅ /login/ — ergonomik alias, faqat login view. Eski /hisob/login/
    # va uning URL name'lari ("login", "forgot_password_*", bot API'lar)
    # o'zgarmaydi — bu alias faqat /login/ kirish nuqtasini qo'shadi.
    path('login/', SecureLoginView.as_view(), name='login_alias'),
    path('api/v1/auth/link-telegram/', api_auth.link_telegram_api, name='api_link_telegram'),
    path('api/calculate-lessons/', education_views.calculate_lessons_api, name='api_calculate_lessons'),
    path('api/hr/employees/', education_hr_views.employees_api, name='hr_employees_api'),
    path('api/hr/employees/<int:employee_id>/', education_hr_views.employee_detail_api, name='hr_employee_detail_api'),
    path('api/hr/teachers/available/', education_hr_views.available_teachers_api, name='hr_available_teachers_api'),

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
    path('robots.txt', marketing_views.robots_txt, name='robots_txt'),
    path('sitemap.xml', marketing_views.sitemap_xml, name='sitemap_xml'),

    # 🔹 Global Platform (Fixed Prefix)
    path('platform/', include(('accounts.urls', 'accounts'), namespace='platform_global')),
    path("i18n/", include("django.conf.urls.i18n")),

    # 🔹 Legacy slug-prefixed marketing URLs → canonical marketing pages
    re_path(
        r'^(?P<center_slug>[a-z0-9][a-z0-9\-]{0,62})/(?P<lang_code>uz|ru|en)/(?:(?P<page_slug>about|features|pricing|demo|resources|support|vacancies|privacy|terms)/)?$',
        marketing_views.legacy_prefixed_marketing_redirect,
        name='legacy_prefixed_marketing_lang_redirect',
    ),
    re_path(
        r'^(?P<center_slug>[a-z0-9][a-z0-9\-]{0,62})/(?P<page_slug>about|features|pricing|demo|resources|support|vacancies|privacy|terms)/$',
        marketing_views.legacy_prefixed_marketing_redirect,
        name='legacy_prefixed_marketing_redirect',
    ),

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
    # ⚡ Chaqmoq Game — alohida mobil o'yin ilovasi uchun API.
    # core.urls ildizga ('') ulangani uchun undan OLDIN turishi shart.
    path('api/mobile/game/', include('game.mobile_urls')),

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
