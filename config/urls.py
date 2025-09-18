"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from accounts.views import logout_view

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth (global nomlar: 'login', 'logout')
    path('hisob/login/',  auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    # EHTIYOT UCHUN: logout nomi global bo‘lsin (base.html `{% url 'logout' %}` ni qoplaydi)
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # App’lar
    path('', include(('core.urls', 'core'), namespace='core')),
    path('hisob/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('chaqmoq/', include(('chaqmoq.urls', 'chaqmoq'), namespace='chaqmoq')),
    path("ta'lim/", include(('education.urls', 'education'), namespace='education')),
    path("do'kon/", include(('store.urls', 'store'), namespace='store')),
    path("login/",  auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)