# billing/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    SubscriptionPlan,
    CenterSubscription,
    PromoCode,
    SubscriptionOrder,
    PlanFeature,
    Subscription,
    PaymentTransaction,
    SubscriptionRequest,
    CenterFeatureOverride,
)

IMPL_BADGES = {
    "READY":   ('<span style="background:#22c55e;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">✅ Tayyor</span>'),
    "PARTIAL": ('<span style="background:#f59e0b;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">🔶 Qisman</span>'),
    "PLANNED": ('<span style="background:#6366f1;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">📋 Rejada</span>'),
}

CATEGORY_LABELS = {
    "core":      "🏠 Asosiy",
    "finance":   "💰 Moliya",
    "marketing": "🎯 Marketing",
    "team":      "👥 Jamoa",
    "advanced":  "⚡ Kengaytirilgan",
}


@admin.register(PlanFeature)
class PlanFeatureAdmin(admin.ModelAdmin):
    list_display = (
        "icon_name", "code", "category_badge", "impl_badge",
        "is_core_badge", "is_active", "order",
    )
    list_filter  = ("category", "is_core", "is_active", "implementation_status")
    search_fields = ("code", "name", "description_uz")
    ordering     = ("category", "order", "name")
    readonly_fields = ("code",)

    fieldsets = (
        ("Asosiy", {
            "fields": ("code", "name", "icon", "category", "order", "is_core", "is_active"),
        }),
        ("Tavsif", {
            "fields": ("description_uz",),
        }),
        ("Landing & Holat", {
            "fields": ("implementation_status", "show_on_landing", "is_highlight"),
        }),
        ("Ko'p tilli (ixtiyoriy)", {
            "classes": ("collapse",),
            "fields": ("name_uz", "name_ru", "name_en"),
        }),
    )

    @admin.display(description="Feature")
    def icon_name(self, obj):
        return format_html("{} {}", obj.icon or "•", obj.name)

    @admin.display(description="Kategoriya")
    def category_badge(self, obj):
        label = CATEGORY_LABELS.get(obj.category, obj.category)
        return format_html('<span style="font-weight:600">{}</span>', label)

    @admin.display(description="Holat")
    def impl_badge(self, obj):
        return format_html(IMPL_BADGES.get(obj.implementation_status, obj.implementation_status))

    @admin.display(description="Bepul?", boolean=False)
    def is_core_badge(self, obj):
        if obj.is_core:
            return format_html('<span style="color:#22c55e;font-weight:bold">♾ Bepul</span>')
        return format_html('<span style="color:#6b7280">💎 Premium</span>')


class PlanFeatureInline(admin.TabularInline):
    model = SubscriptionPlan.plan_features.through
    extra = 0
    verbose_name = "Feature"
    verbose_name_plural = "Tarif Xususiyatlari (M2M)"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("planfeature")


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display  = (
        "tier_badge", "code", "title", "price_display",
        "limits_display", "features_count", "is_popular", "is_recommended", "active",
    )
    list_filter   = ("active", "is_popular", "is_recommended")
    search_fields = ("code", "title")
    ordering      = ("tier",)
    filter_horizontal = ("plan_features",)

    fieldsets = (
        ("Tarif Asosi", {
            "fields": ("code", "title", "tier", "active", "is_popular", "is_recommended"),
        }),
        ("Narx", {
            "fields": ("price", "monthly_price", "price_3m", "price_6m", "price_9m", "price_12m", "duration_days"),
        }),
        ("Limitlar (0 = Cheksiz)", {
            "fields": ("max_students", "max_branches"),
            "description": "⚠️ Guruhlar va Xodimlar limiti yo'q — cheksiz.",
        }),
        ("Marketing Matnlari", {
            "fields": ("subtitle_uz", "description_uz", "student_range_uz", "landing_visible", "caption"),
        }),
        ("Xususiyatlar (Features)", {
            "fields": ("plan_features",),
            "description": "Bu tarifda qaysi feature'lar yoqilganini tanlang.",
        }),
    )

    @admin.display(description="Tier", ordering="tier")
    def tier_badge(self, obj):
        colors = {10: "#3b82f6", 20: "#8b5cf6", 30: "#f59e0b"}
        color = colors.get(obj.tier, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:bold">T{}</span>',
            color, obj.tier,
        )

    @admin.display(description="Narx")
    def price_display(self, obj):
        if obj.price == 0:
            return format_html('<span style="color:#8b5cf6;font-weight:bold">Custom</span>')
        return format_html(
            '<span style="font-weight:600">{:,}</span> <span style="color:#6b7280;font-size:11px">so\'m/oy</span>',
            obj.price,
        )

    @admin.display(description="Limitlar")
    def limits_display(self, obj):
        def lbl(v): return "♾" if v == 0 else str(v)
        return format_html(
            "👩‍🎓 {} | 🏫 {}",
            lbl(obj.max_students),
            lbl(obj.max_branches),
        )

    @admin.display(description="Features")
    def features_count(self, obj):
        n = obj.plan_features.filter(is_core=False).count()
        return format_html(
            '<span style="background:#e0f2fe;color:#0369a1;padding:2px 8px;border-radius:4px">{} ta</span>',
            n,
        )


