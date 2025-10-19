from django.contrib import admin
from .models import Group, Enrollment, Payment, Attendance
from .models import DailyLightningSetting


admin.site.register(Group)
admin.site.register(Enrollment)
admin.site.register(Payment)
admin.site.register(Attendance) 

@admin.register(DailyLightningSetting)
class DailyLightningSettingAdmin(admin.ModelAdmin):
    list_display = ("date", "max_lightning", "active")
    list_filter = ("active",)

