from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Branch, BranchRequest, Center, DirectorCenterAccess, ParentTelegramLinkToken, User
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse


@admin.register(User)
class UserAdmin(BaseUserAdmin):

    list_display = ('email', 'ism', 'familya', 'role', 'child_code', 'center', 'is_demo_user', 'oqituvchi_foizi', 'is_staff')
    list_filter = ('role', 'center', 'is_demo_user', 'is_staff', 'is_active')
    search_fields = ('email', 'ism', 'familya', 'child_code')
    ordering = ('email',)
    readonly_fields = ('child_code',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),

        ('Shaxsiy maʼlumot', {
            'fields': (
                'ism', 'familya', 'telefon1', 'telefon2',
                'lavozim', 'gmail', 'role', 'center', 'is_demo_user', 'child_code'
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


@admin.register(ParentTelegramLinkToken)
class ParentTelegramLinkTokenAdmin(admin.ModelAdmin):
    list_display = ("student", "created_by", "expires_at", "used_at", "used_by_telegram_id")
    list_filter = ("used_at", "expires_at")
    search_fields = ("token", "student__email", "student__ism", "student__familya", "used_by_telegram_id")
    readonly_fields = ("token", "created_at", "used_at", "used_by", "used_by_telegram_id")



@admin.register(Center)
class CenterAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "parent_center",
        "is_demo",
        "plan",
        "status",
        "status_badge",
        "expires_at",
        "days_left_badge",
        "switch_link",
        "created_at",
    )
    list_filter = ("is_demo", "plan", "status", "parent_center")
    search_fields = ("name", "slug", "address")
    ordering = ("name",)

    actions = (
        "extend_30_days",
        "extend_90_days",
        "extend_180_days",
        "extend_365_days",
        "block_centers",
        "unblock_centers",
        "remove_own_subscriptions",
    )
    raw_id_fields = ("parent_center",)

    def remove_own_subscriptions(self, request, queryset):
        """
        Tanlangan markazlarni filial qilib o'rnatish uchun:
        O'z subscription-larini o'chiradi — ular endi parent_center orqali oladi.
        """
        from billing.models import CenterSubscription
        count = 0
        for c in queryset:
            if c.parent_center_id:
                deleted, _ = CenterSubscription.objects.filter(center=c).delete()
                count += deleted
        self.message_user(
            request,
            f"{count} ta subscription o'chirildi. "
            "Endi bu filiallar asosiy markazining tarifidan foydalanadi.",
        )
    remove_own_subscriptions.short_description = (
        "Filial: o'z subscriptionlarini o'chir (parent tarifga o'tish)"
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
        url = reverse("platform_global:center_switch") + f"?center_id={obj.id}&next=/"
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


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "center", "address", "phone", "is_active", "created_at")
    list_filter = ("center", "is_active")
    search_fields = ("name", "center__name", "address")


@admin.register(DirectorCenterAccess)
class DirectorCenterAccessAdmin(admin.ModelAdmin):
    list_display = ("director", "center", "is_active", "granted_at")
    list_filter = ("is_active",)
    search_fields = ("director__email", "director__ism", "director__familya", "center__name")


@admin.register(BranchRequest)
class BranchRequestAdmin(admin.ModelAdmin):
    list_display = ("name", "requester", "parent_center", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "requester__email", "parent_center__name")
    readonly_fields = ("created_at", "reviewed_at")
