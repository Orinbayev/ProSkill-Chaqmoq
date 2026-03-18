# billing/admin.py
from django.contrib import admin
from .models import (
    SubscriptionPlan,
    CenterSubscription,
    PromoCode,
    SubscriptionOrder,
    PlanFeature,
    Subscription,
    PaymentTransaction,
    SubscriptionRequest,
)


@admin.register(PlanFeature)
class PlanFeatureAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "is_core", "order")
    list_filter = ("category", "is_core")
    search_fields = ("code", "name")


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "name",
        "monthly_price",
        "price",
        "duration_days",
        "max_students",
        "max_users",
        "max_groups",
        "is_popular",
        "active",
    )
    list_filter = ("active", "is_popular")
    search_fields = ("code", "title", "name")
    filter_horizontal = ("plan_features",)



@admin.register(CenterSubscription)
class CenterSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("center", "plan", "status", "expires_at", "manual_block", "updated_at")
    list_filter = ("status", "manual_block", "plan")
    search_fields = ("center__name", "center__slug")


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "percent_off", "active", "starts_at", "ends_at", "used_count", "max_uses")
    list_filter = ("active",)
    search_fields = ("code",)


@admin.register(SubscriptionOrder)
class SubscriptionOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "center", "plan", "duration_months", "final_price", "status", "created_at", "paid_at")
    list_filter = ("status", "plan")
    search_fields = ("center__name", "center__slug", "id")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "plan", "start_date", "end_date", "is_active", "created_at")
    list_filter = ("is_active", "plan")
    search_fields = ("user__email", "user__ism", "user__familya", "plan__code")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("transaction_id", "user", "amount", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("transaction_id", "user__email")


@admin.register(SubscriptionRequest)
class SubscriptionRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "center",
        "user",
        "merchant_trans_id",
        "plan",
        "plan_name",
        "duration_months",
        "amount",
        "price",
        "status",
        "created_at",
    )
    list_filter = ("status", "plan_name", "duration_months")
    search_fields = ("center__name", "user__email", "plan_name")
