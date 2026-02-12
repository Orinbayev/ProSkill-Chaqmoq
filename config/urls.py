from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.urls import re_path
from django.views.static import serve
from django.shortcuts import redirect

urlpatterns = [
    # 🔹 Admin panel
    path('admin/', admin.site.urls),

    # 🔹 Auth
    path('hisob/login/', include('accounts.auth_urls')),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # 🔹 Global Platform (Fixed Prefix)
    path('platform/', include(('accounts.urls', 'accounts'), namespace='platform_global')),

    # 🔹 Main Application (Tenant Aware)
    path('', include(('core.urls', 'core'), namespace='core')),
    path('hisob/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('hisob/billing/', include(('billing.urls', 'billing'), namespace='billing')),
    path('chaqmoq/', include(('chaqmoq.urls', 'chaqmoq'), namespace='chaqmoq')),
    path('talim/', include(('education.urls', 'education'), namespace='education')),
    path("do'kon/", include(('store.urls', 'store'), namespace='store')),
]

# 🔹 Media
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
