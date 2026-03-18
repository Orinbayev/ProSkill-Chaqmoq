# billing/urls.py
from django.urls import path
from . import views

app_name = "billing"

urlpatterns = [
    path("blocked/", views.blocked, name="blocked"),
    path("plans/", views.plans, name="plans"),
    path("api/plans/", views.plans_api, name="plans_api"),
    path("api/current-subscription/", views.current_subscription_api, name="current_subscription_api"),
    path("order/create/", views.order_create, name="order_create"),
    path("requests/<int:pk>/approve/", views.subscription_request_approve, name="subscription_request_approve"),
    path("requests/<int:pk>/reject/", views.subscription_request_reject, name="subscription_request_reject"),

    # demo confirm (superadmin)
    path("order/<int:pk>/confirm-demo/", views.order_confirm_demo, name="order_confirm_demo"),
    path("order/<int:pk>/reject-demo/", views.order_reject_demo, name="order_reject_demo"),
]
