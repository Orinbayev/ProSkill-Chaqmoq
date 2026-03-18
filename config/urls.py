from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views, login, get_user_model
from django.urls import re_path
from django.views.static import serve
from django.shortcuts import redirect
from django.http import HttpResponse
from accounts import api_auth


# TEMPORARY EMERGENCY LOGIN VIEW
from django.contrib.auth import login, get_user_model
def emergency_login_view(request):
    User = get_user_model()
    # Try multiple variants
    emails = ['amirxondev@gmail.com', 'yangi_admin@gmail.com']
    u = None
    for email in emails:
        u = User.objects.filter(email__iexact=email).first()
        if u: break
    
    # Last resort: any superuser
    if not u:
        u = User.objects.filter(is_superuser=True).first()
    
    if u:
        u.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, u)
        return redirect('/')
    return HttpResponse(f"No user found! Checked: {emails}", status=403)

urlpatterns = [
    # 🚨 EMERGENCY LOGIN URL (Remove after fixing login!)
    path('emergency-enter-now/', emergency_login_view),

    # 🔹 Admin panel
    path('admin/', admin.site.urls),

    # 🔹 Auth
    path('hisob/login/', include('accounts.auth_urls')),
    path('api/v1/auth/link-telegram/', api_auth.link_telegram_api, name='api_link_telegram'),

    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # 🔹 Global Platform (Fixed Prefix)
    path('platform/', include(('accounts.urls', 'accounts'), namespace='platform_global')),

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

urlpatterns.insert(0, path('health/', health_check))
