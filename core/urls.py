from django.urls import path, include
from . import views, api_views, api_dashboard, trash, dashboard_views
from accounts import views as accounts_views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('api/mobile/', include('core.mobile_urls')),

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
    path('notifications/preferences/', views.notification_preferences_view, name="notification_preferences"),
    path('notifications/api/read-all/', api_views.notifications_mark_read_api, name='notifications_mark_read_api'),
    path('dashboard/students/low-activity/', views.low_activity_students, name='low_activity_students'),
    path('notifications/broadcast/', views.notification_broadcast, name="notification_broadcast"),

    # ✅ Trash & Soft Delete
    path('trash/', trash.deleted_items_list, name='deleted_items'),
    path('trash/<str:model_key>/<int:pk>/restore/', trash.restore_item, name='restore_item'),
    path('trash/<str:model_key>/<int:pk>/hard-delete/', trash.hard_delete_item, name='hard_delete_item'),
    path('trash/toggle-access/', views.toggle_manager_trash_access, name='toggle_manager_trash_access'),
    path('trash/manager-access/<int:user_id>/', trash.toggle_manager_user_trash_access, name='toggle_manager_user_trash_access'),
    
    # ═══════════════════ Director Dashboards ═══════════════════
    path('boshqaruv/',                    dashboard_views.director_boshqaruv,               name='director_boshqaruv'),
    path('api/boshqaruv/',                dashboard_views.director_boshqaruv_api,           name='director_boshqaruv_api'),
    path('api/boshqaruv/chat/',           dashboard_views.director_boshqaruv_chat,          name='director_boshqaruv_chat'),
    path('dashboards/',                   dashboard_views.dashboard_hub,                    name='dashboard_hub'),
    path('dashboards/overview/',          dashboard_views.director_overview,                name='director_overview'),
    path('dashboards/financial/',         dashboard_views.financial_dashboard,               name='financial_dashboard'),
    path('dashboards/students/',          dashboard_views.student_performance_dashboard,     name='student_performance_dashboard'),
    path('dashboards/teachers/',          dashboard_views.teacher_performance_dashboard,     name='teacher_performance_dashboard'),
    path('dashboards/groups/',            dashboard_views.groups_dashboard,                  name='groups_dashboard'),
    path('dashboards/billing/',           dashboard_views.billing_dashboard,                 name='billing_dashboard'),
    path('dashboards/marketing/',         dashboard_views.marketing_dashboard,               name='marketing_dashboard'),
    path('dashboards/inventory/',         dashboard_views.inventory_dashboard,               name='inventory_dashboard'),
    path('dashboards/analytics/',         dashboard_views.analytics_dashboard,               name='analytics_dashboard'),
    # Dashboard APIs
    path('api/dashboards/financial/',     dashboard_views.financial_api,                     name='financial_api'),
    path('api/dashboards/overview/',      dashboard_views.overview_api,                      name='overview_api'),
    path('api/dashboards/students/',      dashboard_views.student_performance_api,           name='student_performance_api'),
    path('api/dashboards/teachers/',      dashboard_views.teacher_performance_api,           name='teacher_performance_api'),
    path('api/dashboards/groups/',        dashboard_views.groups_api,                        name='groups_api'),
    path('api/dashboards/billing/',       dashboard_views.billing_api,                       name='billing_api'),
    path('api/dashboards/marketing/',     dashboard_views.marketing_api,                     name='marketing_api'),
    path('api/dashboards/inventory/',     dashboard_views.inventory_api,                     name='inventory_api'),
    path('api/dashboards/analytics/',     dashboard_views.analytics_api,                     name='analytics_api'),
    # Director panel APIs
    path('api/director/dashboard/',              api_dashboard.DirectorDashboardAPIView.as_view(),  name='director_dashboard_api'),
    path('api/director/dashboard/debtor-diagram/', api_dashboard.DebtorDiagramAPIView.as_view(),   name='debtor_diagram_api'),
    path('api/director/dashboard/category-revenue/', api_dashboard.CategoryRevenueAPIView.as_view(), name='category_revenue_api'),
    path('api/director/dashboard/students-chart/', api_dashboard.StudentChartAPIView.as_view(),    name='student_chart_api'),
    # ✅ Group permissions
    path('permissions/manager-add-student/', views.toggle_manager_can_add_student, name='toggle_manager_can_add_student'),
    path('permissions/manager-remove-student/', views.toggle_manager_can_remove_student, name='toggle_manager_can_remove_student'),
    path('permissions/teacher-add-student/', views.toggle_teacher_can_add_student, name='toggle_teacher_can_add_student'),
    path('permissions/teacher-remove-student/', views.toggle_teacher_can_remove_student, name='toggle_teacher_can_remove_student'),
    path('permissions/', views.group_permissions_settings, name='group_permissions_settings'),
]
