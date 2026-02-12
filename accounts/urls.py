from django.urls import path, include
from . import views
from .views_superadmin import superadmin_dashboard, center_create, center_edit
from . import api_superadmin
from . import views_platform # New HTML Views

app_name = "accounts"

# --- SaaS Platform URLs (Global) ---
platform_patterns = [
    path("", superadmin_dashboard, name="superadmin_dashboard"),
    path("centers/", views.center_picker, name="center_picker"),
    path("center-switch/", views.center_switch, name="center_switch"),
    path("center/create/", center_create, name="center_create"),
    path("center/<int:pk>/edit/", center_edit, name="center_edit"),
    path("centers/<int:pk>/manage/", views.center_manage, name="center_manage"),
    path("centers/<int:pk>/stats/", views.center_stats_view, name="center_stats"),
    
    # ✅ HTML Pages for Management (Fixing JSON Response Issue)
    path("plans/", views_platform.plans_list_view, name="plans_ui"),
    path("promos/", views_platform.promos_list_view, name="promos_ui"),

    # API Endpoints (Used by JS)
    path("api/centers/create/", api_superadmin.center_create_api, name="api_center_create"),
    path("api/centers/list/", api_superadmin.center_stats_api, name="api_center_list_stats"), 
    path("api/centers/<int:center_id>/", api_superadmin.center_detail_api, name="api_center_detail"),
    path("api/centers/<int:center_id>/update/", api_superadmin.center_update_api, name="api_center_update"),
    path("api/centers/<int:center_id>/delete/", api_superadmin.center_delete_api, name="api_center_delete"),
    path("api/centers/<int:center_id>/archive/", api_superadmin.center_archive_api, name="api_center_archive"),
    
    # Plans & Promo APIs
    path("api/plans/", include([
        path("list/", api_superadmin.plan_list_api, name="api_plan_list"),
        path("create/", api_superadmin.plan_create_api, name="api_plan_create"),
        path("<int:plan_id>/update/", api_superadmin.plan_update_api, name="api_plan_update"),
        path("<int:plan_id>/delete/", api_superadmin.plan_delete_api, name="api_plan_delete"),
    ])),
    
    path("api/promos/", include([
        path("list/", api_superadmin.promo_list_api, name="api_promo_list"),
        path("create/", api_superadmin.promo_create_api, name="api_promo_create"),
        path("<int:promo_id>/update/", api_superadmin.promo_update_api, name="api_promo_update"),
        path("<int:promo_id>/delete/", api_superadmin.promo_delete_api, name="api_promo_delete"),
    ])),
]

# --- Tenant URLs (Center Specific) ---
tenant_patterns = [
    path("profil/", views.user_edit, name="profile"), 
    path("qoshish/", views.add_user, name="add_user"),
    path("user/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("oqtuvchi/<int:user_id>/", views.teacher_detail, name="teacher_detail"),
    path("talaba/<int:user_id>/", views.student_detail, name="student_detail"),
    path("logout/", views.logout_now, name="logout"),
]

urlpatterns = tenant_patterns + platform_patterns
