from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Center
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse


@admin.register(User)
class UserAdmin(BaseUserAdmin):

    list_display = ('email', 'ism', 'familya', 'role', 'center', 'oqituvchi_foizi', 'is_staff')
    list_filter = ('role', 'center', 'is_staff', 'is_active')
    search_fields = ('email', 'ism', 'familya')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),

        ('Shaxsiy maʼlumot', {
            'fields': (
                'ism', 'familya', 'telefon1', 'telefon2',
                'lavozim', 'gmail', 'role', 'center'
            )
        }),

        ('O‘qituvchi ulushi', {
            'fields': ('oqituvchi_foizi',),
        }),

        ('Ruxsatlar', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            )
        }),

        ('Muhim sanalar', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role')
        }),
    )
    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))

        if obj and obj.role == "teacher":
            fieldsets.append(
                ("O‘qituvchi ulushi", {"fields": ("oqituvchi_foizi",)})
            )

        return fieldsets



@admin.register(Center)
class CenterAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "plan",
        "status",
        "status_badge",
        "expires_at",
        "days_left_badge",
        "switch_link",
        "created_at",
    )
    list_filter = ("plan", "status")
    search_fields = ("name", "slug", "address")
    ordering = ("name",)

    actions = (
        "extend_30_days",
        "extend_90_days",
        "extend_180_days",
        "extend_365_days",
        "block_centers",
        "unblock_centers",
    )

    def status_badge(self, obj: Center):
        if obj.status == Center.STATUS_BLOCKED:
            return format_html('<span style="padding:3px 8px;border-radius:10px;background:#ef4444;color:white;font-weight:700;">BLOCKED</span>')
        return format_html('<span style="padding:3px 8px;border-radius:10px;background:#22c55e;color:#052e16;font-weight:800;">ACTIVE</span>')
    status_badge.short_description = "Status"

    def days_left_badge(self, obj: Center):
        dl = obj.days_left
        if dl is None:
            return format_html('<span style="color:#94a3b8;">—</span>')
        if dl == 0:
            return format_html('<span style="padding:3px 8px;border-radius:10px;background:#ef4444;color:white;font-weight:800;">0</span>')
        if dl <= 7:
            return format_html('<span style="padding:3px 8px;border-radius:10px;background:#f59e0b;color:#111827;font-weight:900;">{}d</span>', dl)
        return format_html('<span style="padding:3px 8px;border-radius:10px;background:#22c55e;color:#052e16;font-weight:900;">{}d</span>', dl)
    days_left_badge.short_description = "Days left"

    def switch_link(self, obj: Center):
        # ✅ admin listda link bilan switch qilish
        url = reverse("accounts:center_switch") + f"?center_id={obj.id}&next=/"
        return format_html('<a class="button" href="{}">Switch</a>', url)
    switch_link.short_description = "Switch"

    # -------- Actions --------
    def _extend(self, request, queryset, days: int):
        now = timezone.now()
        for c in queryset:
            base = c.expires_at if c.expires_at and c.expires_at > now else now
            c.expires_at = base + timezone.timedelta(days=days)
            c.status = Center.STATUS_ACTIVE
            c.save(update_fields=["expires_at", "status"])
        self.message_user(request, f"✅ Subscription +{days} days uzaytirildi.", level=messages.SUCCESS)

    @admin.action(description="Extend subscription +30 days")
    def extend_30_days(self, request, queryset):
        self._extend(request, queryset, 30)

    @admin.action(description="Extend subscription +90 days")
    def extend_90_days(self, request, queryset):
        self._extend(request, queryset, 90)

    @admin.action(description="Extend subscription +180 days")
    def extend_180_days(self, request, queryset):
        self._extend(request, queryset, 180)

    @admin.action(description="Extend subscription +365 days")
    def extend_365_days(self, request, queryset):
        self._extend(request, queryset, 365)

    @admin.action(description="Block selected centers")
    def block_centers(self, request, queryset):
        queryset.update(status=Center.STATUS_BLOCKED)
        self.message_user(request, "⛔ Centerlar BLOCKED qilindi.", level=messages.WARNING)

    @admin.action(description="Unblock selected centers")
    def unblock_centers(self, request, queryset):
        queryset.update(status=Center.STATUS_ACTIVE)
        self.message_user(request, "✅ Centerlar ACTIVE qilindi.", level=messages.SUCCESS)