from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('hisob/login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/',      auth_views.LogoutView.as_view(next_page='login'),                  name='logout'),

    # Apps
    path('', include(('core.urls', 'core'), namespace='core')),
    path('hisob/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('chaqmoq/', include(('chaqmoq.urls', 'chaqmoq'), namespace='chaqmoq')),
    path('talim/', include(('education.urls', 'education'), namespace='education')),
    path("do'kon/", include(('store.urls', 'store'), namespace='store')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
