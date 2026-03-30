from django.contrib import admin
from django.db import models
from django.forms import Textarea
from django.utils.html import format_html

from .models import (
    FAQ,
    DemoLead,
    FeatureBlock,
    PartnerLogo,
    PricingFeature,
    PricingPlan,
    ScreenshotSection,
    SiteSetting,
    StaticPage,
    SupportCard,
    Testimonial,
    Vacancy,
)


class RichTextAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {"widget": Textarea(attrs={"rows": 4, "style": "width: 80%;"})},
    }


@admin.register(SiteSetting)
class SiteSettingAdmin(RichTextAdmin):
    list_display = ("site_name", "phone", "is_active", "updated_at", "logo_preview")
    search_fields = ("site_name", "phone", "meta_title")
    list_filter = ("is_active",)
    ordering = ("-updated_at",)

    @admin.display(description="Logo")
    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="height:38px;border-radius:8px;"/>', obj.logo.url)
        return "-"


@admin.register(PartnerLogo)
class PartnerLogoAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_active", "logo_preview")
    search_fields = ("name",)
    list_filter = ("is_active",)
    ordering = ("order",)
    list_editable = ("order", "is_active")

    @admin.display(description="Rasm")
    def logo_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:36px;border-radius:6px;"/>', obj.image.url)
        return "-"


@admin.register(FeatureBlock)
class FeatureBlockAdmin(RichTextAdmin):
    list_display = ("title", "section", "order", "is_active", "image_preview")
    search_fields = ("title", "subtitle", "description")
    list_filter = ("section", "is_active")
    ordering = ("section", "order")
    list_editable = ("order", "is_active")

    @admin.display(description="Rasm")
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:36px;border-radius:6px;"/>', obj.image.url)
        return "-"


@admin.register(ScreenshotSection)
class ScreenshotSectionAdmin(RichTextAdmin):
    list_display = ("title", "order", "is_active", "image_preview")
    search_fields = ("title", "description")
    list_filter = ("is_active",)
    ordering = ("order",)
    list_editable = ("order", "is_active")

    @admin.display(description="Preview")
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:36px;border-radius:6px;"/>', obj.image.url)
        return "-"


class PricingFeatureInline(admin.TabularInline):
    model = PricingFeature
    extra = 1
    fields = ("text", "order")
    ordering = ("order",)


@admin.register(PricingPlan)
class PricingPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "duration_months",
        "student_range",
        "current_price",
        "old_price",
        "discount_label",
        "badge_text",
        "is_recommended",
        "is_active",
        "order",
    )
    search_fields = ("name", "student_range", "badge_text", "discount_label")
    list_filter = ("duration_months", "is_recommended", "is_active")
    ordering = ("duration_months", "order")
    list_editable = ("is_recommended", "is_active", "order")
    inlines = [PricingFeatureInline]


@admin.register(PricingFeature)
class PricingFeatureAdmin(admin.ModelAdmin):
    list_display = ("pricing_plan", "text", "order")
    search_fields = ("text", "pricing_plan__name")
    list_filter = ("pricing_plan",)
    ordering = ("pricing_plan", "order")


@admin.register(Testimonial)
class TestimonialAdmin(RichTextAdmin):
    list_display = ("full_name", "center_name", "rating", "is_active", "order", "avatar_preview")
    search_fields = ("full_name", "center_name", "role", "text")
    list_filter = ("is_active", "rating")
    ordering = ("order",)
    list_editable = ("is_active", "order")

    @admin.display(description="Avatar")
    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html('<img src="{}" style="height:34px;width:34px;object-fit:cover;border-radius:999px;"/>', obj.avatar.url)
        return "-"


@admin.register(FAQ)
class FAQAdmin(RichTextAdmin):
    list_display = ("question", "order", "is_active")
    search_fields = ("question", "answer")
    list_filter = ("is_active",)
    ordering = ("order",)
    list_editable = ("order", "is_active")


@admin.action(description="Tanlangan leadlarni bog'landi deb belgilash")
def mark_contacted(modeladmin, request, queryset):
    queryset.update(is_contacted=True)


@admin.register(DemoLead)
class DemoLeadAdmin(RichTextAdmin):
    list_display = ("full_name", "center_name", "phone", "region", "is_contacted", "created_at")
    search_fields = ("full_name", "center_name", "phone", "region", "note")
    list_filter = ("is_contacted", "region", "created_at")
    ordering = ("-created_at",)
    list_editable = ("is_contacted",)
    readonly_fields = ("created_at",)
    actions = [mark_contacted]


@admin.register(SupportCard)
class SupportCardAdmin(RichTextAdmin):
    list_display = ("title", "button_text", "button_url", "order", "is_active")
    search_fields = ("title", "description", "button_url")
    list_filter = ("is_active",)
    ordering = ("order",)
    list_editable = ("order", "is_active")


@admin.register(Vacancy)
class VacancyAdmin(RichTextAdmin):
    list_display = ("title", "city", "employment_type", "department", "order", "is_active")
    search_fields = ("title", "city", "department", "description")
    list_filter = ("employment_type", "department", "is_active")
    ordering = ("order",)
    list_editable = ("order", "is_active")


@admin.register(StaticPage)
class StaticPageAdmin(RichTextAdmin):
    list_display = ("key", "title", "is_active", "updated_at")
    search_fields = ("key", "title", "content")
    list_filter = ("is_active", "key")
    ordering = ("key",)
    list_editable = ("is_active",)
