from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Center

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Shaxsiy maʼlumot', {'fields': ('ism', 'familya', 'telefon1', 'telefon2', 'lavozim', 'gmail', 'role', 'center')}),
        ('Ruxsatlar', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Muhim sanalar', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role')
        }),
    )
    list_display = ('email','ism','familya','role','center','is_staff')
    search_fields = ('email','ism','familya')
    ordering = ('email',)

@admin.register(Center)
class CenterAdmin(admin.ModelAdmin):
    list_display = ('nom','manzil')
