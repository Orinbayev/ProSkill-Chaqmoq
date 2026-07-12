from django.urls import path, include
from . import views
from .views_superadmin import (
    superadmin_dashboard,
    superadmin_plans,
    center_create,
    center_edit,
    toggle_center_ui_feature,
    update_center_capacity,
)
from . import api_superadmin
from . import views_platform # New HTML Views
from .views import test_db, test_center

app_name = "accounts"

# --- SaaS Platform URLs (Global) ---
platform_patterns = [
    path("", superadmin_dashboard, name="superadmin_dashboard"),
    path("plans/matritsa/", superadmin_plans, name="superadmin_plans"),
    path("centers/", views.center_picker, name="center_picker"),
    path("center-switch/", views.center_switch, name="center_switch"),
    path("center/create/", center_create, name="center_create"),
    path("center/<int:pk>/edit/", center_edit, name="center_edit"),
    path("center/<int:center_pk>/toggle-feature/", toggle_center_ui_feature, name="toggle_center_ui_feature"),
    path("centers/<int:pk>/manage/", views.center_manage, name="center_manage"),
    path("centers/<int:pk>/stats/", views.center_stats_view, name="center_stats"),
    path("center/<int:pk>/update-capacity/", update_center_capacity, name="update_center_capacity"),
    
    # ✅ HTML Pages for Management (Fixing JSON Response Issue)
    path("plans/", views_platform.plans_list_view, name="plans_ui"),
    path("promos/", views_platform.promos_list_view, name="promos_ui"),
    path("marketing/", include(("marketing.urls_superadmin", "marketing"), namespace="marketing")),

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
        path("features/", api_superadmin.features_list_api, name="api_features_list"),
        path("create/", api_superadmin.plan_create_api, name="api_plan_create"),
        path("<int:plan_id>/update/", api_superadmin.plan_update_api, name="api_plan_update"),
        path("<int:plan_id>/delete/", api_superadmin.plan_delete_api, name="api_plan_delete"),
        path("feature-rule/", api_superadmin.feature_rule_update, name="api_feature_rule_update"),
        path("feature/create/", api_superadmin.feature_create, name="api_feature_create"),
        path("set-popular/", api_superadmin.plan_set_popular, name="api_plan_set_popular"),
    ])),

    
    path("api/promos/", include([
        path("list/", api_superadmin.promo_list_api, name="api_promo_list"),
        path("create/", api_superadmin.promo_create_api, name="api_promo_create"),
        path("<int:promo_id>/update/", api_superadmin.promo_update_api, name="api_promo_update"),
        path("<int:promo_id>/delete/", api_superadmin.promo_delete_api, name="api_promo_delete"),
    ])),

    # SaaS Analytics
    path("api/finance/payments/", api_superadmin.payment_history_api, name="api_payment_history"),
]

# --- Tenant URLs (Center Specific) ---
tenant_patterns = [
    path("profil/", views.user_edit, name="profile"), 
    path("qoshish/", views.add_user, name="add_user"),
    path("user/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("user/<int:pk>/edit/ajax/", views.student_edit_ajax, name="student_edit_ajax"),
    path("oqtuvchi/<int:user_id>/", views.teacher_detail, name="teacher_detail"),
    path("talaba/<int:user_id>/", views.student_detail, name="student_detail"),
    path("logout/", views.logout_now, name="logout"),
    path("my-centers/", views.director_my_centers, name="my_centers"),
    path("switch-center/", views.director_switch_center, name="director_switch_center"),
    path("branch-request/", views.director_branch_request, name="branch_request"),
    path("branch/<int:center_id>/edit/", views.director_branch_edit, name="director_branch_edit"),
    path("branch/<int:center_id>/deactivate/", views.director_branch_deactivate, name="director_branch_deactivate"),
]

test_urlpatterns = [
    path("test-db/", test_db),
    path("test-center/", test_center),
]

urlpatterns = tenant_patterns + platform_patterns

urlpatterns += test_urlpatterns
