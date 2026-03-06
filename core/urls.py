from django.urls import path, include
from . import views, api_views, api_dashboard
from accounts import views as accounts_views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),

    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/<int:pk>/', views.teacher_detail, name='teacher_detail'),
    path('teachers/<int:pk>/edit/', views.teacher_edit, name='teacher_edit'),
    path("user/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("user/<int:pk>/delete/", views.user_delete, name="user_delete"),
    path("user/<int:pk>/view/", views.user_view, name="user_view"),
    path("users/export-excel/", views.stat_users_export_excel, name="users_export_excel"),
    path('teachers/<int:pk>/delete/', views.teacher_delete, name='teacher_delete'),


    path('stat/managers/',  views.stat_managers,  name='stat_managers'),
    path('stat/teachers/',  views.stat_teachers,  name='stat_teachers'),
    path('stat/students/',  views.stat_students,  name='stat_students'),
    path('stat/parents/',   views.stat_parents,   name='stat_parents'),
    path('parents/add/',    views.parent_add,     name='parent_add'),
    path('parents/<int:pk>/edit/', views.parent_edit, name='parent_edit'),
    path('parents/<int:pk>/delete/', views.parent_delete, name='parent_delete'),
    path('parents/settings/', views.update_center_donation_settings, name='update_center_donation_settings'),
    path('dashboard/parent/', views.dashboard_parent, name='dashboard_parent'),
    path('dashboard/parent/toggle/<int:student_id>/', views.toggle_child, name='toggle_child'),
    path('stat/products/',  views.stat_products,  name='stat_products'),
    path('stat/requests/',  views.stat_requests,  name='stat_requests'),
    path('stat/ledger/',    views.stat_ledger,    name='stat_ledger'),
    path("users/import-excel/", views.users_import_excel, name="users_import_excel"),
    path("users/download-template/", views.users_download_template, name="users_download_template"),
    path("profil/", include([
        path("", accounts_views.user_edit, name="profile"),
    ])),
    
    # ✅ Student Archive Actions
    path("students/<int:pk>/archive/", views.archive_student, name="archive_student"),
    path("students/<int:pk>/restore/", views.restore_student, name="restore_student"),
    path("students/<int:pk>/hard-delete/", views.hard_delete_student, name="hard_delete_student"),
    
    # Notifications
    path('notifications/', views.notifications_view, name="notifications"),
    path('notifications/read/', views.notifications_mark_read, name="notifications_mark_read"),
    path('notifications/api/read-all/', api_views.notifications_mark_read_api, name='notifications_mark_read_api'),
    path('api/director/stats/', api_views.director_stats_api, name='director_stats_api'),
    path('api/director/dashboard/', api_dashboard.DirectorDashboardAPIView.as_view(), name='director_dashboard_api'),
    path('api/director/dashboard/students-chart/', api_dashboard.StudentChartAPIView.as_view(), name='student_chart_api'),
    path('dashboard/stats/', views.dashboard_stats_premium, name='dashboard_stats_premium'),
    path('dashboard/students/low-activity/', views.low_activity_students, name='low_activity_students'),
    path('notifications/broadcast/', views.notification_broadcast, name="notification_broadcast"),
]

