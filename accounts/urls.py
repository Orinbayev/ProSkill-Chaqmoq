# accounts/urls.py
from django.urls import path
from . import views
from .views_superadmin import superadmin_dashboard, center_create, center_edit
from . import api_superadmin


app_name = "accounts"

urlpatterns = [
    path("qoshish/", views.add_user, name="add_user"),
    path("user/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("oqtuvchi/<int:user_id>/", views.teacher_detail, name="teacher_detail"),
    path("talaba/<int:user_id>/", views.student_detail, name="student_detail"),
    path("logout/", views.logout_now, name="logout"),

    # ✅ NEW: siz xohlagan URL’lar (name saqlanadi)
    path("center-picker/", views.center_picker, name="center_picker"),
    path("center-switch/", views.center_switch, name="center_switch"),

    # ✅ OLD: alias (buzilmasin)
    path("center/picker/", views.center_picker),
    path("center/switch/", views.center_switch),

    path("centers/<int:pk>/manage/", views.center_manage, name="center_manage"),
    path("centers/<int:pk>/stats/", views.center_stats_view, name="center_stats"),

    path("logout/", views.logout_view, name="logout"),
    
    # ✅ Super Admin URLs
    path("superadmin/", superadmin_dashboard, name="superadmin_dashboard"),
    path("superadmin/center/create/", center_create, name="center_create"),
    path("superadmin/center/<int:pk>/edit/", center_edit, name="center_edit"),

    # ✅ API Endpoints
    path("api/centers/create/", api_superadmin.center_create_api, name="api_center_create"),
    path("api/centers/<int:center_id>/", api_superadmin.center_detail_api, name="api_center_detail"),
    path("api/centers/<int:center_id>/stats/", api_superadmin.center_stats_api, name="api_center_stats"),
    path("api/centers/<int:center_id>/students/", api_superadmin.center_students_api, name="api_center_students"),
    path("api/centers/<int:center_id>/groups/", api_superadmin.center_groups_api, name="api_center_groups"),
    path("api/centers/<int:center_id>/payments/", api_superadmin.center_payments_api, name="api_center_payments"),
    path("api/centers/<int:center_id>/update/", api_superadmin.center_update_api, name="api_center_update"),
    path("api/centers/<int:center_id>/delete/", api_superadmin.center_delete_api, name="api_center_delete"),
    path("api/plans/create/", api_superadmin.plan_create_api, name="api_plan_create"),
    path("api/plans/list/", api_superadmin.plan_list_api, name="api_plan_list"),
    path("api/plans/<int:plan_id>/update/", api_superadmin.plan_update_api, name="api_plan_update"),
    path("api/plans/<int:plan_id>/delete/", api_superadmin.plan_delete_api, name="api_plan_delete"),

    # Promocode APIs
    path("api/promos/list/", api_superadmin.promo_list_api, name="api_promo_list"),
    path("api/promos/create/", api_superadmin.promo_create_api, name="api_promo_create"),
    path("api/promos/<int:promo_id>/update/", api_superadmin.promo_update_api, name="api_promo_update"),
    path("api/promos/<int:promo_id>/delete/", api_superadmin.promo_delete_api, name="api_promo_delete"),


]
