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


# ✅ Center slug home redirect: /<slug>/ → /c/<slug>/hisob/login/
def center_slug_home(request, center_slug):
    """
    Allows each center to have its own entry URL like /amirxon2/
    Redirects to the center's scoped login page.
    Returns 404 if no center with that slug exists.
    """
    from accounts.models import Center
    from django.http import Http404
    center = Center._default_manager.filter(slug=center_slug, is_deleted=False).first()
    if not center:
        raise Http404(f"'{center_slug}' slugli markaz topilmadi.")
    return redirect(f'/c/{center_slug}/hisob/login/')


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
    path('', include(('core.urls', 'core'), namespace='core')),
    path('hisob/', include(('accounts.urls_tenant', 'accounts'), namespace='accounts')),
    path('hisob/billing/', include(('billing.urls', 'billing'), namespace='billing')),
    path('chaqmoq/', include(('chaqmoq.urls', 'chaqmoq'), namespace='chaqmoq')),
    path('talim/', include(('education.urls', 'education'), namespace='education')),
    path("do'kon/", include(('store.urls', 'store'), namespace='store')),

    # ✅ Center-scoped optional routes: /c/<center_slug>/hisob/login/ and /c/<center_slug>/hisob/billing/
    # These are ADDITIVE — all existing routes above remain untouched.
    path('c/<slug:center_slug>/', include(('core.center_urls', 'center'), namespace='center')),

    # ✅ Root-level center slug: /<center_slug>/ → redirect to center login
    # IMPORTANT: This MUST be the LAST pattern — only activates when nothing else matched.
    path('<slug:center_slug>/', center_slug_home),
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
