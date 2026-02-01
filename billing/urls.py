# billing/urls.py
from django.urls import path
from . import views

app_name = "billing"

urlpatterns = [
    path("blocked/", views.blocked, name="blocked"),
    path("plans/", views.plans, name="plans"),
    path("order/create/", views.order_create, name="order_create"),

    # demo confirm (superadmin)
    path("order/<int:pk>/confirm-demo/", views.order_confirm_demo, name="order_confirm_demo"),
]
