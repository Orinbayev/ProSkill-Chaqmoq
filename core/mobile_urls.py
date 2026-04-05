from django.urls import path

from . import mobile_api


urlpatterns = [
    path("auth/csrf/", mobile_api.mobile_auth_csrf, name="auth_csrf"),
    path("auth/login/", mobile_api.mobile_auth_login, name="auth_login"),
    path("auth/logout/", mobile_api.mobile_auth_logout, name="auth_logout"),
    path("auth/status/", mobile_api.mobile_auth_status, name="auth_status"),
    path("me/", mobile_api.mobile_me, name="me"),
    path("home/", mobile_api.mobile_role_home, name="home"),
    path("dashboard/director/", mobile_api.mobile_director_dashboard, name="director_dashboard"),
    path("teacher/home/", mobile_api.mobile_teacher_home, name="teacher_home"),
    path("student/home/", mobile_api.mobile_student_home, name="student_home"),
    path("parent/home/", mobile_api.mobile_parent_home, name="parent_home"),
    path("student/debt/", mobile_api.mobile_student_debt_breakdown, name="student_debt"),
    path("notifications/", mobile_api.mobile_notifications, name="notifications"),
    path("notifications/read-all/", mobile_api.mobile_notifications_read_all, name="notifications_read_all"),
    path("billing/status/", mobile_api.mobile_billing_status, name="billing_status"),
    path("leads/", mobile_api.mobile_leads, name="leads"),
    path("store/products/", mobile_api.mobile_store_products, name="store_products"),
    path("chaqmoq/history/", mobile_api.mobile_chaqmoq_history, name="chaqmoq_history"),
    path("store/purchase-requests/", mobile_api.mobile_purchase_requests, name="purchase_requests"),
    path("store/purchase-requests/create/", mobile_api.mobile_purchase_request_create, name="purchase_request_create"),
]
