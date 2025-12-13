from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),

    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/<int:pk>/', views.teacher_detail, name='teacher_detail'),
    path('teachers/<int:pk>/edit/', views.teacher_edit, name='teacher_edit'),
    path("user/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("user/<int:pk>/delete/", views.user_delete, name="user_delete"),
    path("user/<int:pk>/view/", views.user_view, name="user_view"),
    path("students/export-excel/", views.stat_students_export_excel, name="students_export_excel"),
    path('teachers/<int:pk>/delete/', views.teacher_delete, name='teacher_delete'),


    path('stat/managers/',  views.stat_managers,  name='stat_managers'),
    path('stat/teachers/',  views.stat_teachers,  name='stat_teachers'),
    path('stat/students/',  views.stat_students,  name='stat_students'),
    path('stat/products/',  views.stat_products,  name='stat_products'),
    path('stat/requests/',  views.stat_requests,  name='stat_requests'),
    path('stat/ledger/',    views.stat_ledger,    name='stat_ledger'),
]

