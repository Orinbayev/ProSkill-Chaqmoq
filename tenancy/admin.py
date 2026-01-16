from django.contrib import admin
from tenancy.models import EducationCenter, CenterDomain, Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price_monthly", "max_teachers", "max_students",
                    "enable_store", "enable_chaqmoq", "enable_attendance")
    search_fields = ("name",)
    list_filter = ("enable_store", "enable_chaqmoq", "enable_attendance")


@admin.register(EducationCenter)
class EducationCenterAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "schema_name", "is_active", "paid_until", "plan")
    search_fields = ("name", "schema_name")
    list_filter = ("is_active", "plan")
    ordering = ("-id",)


@admin.register(CenterDomain)
class CenterDomainAdmin(admin.ModelAdmin):
    list_display = ("id", "domain", "tenant", "is_primary")
    search_fields = ("domain", "tenant__name", "tenant__schema_name")
    list_filter = ("is_primary",)
