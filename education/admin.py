from django.contrib import admin
from .models import Group, Enrollment, Payment

admin.site.register(Group)
admin.site.register(Enrollment)
admin.site.register(Payment)