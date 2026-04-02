from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


class Plan(models.Model):
    name = models.CharField(max_length=50)
    price_monthly = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_teachers = models.PositiveIntegerField(default=5)
    max_students = models.PositiveIntegerField(default=200)
    enable_store = models.BooleanField(default=True)
    enable_chaqmoq = models.BooleanField(default=True)
    enable_attendance = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class EducationCenter(TenantMixin):
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    paid_until = models.DateField(null=True, blank=True)

    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)

    # django-tenants talab qiladigan field:
    auto_create_schema = True

    def __str__(self):
        return self.name


class CenterDomain(DomainMixin):
    pass
