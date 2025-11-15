from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Center

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
    list_display = ('nom','manzil')
