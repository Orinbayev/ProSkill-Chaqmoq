# billing/admin.py
from django.contrib import admin
from .models import SubscriptionPlan, CenterSubscription, PromoCode, SubscriptionOrder, PlanFeature
from .services import mark_order_paid


@admin.register(PlanFeature)
class PlanFeatureAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "is_core", "order")
    list_filter = ("category", "is_core")
    search_fields = ("code", "name")


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "monthly_price", "max_students", "max_users", "max_groups", "is_popular", "active")
    list_filter = ("active", "is_popular")
    search_fields = ("code", "title")
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
    actions = ["make_paid"]

    def make_paid(self, request, queryset):
        for order in queryset:
            mark_order_paid(order)
    make_paid.short_description = "Tanlangan orderlarni PAID qilish"
