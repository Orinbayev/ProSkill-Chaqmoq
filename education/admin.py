from django.contrib import admin
from .models import Group, Enrollment, Payment, Attendance


admin.site.register(Group)
admin.site.register(Enrollment)
admin.site.register(Payment)
admin.site.register(Attendance) 