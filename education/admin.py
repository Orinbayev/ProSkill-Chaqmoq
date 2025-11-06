from django.contrib import admin
from .models import Group, Enrollment, Payment, Attendance
from .models import DailyLightningSetting
from .models import Category


admin.site.register(Group)
admin.site.register(Enrollment)
admin.site.register(Payment)
admin.site.register(Attendance) 



@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "description")
    search_fields = ("name",)


@admin.register(DailyLightningSetting)
class DailyLightningSettingAdmin(admin.ModelAdmin):
    list_display = ("date", "max_lightning", "active")
    list_filter = ("active",)

