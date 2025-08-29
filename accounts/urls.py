# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',  auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),  # POST bilan chiqish
    # Manager uchun tezkor sahifalar (agar hali qo'ygan bo'lsang qoldir):
    path('manager/oqituvchi-qoshish/', views.manager_add_teacher, name='add_teacher'),
    path('manager/oquvchi-qoshish/',   views.manager_add_student, name='add_student'),
]