@admin.register(CenterSubscription)
class CenterSubscriptionAdmin(admin.ModelAdmin):
    list_display  = ("center", "plan_badge", "status_badge", "expires_at", "days_left_display", "manual_block", "updated_at")
    list_filter   = ("status", "manual_block", "plan")
    search_fields = ("center__name", "center__slug")
    readonly_fields = ("started_at", "updated_at", "paused_at", "remaining_seconds")
    ordering = ("-expires_at",)

    @admin.display(description="Tarif")
    def plan_badge(self, obj):
        return format_html('<strong>{}</strong>', obj.plan.code)

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "ACTIVE":  "#22c55e",
            "PAUSED":  "#f59e0b",
            "EXPIRED": "#ef4444",
            "BLOCKED": "#1f2937",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.status,
        )

    @admin.display(description="Qolgan kun")
    def days_left_display(self, obj):
        d = obj.days_left()
        if d <= 0:
            return format_html('<span style="color:#ef4444;font-weight:bold">Tugagan</span>')
        if d <= 5:
            return format_html('<span style="color:#f59e0b;font-weight:bold">{} kun</span>', d)
        return format_html('<span style="color:#22c55e">{} kun</span>', d)


@admin.register(CenterFeatureOverride)
class CenterFeatureOverrideAdmin(admin.ModelAdmin):
    list_display  = ("center", "feature_display", "enabled_badge", "note", "created_by", "updated_at")
    list_filter   = ("enabled", "feature__category")
    search_fields = ("center__name", "feature__code", "feature__name")
    autocomplete_fields = ("center", "feature")

    @admin.display(description="Feature")
    def feature_display(self, obj):
        return format_html("{} {}", obj.feature.icon or "•", obj.feature.name)

    @admin.display(description="Holat")
    def enabled_badge(self, obj):
        if obj.enabled:
            return format_html('<span style="color:#22c55e;font-weight:bold">✅ Yoqilgan</span>')
        return format_html('<span style="color:#ef4444;font-weight:bold">❌ O\'chirilgan</span>')


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display  = ("code", "percent_off", "active_badge", "starts_at", "ends_at", "used_count", "max_uses")
    list_filter   = ("active",)
    search_fields = ("code",)

    @admin.display(description="Faol")
    def active_badge(self, obj):
        if obj.active:
            return format_html('<span style="color:#22c55e;font-weight:bold">✅</span>')
        return format_html('<span style="color:#ef4444">❌</span>')


@admin.register(SubscriptionOrder)
class SubscriptionOrderAdmin(admin.ModelAdmin):
    list_display  = ("id", "center", "plan", "duration_months", "final_price", "status_badge", "created_at", "paid_at")
    list_filter   = ("status", "plan")
    search_fields = ("center__name", "center__slug")

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {"PENDING": "#f59e0b", "PAID": "#22c55e", "CANCELED": "#ef4444"}
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.status,
        )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display  = ("id", "user", "plan", "start_date", "end_date", "is_active", "created_at")
    list_filter   = ("is_active", "plan")
    search_fields = ("user__email", "plan__code")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display  = ("transaction_id", "user", "amount", "status", "created_at")
    list_filter   = ("status",)
    search_fields = ("transaction_id", "user__email")


@admin.register(SubscriptionRequest)
class SubscriptionRequestAdmin(admin.ModelAdmin):
    list_display  = (
        "id", "center", "user", "plan_name",
        "duration_months", "amount", "status_badge", "created_at",
    )
    list_filter   = ("status", "plan_name", "duration_months")
    search_fields = ("center__name", "user__email", "plan_name")

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {"pending": "#f59e0b", "paid": "#22c55e", "cancelled": "#ef4444"}
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.status,
        )
