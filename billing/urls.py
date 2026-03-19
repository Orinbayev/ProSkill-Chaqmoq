# billing/urls.py
from django.urls import path
from . import views
from . import click_views

app_name = "billing"

urlpatterns = [
    path("blocked/", views.blocked, name="blocked"),
    path("plans/", views.plans, name="plans"),
    path("api/plans/", views.plans_api, name="plans_api"),
    path("api/current-subscription/", views.current_subscription_api, name="current_subscription_api"),
    path("api/payment-status/", click_views.payment_status_api, name="payment_status_api"),
    path("order/create/", views.order_create, name="order_create"),
    path("requests/<int:pk>/approve/", views.subscription_request_approve, name="subscription_request_approve"),
    path("requests/<int:pk>/reject/", views.subscription_request_reject, name="subscription_request_reject"),

    # demo confirm (superadmin)
    path("order/<int:pk>/confirm-demo/", views.order_confirm_demo, name="order_confirm_demo"),
    path("order/<int:pk>/reject-demo/", views.order_reject_demo, name="order_reject_demo"),

    # ✅ Click payment integration
    path("order/click-create/", click_views.create_order_and_redirect, name="click_create"),
    path("order/click-payment-url/", click_views.create_order_and_redirect, name="click_payment_url"),
    path("payment/success/", click_views.payment_success, name="payment_success"),
    path("payment/cancel/", click_views.payment_cancel, name="payment_cancel"),
    path("click/prepare/", click_views.click_prepare),
    path("click/complete/", click_views.click_complete),
]
