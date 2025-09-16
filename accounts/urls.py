# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',  auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('manager/oqituvchi-qoshish/', views.manager_add_teacher, name='add_teacher'),
    path('manager/oquvchi-qoshish/',   views.manager_add_student, name='add_student'),

    # CRUD
    path('manager/manager-qoshish/',   views.manager_add_manager, name='add_manager'),
    path('user/<int:pk>/edit/',        views.user_edit,  name='user_edit'),
    path('user/<int:pk>/delete/',      views.user_delete, name='user_delete'),
]
